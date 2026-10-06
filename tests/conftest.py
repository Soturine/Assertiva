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


FAST_LIMIT_S = 2.0
SLOW_MARKERS = {"integration", "artifact"}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Keep the fast suite fast: an unmarked test that runs long must declare what it is.

    Applies to fast-suite runs (``-m "not integration and not artifact"``), sequentially, so
    parallel full runs are never failed by CPU contention. Setup time counts: heavy work in a
    fixture is still heavy.
    """
    outcome = yield
    report = outcome.get_result()
    if "not integration" not in (item.config.option.markexpr or ""):
        return
    elapsed = getattr(item, "_assertiva_elapsed", 0.0) + call.duration
    item._assertiva_elapsed = elapsed
    if report.when == "call" and report.passed and elapsed > FAST_LIMIT_S:
        if not SLOW_MARKERS & {mark.name for mark in item.iter_markers()}:
            report.outcome = "failed"
            report.longrepr = (
                f"{item.nodeid} took {elapsed:.1f}s (setup + call) without an 'integration' or 'artifact' marker; "
                "mark it (it still runs in the full suite) or make it fast"
            )
