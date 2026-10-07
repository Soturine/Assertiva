"""Assertiva deterministic assurance primitives."""

import re
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .pytest_audit import audit_pytest_project, discover_pytest_definitions


def _checkout_version() -> str | None:
    """The version declared by the source checkout this package is imported from, if any.

    Installed metadata is written at install time, so an editable install keeps reporting the old version after
    pyproject.toml is bumped. The version that describes the running code is the checkout's own declaration.
    """
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("project") or {}
    except (OSError, tomllib.TOMLDecodeError):
        return None
    if project.get("name") != "assertiva" or not isinstance(project.get("version"), str):
        return None
    return project["version"] if re.fullmatch(r"[\w.+-]+", project["version"]) else None


def _installed_version() -> str | None:
    try:
        return version("assertiva")
    except PackageNotFoundError:
        return None


__version__ = _checkout_version() or _installed_version() or "unknown"

__all__ = ["audit_pytest_project", "discover_pytest_definitions", "__version__"]
