"""Unofficial tool for querying MEP teaching vacancies and appointments."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("consulta-vacantes-mep")
except PackageNotFoundError:  # pragma: no cover
    # The package is being run from source without being installed.
    __version__ = "0.0.0.dev0"

__all__ = ["__version__"]
