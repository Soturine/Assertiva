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
