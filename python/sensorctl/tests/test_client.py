"""Unit tests for the sensor-hub HTTP client — no daemon required."""

from __future__ import annotations

import httpx
import pytest
import respx

from sensorctl.client import Reading, SensorHubClient, SensorHubError

ENDPOINT = "http://sensor-hub.test:8080"


@pytest.fixture
def client() -> SensorHubClient:
    with SensorHubClient(ENDPOINT) as instance:
        yield instance


@respx.mock
def test_health_returns_payload(client: SensorHubClient) -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(
        return_value=httpx.Response(200, json={"status": "ok", "version": "1.2.3"})
    )

    assert client.health() == {"status": "ok", "version": "1.2.3"}


@respx.mock
def test_readings_are_parsed_into_dataclasses(client: SensorHubClient) -> None:
    respx.get(f"{ENDPOINT}/api/v1/readings").mock(
        return_value=httpx.Response(
            200,
            json={
                "count": 2,
                "readings": [
                    {"sensor_id": "temp-01", "timestamp_ms": 1000, "value": 21.5, "unit": "C"},
                    {"sensor_id": "temp-01", "timestamp_ms": 1100, "value": 22.0, "unit": "C"},
                ],
            },
        )
    )

    readings = client.readings(2)

    assert readings == [
        Reading("temp-01", 1000, 21.5, "C"),
        Reading("temp-01", 1100, 22.0, "C"),
    ]


@respx.mock
def test_readings_passes_count_as_query_param(client: SensorHubClient) -> None:
    route = respx.get(f"{ENDPOINT}/api/v1/readings").mock(
        return_value=httpx.Response(200, json={"count": 0, "readings": []})
    )

    client.readings(37)

    assert route.calls.last.request.url.params["n"] == "37"


@respx.mock
def test_trailing_slash_in_endpoint_is_normalised() -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(return_value=httpx.Response(200, json={"status": "ok"}))

    with SensorHubClient(f"{ENDPOINT}/") as client:
        assert client.health()["status"] == "ok"


@respx.mock
def test_error_status_raises(client: SensorHubClient) -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(return_value=httpx.Response(503))

    with pytest.raises(SensorHubError, match="HTTP 503"):
        client.health()


@respx.mock
def test_connection_failure_raises(client: SensorHubClient) -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(side_effect=httpx.ConnectError("refused"))

    with pytest.raises(SensorHubError, match="cannot reach sensor-hub"):
        client.health()


@respx.mock
def test_non_json_body_raises(client: SensorHubClient) -> None:
    respx.get(f"{ENDPOINT}/healthz").mock(return_value=httpx.Response(200, text="<html>nope"))

    with pytest.raises(SensorHubError, match="non-JSON"):
        client.health()
