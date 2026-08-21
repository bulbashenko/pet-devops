#!/usr/bin/env python3
"""Post-deployment smoke test.

Runs against whatever is already deployed and answers one question: is this
instance actually serving correct data, not merely listening? It deliberately
uses nothing but the standard library so it can run on a bare target host with
no virtualenv.

    scripts/smoke_test.py                          # http://127.0.0.1:8080
    scripts/smoke_test.py --endpoint http://host:8080 --expect-version 1.2.3
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_ENDPOINT = "http://127.0.0.1:8080"
EXPECTED_SENSORS = {"temp-01", "humidity-01", "imu-01-accel-z"}


class SmokeFailure(Exception):
    """A check that did not hold."""


def fetch(endpoint: str, path: str, timeout: float = 5.0) -> dict:
    url = f"{endpoint.rstrip('/')}{path}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            if response.status != 200:
                raise SmokeFailure(f"{url} returned HTTP {response.status}")
            return json.loads(response.read().decode())
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"cannot reach {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"{url} returned a non-JSON body") from exc


def wait_for_health(endpoint: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return fetch(endpoint, "/healthz")
        except SmokeFailure as exc:
            last = exc
            time.sleep(1.0)
    raise SmokeFailure(f"never became healthy within {timeout:.0f}s: {last}")


def check_health(endpoint: str, timeout: float, expect_version: str | None) -> str:
    payload = wait_for_health(endpoint, timeout)

    if payload.get("status") != "ok":
        raise SmokeFailure(f"/healthz reports status={payload.get('status')!r}")

    version = payload.get("version", "")
    if not version:
        raise SmokeFailure("/healthz did not report a version")
    if expect_version and version != expect_version:
        raise SmokeFailure(f"expected version {expect_version}, daemon serves {version}")

    return version


def check_readings(endpoint: str) -> None:
    payload = fetch(endpoint, "/api/v1/readings?n=5")
    readings = payload.get("readings", [])

    # Three channels, five samples each.
    if len(readings) != 15:
        raise SmokeFailure(f"expected 15 readings for n=5, got {len(readings)}")

    sensors = {reading["sensor_id"] for reading in readings}
    if sensors != EXPECTED_SENSORS:
        raise SmokeFailure(f"unexpected sensor set: {sorted(sensors)}")

    timestamps = [reading["timestamp_ms"] for reading in readings]
    if sorted(timestamps) != timestamps:
        raise SmokeFailure("readings are not ordered by timestamp")


def check_stats(endpoint: str) -> None:
    payload = fetch(endpoint, "/api/v1/stats?n=50")

    per_sensor = payload.get("per_sensor", {})
    if set(per_sensor) != EXPECTED_SENSORS:
        raise SmokeFailure(f"stats cover {sorted(per_sensor)}, expected {sorted(EXPECTED_SENSORS)}")

    for sensor_id, values in per_sensor.items():
        if not values["min"] <= values["mean"] <= values["max"]:
            raise SmokeFailure(f"{sensor_id}: min/mean/max are inconsistent: {values}")
        if values["stddev"] < 0:
            raise SmokeFailure(f"{sensor_id}: negative stddev {values['stddev']}")
        if values["count"] != 50:
            raise SmokeFailure(f"{sensor_id}: expected 50 samples, got {values['count']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--expect-version", default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    checks = (
        ("health", lambda: check_health(args.endpoint, args.timeout, args.expect_version)),
        ("readings", lambda: check_readings(args.endpoint)),
        ("stats", lambda: check_stats(args.endpoint)),
    )

    print(f"smoke testing {args.endpoint}")
    failures = 0
    for name, check in checks:
        try:
            result = check()
        except SmokeFailure as exc:
            print(f"  FAIL  {name}: {exc}")
            failures += 1
        else:
            detail = f" ({result})" if isinstance(result, str) else ""
            print(f"  ok    {name}{detail}")

    if failures:
        print(f"\n{failures} check(s) failed")
        return 1

    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
