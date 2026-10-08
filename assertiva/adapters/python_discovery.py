"""Which files a Python test runner would look at, from the project's own discovery configuration (static).

pytest: `testpaths` (glob patterns from the rootdir), `python_files` and `norecursedirs` from pytest.ini,
pyproject.toml (`[tool.pytest.ini_options]` or `[tool.pytest]`), tox.ini or setup.cfg (first file that has a
pytest section wins, as pytest does), with pytest's defaults otherwise; virtual environments are never
recursed into. A file found here is a candidate, not a collected test: native collection is authoritative.
"""

from __future__ import annotations

import configparser
import fnmatch
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_FILES = ("test_*.py", "*_test.py")
DEFAULT_NORECURSE = ("*.egg", ".*", "_darcs", "build", "CVS", "dist", "node_modules", "venv", "{arch}")


@dataclass(frozen=True)
class DiscoveryConfig:
    testpaths: tuple[str, ...] = ()
    python_files: tuple[str, ...] = DEFAULT_FILES
    norecursedirs: tuple[str, ...] = DEFAULT_NORECURSE
    source: str | None = None


def _split(value) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(v) for v in value)
    return tuple(str(value or "").split())


def _from_mapping(options: dict, source: str) -> DiscoveryConfig:
    return DiscoveryConfig(
        testpaths=_split(options.get("testpaths", ())),
        python_files=_split(options["python_files"]) if "python_files" in options else DEFAULT_FILES,
        norecursedirs=_split(options["norecursedirs"]) if "norecursedirs" in options else DEFAULT_NORECURSE,
        source=source,
    )


def _ini(path: Path, section: str) -> dict | None:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(path.read_text(encoding="utf-8", errors="replace"))
    except configparser.Error:
        return None
    return dict(parser[section]) if parser.has_section(section) else None


def discovery_config(root: str | Path) -> DiscoveryConfig:
    root = Path(root)
    for name, section in (("pytest.ini", "pytest"), (".pytest.ini", "pytest")):
        if (root / name).is_file():
            return _from_mapping(_ini(root / name, section) or {}, name)
    if (root / "pyproject.toml").is_file():
        try:
            tool = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")).get("tool", {}).get("pytest")
        except (OSError, tomllib.TOMLDecodeError):
            tool = None
        if isinstance(tool, dict):
            options = tool.get("ini_options") if isinstance(tool.get("ini_options"), dict) else tool
            return _from_mapping(options, "pyproject.toml")
    for name, section in (("tox.ini", "pytest"), ("setup.cfg", "tool:pytest")):
        if (root / name).is_file() and (options := _ini(root / name, section)) is not None:
            return _from_mapping(options, name)
    return DiscoveryConfig()


def _is_venv(path: Path) -> bool:
    return (path / "pyvenv.cfg").is_file() or (path / "conda-meta" / "history").is_file()


def test_files(root: str | Path, config: DiscoveryConfig | None = None) -> list[Path]:
    """Files whose names match the runner's file patterns, under its configured start paths."""
    root = Path(root)
    config = config or discovery_config(root)
    starts = [p for pattern in config.testpaths for p in sorted(root.glob(pattern))] if config.testpaths else [root]
    found: set[Path] = set()
    for start in starts:
        if start.is_file():
            found.add(start)
            continue
        for current, dirs, files in os.walk(start):
            here = Path(current)
            dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, p) for p in config.norecursedirs) and not _is_venv(here / d)]
            found.update(here / f for f in files if f.endswith(".py") and any(fnmatch.fnmatch(f, p) for p in config.python_files))
    return sorted(p for p in found if root in p.parents or p.parent == root)
