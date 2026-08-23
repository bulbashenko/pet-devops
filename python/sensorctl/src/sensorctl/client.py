"""HTTP client for the sensor-hub daemon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_ENDPOINT = "http://127.0.0.1:8080"
DEFAULT_TIMEOUT = 5.0


class SensorHubError(RuntimeError):
    """Raised when the daemon is unreachable or answers with an error status."""


@dataclass(frozen=True)
class Reading:
    sensor_id: str
    timestamp_ms: int
    value: float
    unit: str

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Reading:
        return cls(
            sensor_id=payload["sensor_id"],
            timestamp_ms=int(payload["timestamp_ms"]),
            value=float(payload["value"]),
            unit=payload["unit"],
        )


class SensorHubClient:
    """Thin wrapper over the daemon's REST API.

    Kept deliberately small: the CLI layer does formatting, this layer only
    speaks HTTP, which is what makes it testable without a running daemon.
    """

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    def __enter__(self) -> SensorHubClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self._timeout)
        return self._client

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        try:
            response = self.client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise SensorHubError(f"cannot reach sensor-hub at {url}: {exc}") from exc

        if response.status_code != httpx.codes.OK:
            raise SensorHubError(f"{url} returned HTTP {response.status_code}")

        try:
            return response.json()
        except ValueError as exc:
            raise SensorHubError(f"{url} returned a non-JSON body") from exc

    def health(self) -> dict[str, Any]:
        return self._get("/healthz")

    def readings(self, count: int = 10) -> list[Reading]:
        payload = self._get("/api/v1/readings", {"n": count})
        return [Reading.from_json(item) for item in payload.get("readings", [])]

    def stats(self, count: int = 100) -> dict[str, Any]:
        return self._get("/api/v1/stats", {"n": count})
