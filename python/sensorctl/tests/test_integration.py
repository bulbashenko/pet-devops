"""Integration test: run the real CLI against a real sensor-hub container.

Skipped automatically when no container runtime or no image is available, so the
unit suite stays runnable on a bare checkout. CI runs it explicitly after the
image build step (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid

import httpx
import pytest

from sensorctl.client import SensorHubClient

IMAGE = os.environ.get("SENSOR_HUB_IMAGE", "sensor-hub:local")
RUNTIME = shutil.which("docker") or shutil.which("podman")

pytestmark = pytest.mark.integration


def _image_exists() -> bool:
    if RUNTIME is None:
        return False
    result = subprocess.run(
        [RUNTIME, "image", "inspect", IMAGE],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


requires_container = pytest.mark.skipif(
    not _image_exists(),
    reason=f"container runtime or image {IMAGE} unavailable",
)


@pytest.fixture(scope="module")
def sensor_hub() -> str:
    """Starts sensor-hub on a random host port and yields its endpoint."""
    name = f"sensor-hub-it-{uuid.uuid4().hex[:8]}"
    # An empty host port asks for a free one. `-p 0:8080` means the same thing
    # to Docker but podman rejects it, and this form works on both.
    subprocess.run(
        [RUNTIME, "run", "-d", "--rm", "--name", name, "-p", "127.0.0.1::8080", IMAGE],
        check=True,
        capture_output=True,
    )
    try:
        port = (
            subprocess.run(
                [RUNTIME, "port", name, "8080/tcp"],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .rsplit(":", 1)[-1]
        )

        endpoint = f"http://127.0.0.1:{port}"
        _wait_until_healthy(endpoint)
        yield endpoint
    finally:
        subprocess.run([RUNTIME, "rm", "-f", name], check=False, capture_output=True)


def _wait_until_healthy(endpoint: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{endpoint}/healthz", timeout=1.0)
            if response.status_code == httpx.codes.OK:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.5)
    raise TimeoutError(f"sensor-hub did not become healthy at {endpoint}: {last_error}")


@requires_container
def test_health_reports_ok(sensor_hub: str) -> None:
    with SensorHubClient(sensor_hub) as client:
        payload = client.health()

    assert payload["status"] == "ok"
    assert payload["version"]


@requires_container
def test_readings_honour_requested_count(sensor_hub: str) -> None:
    with SensorHubClient(sensor_hub) as client:
        readings = client.readings(5)

    # Three default channels, five samples each.
    assert len(readings) == 15
    assert {reading.sensor_id for reading in readings} == {
        "temp-01",
        "humidity-01",
        "imu-01-accel-z",
    }


@requires_container
def test_stats_are_internally_consistent(sensor_hub: str) -> None:
    with SensorHubClient(sensor_hub) as client:
        payload = client.stats(50)

    for values in payload["per_sensor"].values():
        assert values["min"] <= values["mean"] <= values["max"]
        assert values["stddev"] >= 0.0


@requires_container
def test_cli_binary_talks_to_the_daemon(sensor_hub: str) -> None:
    result = subprocess.run(
        ["sensorctl", "stats", "--endpoint", sensor_hub, "--json", "-n", "20"],
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["overall"]["count"] == 60
