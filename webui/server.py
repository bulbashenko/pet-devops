#!/usr/bin/env python3
"""Release Console — a tiny web panel to view versions and deploy/roll back.

Deliberately dependency-free (Python standard library only) and deliberately
thin: it renders git history and the target's live state, and every button
shells out to the same `make` targets a developer runs by hand. The actual
build and deploy happen inside the jenkins-agent container via
scripts/release_deploy.sh — the Arch host has neither dpkg-deb nor ansible.

    make ui      # then open http://localhost:8090

Nothing here is a security boundary: it runs commands on your machine and is
meant for localhost only. It refuses to deploy a ref it did not itself list.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBUI_DIR = Path(__file__).resolve().parent
AGENT = "pet-devops-jenkins-agent"
TARGET = "pet-devops-target"
HEALTHZ = "http://localhost:8080/healthz"
PORT = 8090
COMMIT_COUNT = 8
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def derive_version(ref: str) -> str:
    """Mirror scripts/version.sh for a given ref: vX.Y.Z-N-gSHA -> X.Y.Z[.devN+gSHA]."""
    try:
        d = git("describe", "--tags", "--match", "v[0-9]*", "--long", ref)
    except subprocess.CalledProcessError:
        sha = git("rev-parse", "--short", ref)
        return f"0.1.0.dev0+g{sha}"
    sha = d.rsplit("-", 1)[-1]          # g1a2b3c4
    rest = d.rsplit("-", 1)[0]          # v1.2.3-4
    distance = rest.rsplit("-", 1)[-1]  # 4
    base = rest.rsplit("-", 1)[0][1:]   # 1.2.3
    if distance == "0":
        return base
    return f"{base}.dev{distance}+{sha}"


def list_versions() -> list[dict]:
    """Tags (real releases) and recent commits, newest first, de-duplicated."""
    seen: set[str] = set()
    rows: list[dict] = []

    def add(ref: str, kind: str) -> None:
        full = git("rev-parse", ref)
        if full in seen:
            return
        seen.add(full)
        short = full[:7]
        rows.append({
            "id": short,
            "kind": kind,
            "version": derive_version(full),
            "sha": short,
            "subject": git("log", "-1", "--format=%s", full),
            "date": git("log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M", full),
            # Commit time, so the UI can say "roll back" vs "deploy" by real
            # chronology rather than by this list's tags-first ordering.
            "ts": int(git("log", "-1", "--format=%ct", full)),
        })

    for tag in git("tag", "--list", "v[0-9]*", "--sort=-creatordate").splitlines():
        if tag.strip():
            add(tag.strip(), "tag")
    for sha in git("rev-list", f"-{COMMIT_COUNT}", "HEAD").splitlines():
        add(sha.strip(), "commit")
    return rows


def deployed_state() -> dict:
    """What the target believes it has installed, and what it is actually serving."""
    installed = None
    try:
        installed = subprocess.run(
            ["docker", "exec", TARGET, "dpkg-query",
             "--showformat=${Version}", "--show", "sensor-hub"],
            capture_output=True, text=True, timeout=8,
        ).stdout.strip() or None
    except Exception:
        pass
    serving, healthy = None, False
    try:
        with urllib.request.urlopen(HEALTHZ, timeout=4) as r:
            body = json.loads(r.read().decode())
            serving = body.get("version")
            healthy = body.get("status") == "ok"
    except Exception:
        pass
    return {"installed": installed, "serving": serving, "healthy": healthy}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quieter console
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlparse(self.path)
        if route.path in ("/", "/index.html"):
            html = (WEBUI_DIR / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")
        if route.path == "/api/state":
            payload = {"versions": list_versions(), "deployed": deployed_state()}
            return self._send(200, json.dumps(payload).encode(), "application/json")
        if route.path == "/api/deploy":
            return self._stream_deploy(parse_qs(route.query).get("ref", [""])[0])
        self._send(404, b"not found", "text/plain")

    def _stream_deploy(self, ref_id: str) -> None:
        # Only deploy a ref we ourselves just listed — never a raw client string.
        allowed = {r["sha"]: r for r in list_versions()}
        row = allowed.get(ref_id)
        if row is None or not SHA_RE.match(ref_id):
            return self._send(400, b"unknown ref\n", "text/plain")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(line: str) -> None:
            try:
                self.wfile.write(line.encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                raise

        emit(f"# deploying {row['version']}  ({row['kind']} {ref_id}: {row['subject']})\n")
        proc = subprocess.Popen(
            ["docker", "exec", AGENT, "bash",
             "/workspace/scripts/release_deploy.sh", ref_id],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                emit(line)
            code = proc.wait()
        except (BrokenPipeError, ConnectionResetError):
            proc.kill()
            return
        emit(f"\n# exit code {code}\n")
        emit("__RC_DONE_OK__\n" if code == 0 else "__RC_DONE_FAIL__\n")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Release Console on http://localhost:{PORT}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
