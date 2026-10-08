import subprocess
from pathlib import Path

import pytest


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def commit_all(root: Path) -> None:
    """Make ``root`` a Git repository with everything committed (fixture copies of real projects)."""
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture")


@pytest.fixture(autouse=True)
def assertiva_home(tmp_path, monkeypatch):
    """Keep Assertiva-owned state out of the real home directory during tests."""
    home = tmp_path / "assertiva-home"
    monkeypatch.setenv("ASSERTIVA_HOME", str(home))
    return home


@pytest.fixture
def calc_project(tmp_path):
    """Small generic project: one behavior, one weak test, one strong test."""
    root = tmp_path / "project"
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(
        root / "tests" / "test_calc.py",
        "from calc import add\n\n"
        "def test_add_runs():\n    assert add(1, 2) is not None\n\n"
        "def test_add_value():\n    assert add(2, 2) == 4\n",
    )
    write(root / "conftest.py", "")
    return root


@pytest.fixture
def git_calc_project(calc_project):
    git(calc_project, "init", "-q")
    git(calc_project, "add", "-A")
    git(calc_project, "commit", "-q", "-m", "baseline")
    return calc_project


SLOW_REPORT_S = 2.0
SLOW_MARKERS = {"integration", "artifact"}
_SLOW: list[tuple[float, str]] = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Record unmarked tests that run long in the fast suite. Time is evidence, never a test failure."""
    outcome = yield
    outcome.get_result()
    if "not integration" not in (item.config.option.markexpr or ""):
        return
    elapsed = getattr(item, "_assertiva_elapsed", 0.0) + call.duration
    item._assertiva_elapsed = elapsed
    if call.when == "call" and elapsed > SLOW_REPORT_S and not SLOW_MARKERS & {m.name for m in item.iter_markers()}:
        _SLOW.append((elapsed, item.nodeid))


def pytest_terminal_summary(terminalreporter):
    if _SLOW:
        terminalreporter.write_line(f"unmarked tests slower than {SLOW_REPORT_S:.0f}s in the fast suite (mark them or make them fast):")
        for elapsed, nodeid in sorted(_SLOW, reverse=True)[:10]:
            terminalreporter.write_line(f"  {elapsed:.1f}s {nodeid}")
