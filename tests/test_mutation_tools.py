"""Choosing the mutation tool by capability (language, runner, build), and StrykerJS run on a copy of a state.

The StrykerJS integration test drives the real tool installed in tests/fixtures/js-stryker (``npm ci`` there); without
it the test skips, and with ASSERTIVA_REQUIRE_MUTATION=1 it fails instead.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters import stryker
from assertiva.adapters.mutation import mutation_tools, run_mutation_tool
from assertiva.workspace import link_installed, tree_fingerprint

from conftest import write

JS = Path(__file__).parent / "fixtures" / "js-stryker"


def _js_project(root: Path, runner: str = "jest") -> Path:
    write(root / "package.json", json.dumps({"devDependencies": {runner: "1.0.0"}}))
    write(root / "src" / "a.js", "module.exports = (a, b) => a + b;\n")
    write(root / "src" / "a.test.js", "test('a', () => {})\n")
    return root


def test_no_applicable_tool_is_an_explained_error_never_a_result(tmp_path):
    write(tmp_path / "go.mod", "module example.com/a\n")
    run = run_mutation_tool(tmp_path, sys.executable, ["a.go"])
    assert run.error and "no integrated mutation tool applies" in run.error and not run.mutants and not run.counts


def test_an_applicable_tool_that_is_not_installed_blocks_and_is_never_installed(tmp_path):
    run = run_mutation_tool(_js_project(tmp_path, "vitest"), sys.executable, ["src/a.js"])
    assert run.tool == stryker.TOOL and "not installed" in run.error and "does not install" in run.error
    assert not (tmp_path / "node_modules").exists() and run.counts == {}


def test_a_tool_that_does_not_apply_is_refused_even_when_named(tmp_path):
    run = run_mutation_tool(_js_project(tmp_path), sys.executable, ["src/a.js"], tool="cosmic-ray")
    assert "no integrated mutation tool applies" in run.error and "no Python tests" in run.error
    assert "unknown mutation tool" in run_mutation_tool(tmp_path, sys.executable, ["src/a.js"], tool="mutmut").error


def test_several_applicable_tools_need_the_users_choice_and_only_one_runs(tmp_path, monkeypatch):
    _js_project(tmp_path)
    write(tmp_path / "calc.py", "def add(a, b):\n    return a + b\n")
    write(tmp_path / "tests" / "test_calc.py", "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n")
    options = {o["tool"]: o for o in mutation_tools(tmp_path, sys.executable)}
    assert options["cosmic-ray"]["applies"] and options["stryker"]["applies"]
    assert "choose one with --mutation-tool" in run_mutation_tool(tmp_path, sys.executable, ["calc.py"]).error
    ran = []
    monkeypatch.setattr(stryker, "run", lambda *a, **k: ran.append("stryker"))
    from assertiva.adapters import cosmic_ray
    from assertiva.models import MutationRun

    monkeypatch.setattr(cosmic_ray, "run", lambda root, python, targets, test_paths, runner: ran.append(runner) or MutationRun(source="x"))
    monkeypatch.setattr("assertiva.process.module_available", lambda python, module: True)
    run = run_mutation_tool(tmp_path, sys.executable, ["calc.py"], tool="cosmic-ray")
    assert ran == ["pytest-native"] and run.config["selected"] == "cosmic-ray" and "named by the user" in run.config["selected_because"]


def test_cosmic_ray_runs_the_declared_runner_never_a_substitute(tmp_path, monkeypatch):
    write(tmp_path / "calc.py", "def add(a, b):\n    return a + b\n")
    write(tmp_path / "test_calc.py", "import unittest\nfrom calc import add\n\n"
                                     "class T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")
    write(tmp_path / ".assertiva.toml", '[tests]\nrunners = ["unittest"]\n')
    [option] = [o for o in mutation_tools(tmp_path, sys.executable) if o["tool"] == "cosmic-ray"]
    assert option["applies"] and option["runner"] == "unittest"
    write(tmp_path / ".assertiva.toml", '[tests]\nrunners = ["unittest", "pytest"]\n')
    [option] = [o for o in mutation_tools(tmp_path, sys.executable) if o["tool"] == "cosmic-ray"]
    assert option["runner"] is None and "several Python runners" in option["blocked"]


def _stryker_ready() -> None:
    reason = stryker.availability(JS)
    if reason:
        if os.environ.get("ASSERTIVA_REQUIRE_MUTATION"):
            pytest.fail(reason)
        pytest.skip(f"{reason} (run npm ci in tests/fixtures/js-stryker)")


def _run(capsys, *args) -> dict:
    capsys.readouterr()
    cli.main([*args, "--output", "json"])
    return json.loads(capsys.readouterr().out)


@pytest.mark.integration
def test_stryker_proves_the_protection_a_strengthened_jest_test_adds(tmp_path, capsys):
    _stryker_ready()
    root = tmp_path / "project"
    shutil.copytree(JS, root, ignore=shutil.ignore_patterns("node_modules", "strengthened"))
    link_installed(root, JS, ["node_modules"])  # the project's installed tools, as a developer has them
    before = tree_fingerprint(root)

    audit = _run(capsys, "audit", str(root), "--execute", "--mutate", "src/pricing.js")
    [run] = audit["states"]["current"]["mutation"]
    assert run["error"] is None and run["tool"] == "StrykerJS" and run["matches_state"] is True
    assert run["counts"].get("SURVIVED", 0) > 0 and run["killers_complete"] is True
    assert run["config"]["selected"] == "stryker" and run["config"]["test_runner"] == "jest"

    workspace = Path(_run(capsys, "improve", str(root))["candidate_workspace"])
    shutil.copy(JS / "strengthened" / "pricing.test.js", workspace / "src" / "pricing.test.js")
    report = _run(capsys, "improve", str(root), "--mutate", "src/pricing.js")
    protection = report["candidate_qualification"]["protection"]
    gained = [e for e in protection["gained"] if e["kind"] == "mutant"]
    assert len(gained) >= 3 and protection["lost"] == []
    assert all(e["attribution"] == "TEST" and e["detected_by"] for e in gained)
    assert any("the threshold is inclusive (src/pricing.test.js)" in e["detected_by"] for e in gained)

    cli.main(["improve", str(root), "--discard"])
    assert tree_fingerprint(root) == before


@pytest.mark.integration
def test_cosmic_ray_mutates_under_the_projects_unittest_runner(tmp_path):
    import subprocess

    python = os.environ.get("ASSERTIVA_MUTATION_PYTHON") or sys.executable
    if subprocess.run([python, "-c", "import cosmic_ray"], capture_output=True).returncode != 0:
        if os.environ.get("ASSERTIVA_REQUIRE_MUTATION"):
            pytest.fail("needs an interpreter with cosmic-ray (this one, or ASSERTIVA_MUTATION_PYTHON)")
        pytest.skip("needs an interpreter with cosmic-ray (this one, or ASSERTIVA_MUTATION_PYTHON)")
    write(tmp_path / "calc.py", "def add(a, b):\n    return a + b\n")
    write(tmp_path / "test_calc.py", "import unittest\nfrom calc import add\n\n"
                                     "class T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")
    write(tmp_path / ".assertiva.toml", '[tests]\nrunners = ["unittest"]\n')
    run = run_mutation_tool(tmp_path, python, ["calc.py"])
    assert run.error is None and run.config["runner"] == "unittest" and run.config["test_command"][:2] == ["-m", "unittest"]
    assert run.counts.get("KILLED", 0) > 0 and "test_calc.py" in run.test_sources


def test_a_copy_that_cannot_be_made_is_an_explained_error_not_a_crash(tmp_path, monkeypatch):
    _js_project(tmp_path)
    monkeypatch.setattr("assertiva.adapters.mutation.mutation_tools", lambda *a: [
        {"tool": "stryker", "name": stryker.TOOL, "applies": True, "blocked": None, "runner": "jest", "why": "jest"}])

    def too_long(*args, **kwargs):
        raise FileNotFoundError(3, "path not found")

    monkeypatch.setattr(stryker, "run", too_long)
    run = run_mutation_tool(tmp_path, sys.executable, ["src/a.js"])
    assert "could not use a copy" in run.error and run.counts == {} and run.orchestrated
