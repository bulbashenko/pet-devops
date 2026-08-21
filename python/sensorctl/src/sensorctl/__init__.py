"""sensorctl — command line client for the sensor-hub daemon."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sensorctl")
except PackageNotFoundError:  # pragma: no cover - only hit in a source checkout
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
