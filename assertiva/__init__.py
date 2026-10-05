"""Assertiva deterministic assurance primitives."""

from importlib.metadata import PackageNotFoundError, version

from .pytest_audit import audit_pytest_project, discover_pytest_definitions

try:
    __version__ = version("assertiva")
except PackageNotFoundError:  # running from a source tree
    __version__ = "source"

__all__ = ["audit_pytest_project", "discover_pytest_definitions", "__version__"]
