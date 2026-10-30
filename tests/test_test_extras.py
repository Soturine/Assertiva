"""AX-E06: an interpreter without the project's declared test extras is BLOCKED with the extra named; never a project
failure, never installed by Assertiva."""

import sys

import pytest

from assertiva.adapters.pytest_native import PytestNativeAdapter, declared_test_extras

from conftest import write

PYPROJECT = """[project]
name = "ledger"
version = "0.1"
dependencies = ["pyyaml"]

[project.optional-dependencies]
dev = ["pytest>=8", "hypothesis"]
docs = ["mkdocs"]

[dependency-groups]
test = ["pytest-cov", "pytest"]
"""


def test_declared_test_extras_are_read_from_optional_dependencies_and_groups(tmp_path):
    write(tmp_path / "pyproject.toml", PYPROJECT)
    assert declared_test_extras(tmp_path) == ["dev", "test"]


def test_an_interpreter_without_pytest_is_blocked_with_the_extra_named(tmp_path, monkeypatch):
    write(tmp_path / "pyproject.toml", PYPROJECT)
    write(tmp_path / "tests" / "test_x.py", "def test_x():\n    assert True\n")
    monkeypatch.setattr("assertiva.adapters.pytest_native.module_available", lambda python, module: module != "pytest")
    run = PytestNativeAdapter(python=sys.executable).run(tmp_path)
    assert run.status.value == "BLOCKED" and not run.invocations
    assert "[dev]" in run.limitations[0] and "installs nothing" in run.limitations[0]
    assert run.metadata["missing_test_dependency"] == "pytest"


@pytest.mark.integration
def test_with_pytest_available_the_preflight_changes_nothing(tmp_path):
    write(tmp_path / "pyproject.toml", PYPROJECT)
    write(tmp_path / "tests" / "test_x.py", "def test_x():\n    assert True\n")
    assert PytestNativeAdapter(python=sys.executable).run(tmp_path).status.value == "PASS"
