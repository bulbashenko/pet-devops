"""Command line interface for sensor-hub."""

from __future__ import annotations

import json
import sys
from typing import Annotated, Optional

import typer

from sensorctl import __version__
from sensorctl.client import DEFAULT_ENDPOINT, SensorHubClient, SensorHubError

app = typer.Typer(
    add_completion=False,
    help="Query a sensor-hub daemon.",
    no_args_is_help=True,
)

EndpointOption = Annotated[
    str,
    typer.Option("--endpoint", "-e", envvar="SENSOR_HUB_ENDPOINT", help="sensor-hub base URL."),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Emit raw JSON instead of a table.")]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = None,
) -> None:
    """sensorctl — control and inspect a sensor-hub instance."""


def _client(endpoint: str) -> SensorHubClient:
    return SensorHubClient(endpoint)


def _fail(exc: SensorHubError) -> None:
    typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@app.command()
def status(endpoint: EndpointOption = DEFAULT_ENDPOINT, as_json: JsonOption = False) -> None:
    """Check daemon health and report its version."""
    try:
        with _client(endpoint) as client:
            payload = client.health()
    except SensorHubError as exc:
        _fail(exc)
        return

    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.secho(f"status : {payload.get('status', 'unknown')}", fg=typer.colors.GREEN)
    typer.echo(f"version: {payload.get('version', 'unknown')}")
    typer.echo(f"endpoint: {endpoint}")


@app.command()
def read(
    count: Annotated[int, typer.Option("--count", "-n", min=1, max=1000)] = 10,
    endpoint: EndpointOption = DEFAULT_ENDPOINT,
    as_json: JsonOption = False,
) -> None:
    """Fetch the most recent readings."""
    try:
        with _client(endpoint) as client:
            readings = client.readings(count)
    except SensorHubError as exc:
        _fail(exc)
        return

    if as_json:
        typer.echo(json.dumps([reading.__dict__ for reading in readings], indent=2))
        return

    typer.echo(f"{'SENSOR':<18}{'TIMESTAMP(ms)':>16}{'VALUE':>12}  UNIT")
    for reading in readings:
        typer.echo(
            f"{reading.sensor_id:<18}{reading.timestamp_ms:>16}{reading.value:>12.3f}  {reading.unit}"
        )


@app.command()
def stats(
    count: Annotated[int, typer.Option("--count", "-n", min=1, max=1000)] = 100,
    endpoint: EndpointOption = DEFAULT_ENDPOINT,
    as_json: JsonOption = False,
) -> None:
    """Aggregate readings and print per-sensor statistics."""
    try:
        with _client(endpoint) as client:
            payload = client.stats(count)
    except SensorHubError as exc:
        _fail(exc)
        return

    if as_json:
        typer.echo(json.dumps(payload, indent=2))
        return

    typer.echo(f"{'SENSOR':<18}{'COUNT':>7}{'MIN':>10}{'MEAN':>10}{'MAX':>10}{'STDDEV':>10}")
    for sensor_id, values in sorted(payload.get("per_sensor", {}).items()):
        typer.echo(
            f"{sensor_id:<18}{values['count']:>7}{values['min']:>10.3f}"
            f"{values['mean']:>10.3f}{values['max']:>10.3f}{values['stddev']:>10.3f}"
        )


def run() -> None:
    """Console-script entry point."""
    try:
        app()
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        sys.exit(130)


if __name__ == "__main__":  # pragma: no cover
    run()
