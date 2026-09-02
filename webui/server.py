#!/usr/bin/env python3
"""Release Console — view released versions and deploy / roll back between them.

Deliberately dependency-free (Python standard library only) and deliberately
thin. The model is the same as production:

  * Release  — the sensor-hub-release Jenkins job builds, tests, publishes the
               artifacts to Artifactory and deploys HEAD. That is how a version
               gets into the registry.
  * Roll back — install an already-published .deb straight from Artifactory. No
               rebuild; the exact artifact that was released is what goes back.

    make ui      # then open http://localhost:8090

Localhost only; it runs commands on your machine. It refuses to act on a ref it
did not itself list, and only offers versions that are actually in the registry.
"""
from __future__ import annotations

import base64
import http.cookiejar
import json
import re
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode

REPO_ROOT = Path(__file__).resolve().parent.parent
WEBUI_DIR = Path(__file__).resolve().parent
AGENT = "pet-devops-jenkins-agent"
TARGET = "pet-devops-target"
HEALTHZ = "http://localhost:8080/healthz"
PORT = 8090
COMMIT_COUNT = 8
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

JENKINS = "http://localhost:8081"
JENKINS_USER, JENKINS_PASS = "admin", "admin"
RELEASE_JOB = "sensor-hub-release"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def derive_version(ref: str) -> str:
    """Mirror scripts/version.sh: vX.Y.Z-N-gSHA -> X.Y.Z[.devN+gSHA]."""
    try:
        d = git("describe", "--tags", "--match", "v[0-9]*", "--long", ref)
    except subprocess.CalledProcessError:
        return "0.1.0.dev0+g" + git("rev-parse", "--short", ref)
    sha = d.rsplit("-", 1)[-1]
    rest = d.rsplit("-", 1)[0]
    distance = rest.rsplit("-", 1)[-1]
    base = rest.rsplit("-", 1)[0][1:]
    return base if distance == "0" else f"{base}.dev{distance}+{sha}"


def list_versions() -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []

    def add(ref: str, kind: str) -> None:
        full = git("rev-parse", ref)
        if full in seen:
            return
        seen.add(full)
        rows.append({
            "id": full[:7],
            "kind": kind,
            "version": derive_version(full),
            "sha": full[:7],
            "subject": git("log", "-1", "--format=%s", full),
            "date": git("log", "-1", "--format=%cd", "--date=format:%Y-%m-%d %H:%M", full),
            "ts": int(git("log", "-1", "--format=%ct", full)),
        })

    for tag in git("tag", "--list", "v[0-9]*", "--sort=-creatordate").splitlines():
        if tag.strip():
            add(tag.strip(), "tag")
    for sha in git("rev-list", f"-{COMMIT_COUNT}", "HEAD").splitlines():
        add(sha.strip(), "commit")
    return rows


def head_info() -> dict:
    full = git("rev-parse", "HEAD")
    return {"sha": full[:7], "version": derive_version(full),
            "subject": git("log", "-1", "--format=%s", full)}


def deployed_state() -> dict:
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


# --- Artifactory -------------------------------------------------------------

def _load_jfrog_env() -> dict:
    env: dict[str, str] = {}
    try:
        for line in (REPO_ROOT / "secrets" / "jfrog.env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env


JFROG = _load_jfrog_env()


def artifactory_enabled() -> bool:
    return bool(JFROG.get("JFROG_URL") and JFROG.get("JFROG_TOKEN"))


def published_versions() -> list[str]:
    if not artifactory_enabled():
        return []
    api = (JFROG["JFROG_URL"].rstrip("/")
           + "/api/storage/pet-devops-generic/sensor-hub?list&deep=1")
    try:
        req = urllib.request.Request(
            api, headers={"Authorization": "Bearer " + JFROG["JFROG_TOKEN"]})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode())
        vers = set()
        for f in data.get("files", []):
            parts = f.get("uri", "").lstrip("/").split("/")
            if len(parts) >= 2 and parts[-1].endswith(".deb"):
                vers.add(parts[0])
        return sorted(vers)
    except Exception:
        return []


# --- Jenkins (release job) ---------------------------------------------------

def _jenkins_auth() -> str:
    return "Basic " + base64.b64encode(
        f"{JENKINS_USER}:{JENKINS_PASS}".encode()).decode()


def _jenkins_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def _jenkins_get(opener, path: str, timeout: int = 8) -> str:
    req = urllib.request.Request(JENKINS + path,
                                 headers={"Authorization": _jenkins_auth()})
    with opener.open(req, timeout=timeout) as r:
        return r.read().decode()


def jenkins_available() -> bool:
    try:
        _jenkins_get(_jenkins_opener(), f"/job/{RELEASE_JOB}/api/json?tree=name", 4)
        return True
    except Exception:
        return False


def trigger_release(opener) -> int:
    """Cut a release of HEAD: build, test, publish to Artifactory, deploy."""
    crumb = json.loads(_jenkins_get(opener, "/crumbIssuer/api/json"))["crumb"]
    n = json.loads(_jenkins_get(
        opener, f"/job/{RELEASE_JOB}/api/json?tree=nextBuildNumber"))["nextBuildNumber"]
    data = urlencode({"DEPLOY_SOURCE": "artifactory", "SKIP_DEPLOY": "false"}).encode()
    req = urllib.request.Request(
        JENKINS + f"/job/{RELEASE_JOB}/buildWithParameters", data=data,
        headers={"Authorization": _jenkins_auth(), "Jenkins-Crumb": crumb})
    opener.open(req, timeout=8).read()
    return n


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _open_stream(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def _emit(self, line: str) -> None:
        self.wfile.write(line.encode())
        self.wfile.flush()

    def do_GET(self) -> None:
        route = urlparse(self.path)
        if route.path in ("/", "/index.html"):
            return self._send(200, (WEBUI_DIR / "index.html").read_bytes(),
                              "text/html; charset=utf-8")
        if route.path == "/api/state":
            payload = {
                "versions": list_versions(),
                "head": head_info(),
                "deployed": deployed_state(),
                "jenkins": jenkins_available(),
                "artifactory": {
                    "enabled": artifactory_enabled(),
                    "published": published_versions(),
                },
            }
            return self._send(200, json.dumps(payload).encode(), "application/json")
        if route.path == "/api/deploy_artifactory":
            return self._stream_artifactory(parse_qs(route.query).get("ref", [""])[0])
        if route.path == "/api/release":
            return self._stream_release()
        self._send(404, b"not found", "text/plain")

    def _stream_artifactory(self, ref_id: str) -> None:
        row = {r["sha"]: r for r in list_versions()}.get(ref_id)
        if row is None or not SHA_RE.match(ref_id):
            return self._send(400, b"unknown ref\n", "text/plain")
        if not artifactory_enabled():
            return self._send(400, b"Artifactory is not configured\n", "text/plain")
        if row["version"] not in published_versions():
            return self._send(409, b"that version is not published to Artifactory\n",
                               "text/plain")
        self._open_stream()
        self._emit(f"# deploying {row['version']} from Artifactory — no rebuild\n")
        proc = subprocess.Popen(
            ["docker", "exec",
             "-e", "JFROG_URL=" + JFROG["JFROG_URL"],
             "-e", "JFROG_TOKEN=" + JFROG["JFROG_TOKEN"],
             AGENT, "bash",
             "/workspace/scripts/release_deploy_artifactory.sh", row["version"]],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        self._pump(proc)

    def _stream_release(self) -> None:
        if not jenkins_available():
            return self._send(400, b"Jenkins is not reachable\n", "text/plain")
        self._open_stream()
        try:
            opener = _jenkins_opener()
            self._emit(f"# cutting a release of HEAD via {RELEASE_JOB}\n")
            n = trigger_release(opener)
            url = f"{JENKINS}/job/{RELEASE_JOB}/{n}/"
            self._emit(f"# Jenkins build #{n}: {url}console\n\n")
            for _ in range(60):
                try:
                    _jenkins_get(opener, f"/job/{RELEASE_JOB}/{n}/api/json?tree=id")
                    break
                except Exception:
                    time.sleep(2)
            sent = 0
            while True:
                console = _jenkins_get(opener, f"/job/{RELEASE_JOB}/{n}/consoleText", 12)
                if len(console) > sent:
                    self._emit(console[sent:])
                    sent = len(console)
                info = json.loads(_jenkins_get(
                    opener, f"/job/{RELEASE_JOB}/{n}/api/json?tree=building,result"))
                if not info.get("building"):
                    ok = info.get("result") == "SUCCESS"
                    self._emit(f"\n# Jenkins result: {info.get('result')}  ({url})\n")
                    self._emit("__RC_DONE_OK__\n" if ok else "__RC_DONE_FAIL__\n")
                    return
                time.sleep(3)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as e:
            try:
                self._emit(f"\n# error talking to Jenkins: {e}\n__RC_DONE_FAIL__\n")
            except Exception:
                pass

    def _pump(self, proc: subprocess.Popen) -> None:
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                self._emit(line)
            code = proc.wait()
        except (BrokenPipeError, ConnectionResetError):
            proc.kill()
            return
        self._emit(f"\n# exit code {code}\n")
        self._emit("__RC_DONE_OK__\n" if code == 0 else "__RC_DONE_FAIL__\n")


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Release Console on http://localhost:{PORT}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
