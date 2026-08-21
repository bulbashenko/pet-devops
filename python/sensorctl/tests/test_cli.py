"""Unit tests for the CLI layer, exercised through Typer's runner."""

from __future__ import annotations

import json

import httpx
import respx
from typer.testing import CliRunner

from sensorctl.cli import app

ENDPOINT = "http://sensor-hub.test:8080"
runner = CliRunner()


@respx.mock
def test_status_prints_version() -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(
        return_value=httpx.Response(200, json={"status": "ok", "version": "1.2.3"})
    )

    result = runner.invoke(app, ["status", "--endpoint", ENDPOINT])

    assert result.exit_code == 0
    assert "1.2.3" in result.stdout


@respx.mock
def test_status_json_output_is_parseable() -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(
        return_value=httpx.Response(200, json={"status": "ok", "version": "1.2.3"})
    )

    result = runner.invoke(app, ["status", "--endpoint", ENDPOINT, "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"status": "ok", "version": "1.2.3"}


@respx.mock
def test_read_renders_a_row_per_reading() -> None:
    respx.get(f"{ENDPOINT}/api/v1/readings").mock(
        return_value=httpx.Response(
            200,
            json={
                "count": 1,
                "readings": [
                    {"sensor_id": "temp-01", "timestamp_ms": 1000, "value": 21.5, "unit": "C"}
                ],
            },
        )
    )

    result = runner.invoke(app, ["read", "--endpoint", ENDPOINT, "-n", "1"])

    assert result.exit_code == 0
    assert "temp-01" in result.stdout
    assert "21.500" in result.stdout


@respx.mock
def test_stats_renders_per_sensor_rows() -> None:
    respx.get(f"{ENDPOINT}/api/v1/stats").mock(
        return_value=httpx.Response(
            200,
            json={
                "overall": {"count": 2, "min": 1.0, "max": 3.0, "mean": 2.0, "stddev": 1.0},
                "per_sensor": {
                    "temp-01": {"count": 2, "min": 1.0, "max": 3.0, "mean": 2.0, "stddev": 1.0}
                },
            },
        )
    )

    result = runner.invoke(app, ["stats", "--endpoint", ENDPOINT])

    assert result.exit_code == 0
    assert "temp-01" in result.stdout


@respx.mock
def test_unreachable_daemon_exits_nonzero() -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(side_effect=httpx.ConnectError("refused"))

    result = runner.invoke(app, ["status", "--endpoint", ENDPOINT])

    assert result.exit_code == 1


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip()
