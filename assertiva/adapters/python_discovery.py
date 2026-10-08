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
    return pytest_config(root) or _unittest_discovery(root) or DiscoveryConfig()


def pytest_config(root: Path) -> DiscoveryConfig | None:
    """pytest's own configuration, from the first file that has a pytest section (None without one)."""
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
    return None


def _unittest_discovery(root: Path) -> DiscoveryConfig | None:
    """Without pytest configuration, a project whose only declared runners are unittest or Django finds test files
    by unittest's pattern (`test*.py`, or the declared `-p`). The whole tree stays in scope: a CI start directory
    (`-s tests`) is a CI scope, and tests outside it are a CI gap, not files to ignore."""
    declared = declared_runners(root)
    if not declared or set(declared) - {"unittest", "django"}:
        return None
    from .commands import classify_command

    patterns = []
    for command in declared.get("unittest", []):
        args = list(classify_command(command).runner_args)
        patterns += [args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-p", "--pattern")]
    return DiscoveryConfig(python_files=tuple(dict.fromkeys(patterns)) or ("test*.py",),
                           source="declared " + "/".join(sorted(declared)) + " discovery")


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


# --- which Python runner the project declares ----------------------------------------------
# One runner per declaration: the project's own CI/scripts decide (a unittest CI is reproduced with unittest,
# never assumed equivalent to pytest); pytest configuration also declares pytest; without any declaration a
# Django project (manage.py) uses its test command and anything else keeps pytest, which also runs TestCases.
_PYTEST_CONFIG = ("pytest.ini", ".pytest.ini", "conftest.py")


def django_manage(root: str | Path) -> Path | None:
    path = Path(root) / "manage.py"
    try:
        return path if path.is_file() and "django" in path.read_text(encoding="utf-8", errors="replace").lower() else None
    except OSError:
        return None


def pytest_configured(root: str | Path) -> bool:
    root = Path(root)
    if any((root / name).is_file() for name in _PYTEST_CONFIG) or (root / "tests" / "conftest.py").is_file():
        return True
    return pytest_config(root) is not None


def declared_runners(root: str | Path) -> dict[str, list[str]]:
    """Runner -> the declared commands (CI, hooks, scripts) that invoke it."""
    from assertiva.verification import discover_surface

    found: dict[str, list[str]] = {}
    for check in discover_surface(Path(root)).checks:
        tool = check.tool or ""
        runner = {"pytest": "pytest", "unittest": "unittest", "manage.py test": "django"}.get(tool)
        if runner and check.command:
            found.setdefault(runner, []).append(check.command)
    return found


def python_runners(root: str | Path) -> set[str]:
    root = Path(root)
    runners = set(declared_runners(root))
    if pytest_configured(root):
        runners.add("pytest")
    if runners:
        return runners
    return {"django"} if django_manage(root) else {"pytest"}
