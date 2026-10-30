"""AG-11: targeted mutation. The auditor names the tests that claim the target's behavior; the baseline qualifies those
tests, each mutant runs only them, and the run records the selection and never claims the whole suite."""

import os
import subprocess
import sys

import pytest

from assertiva import cli
from assertiva.adapters import stryker
from assertiva.adapters.mutation import run_mutation_tool

from conftest import write


def project(root):
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "test_calc.py", "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n\n"
                                           "def test_add_negative():\n    assert add(-1, -2) == -3\n")
    write(root / "tests" / "test_other.py", "def test_unrelated_preexisting_failure():\n    assert False\n")
    return root


def test_mutate_tests_without_mutate_is_refused(tmp_path, capsys):
    assert cli.main(["audit", str(project(tmp_path / "p")), "--execute", "--mutate-tests", "tests/test_calc.py"]) == 2
    assert "--mutate" in capsys.readouterr().err


def test_a_tool_that_cannot_select_tests_refuses_the_selection(tmp_path, monkeypatch):
    monkeypatch.setattr("assertiva.adapters.mutation.mutation_tools", lambda *a: [
        {"tool": "stryker", "name": stryker.TOOL, "applies": True, "blocked": None, "runner": "jest", "why": "jest"}])
    run = run_mutation_tool(tmp_path, sys.executable, ["src/a.js"], tests=["src/a.test.js"])
    assert "cannot be limited to selected tests" in run.error and not run.mutants


@pytest.mark.parametrize("test_path", ["../outside", "/etc/passwd", "tests/missing.py"])
def test_selected_tests_must_be_inside_the_project(tmp_path, monkeypatch, test_path):
    project(tmp_path)
    monkeypatch.setattr("assertiva.adapters.cosmic_ray.module_available", lambda python, module: True)
    run = run_mutation_tool(tmp_path, sys.executable, ["calc.py"], tests=[test_path])
    assert run.error and "selected tests must be" in run.error


def _mutation_python():
    python = os.environ.get("ASSERTIVA_MUTATION_PYTHON") or sys.executable
    if subprocess.run([python, "-c", "import cosmic_ray"], capture_output=True).returncode != 0:
        if os.environ.get("ASSERTIVA_REQUIRE_MUTATION"):
            pytest.fail("needs an interpreter with cosmic-ray (this one, or ASSERTIVA_MUTATION_PYTHON)")
        pytest.skip("needs an interpreter with cosmic-ray (this one, or ASSERTIVA_MUTATION_PYTHON)")
    return python


@pytest.mark.integration
def test_an_unrelated_failure_refuses_the_whole_suite_run_but_not_the_named_tests(tmp_path):
    python = _mutation_python()
    root = project(tmp_path)
    whole = run_mutation_tool(root, python, ["calc.py"])
    assert whole.error and "the tests do not pass" in whole.error  # the default stays: the whole suite must be green
    selected = run_mutation_tool(root, python, ["calc.py"], tests=["tests/test_calc.py"])
    assert selected.error is None, selected.error
    assert selected.counts.get("KILLED", 0) > 0
    assert selected.config["test_selection"]["tests"] == ["tests/test_calc.py"]
    assert selected.config["test_selection"]["whole_suite"] == "NOT_RUN"
    assert any("only the selected tests ran" in limitation for limitation in selected.limitations)
