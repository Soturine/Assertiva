"""TCC-A11: nested package scripts form a graph; a script CI reaches twice runs twice (cost, not new evidence)."""

import json

from assertiva.adapters.package_scripts import script_graph
from assertiva.verification import discover_surface, surface_findings

from conftest import write

SCRIPTS = {"test": "npm run test:unit && npm run test:integration", "test:unit": "node --test test/unit",
           "test:integration": "npm run test:mqtt && node --test test/integration", "test:mqtt": "node --test test/mqtt",
           "loop:a": "npm run loop:b", "loop:b": "npm run loop:a", "lint": "eslint ."}


def test_the_graph_has_direct_calls_and_transitive_reach_and_stops_on_cycles():
    graph = script_graph(SCRIPTS)
    assert graph["test"]["calls"] == ["test:unit", "test:integration"]
    assert graph["test"]["reaches"] == ["test:unit", "test:integration", "test:mqtt"]
    assert graph["loop:a"]["reaches"] == ["loop:b"] and graph["lint"] == {"calls": [], "reaches": []}


def project(root, steps):
    write(root / "package.json", json.dumps({"name": "app", "scripts": SCRIPTS}))
    write(root / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n" + steps)
    return root


def repetition(root):
    return next((f for f in surface_findings(discover_surface(root)) if f.code == "NESTED_SCRIPT_REPETITION"), None)


def test_ci_running_a_parent_and_its_child_repeats_the_shared_scripts(tmp_path):
    found = repetition(project(tmp_path, "      - run: npm test\n      - run: npm run test:integration\n"))
    assert found is not None and found.severity == "info"
    assert set(found.evidence["repeated"]) == {"test:integration", "test:mqtt"}


def test_ci_running_disjoint_scripts_repeats_nothing(tmp_path):
    # negative control: two different gates are not repetition
    assert repetition(project(tmp_path, "      - run: npm test\n      - run: npm run lint\n")) is None


# --- Randomizer dogfood (AXR-03/05/06/08): CI that runs a package script that runs a repository script -----------

def _wrapped(root, wrapper="import subprocess, sys\nsys.exit(subprocess.call([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests']))\n",
             workflows=None):
    write(root / "package.json", json.dumps({"name": "app", "scripts": {"verify": "python tools/verify.py",
                                                                         "test:js": "vitest run", "loop": "npm run verify && npm run loop"}}))
    write(root / "tools" / "verify.py", wrapper)
    write(root / "src" / "mod.py", "def one():\n    return 1\n")
    write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_mod.py", "import unittest\nfrom src.mod import one\n\nclass T(unittest.TestCase):\n"
                                           "    def test_one(self):\n        self.assertEqual(one(), 1)\n")
    workflows = workflows or {"ci.yml": "on: push\n", "release.yml": "on:\n  push:\n    tags: ['v*']\n"}
    for name, trigger in workflows.items():
        write(root / ".github" / "workflows" / name,
              trigger + "jobs:\n  v:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npm ci\n      - run: npm run verify\n")
    return root


def test_a_ci_step_that_runs_a_local_script_covers_it(tmp_path):
    findings = surface_findings(discover_surface(_wrapped(tmp_path)))
    missing = next(f for f in findings if f.code == "LOCAL_CHECK_NOT_OBSERVED_IN_CI").evidence["checks"]
    assert missing == ["package-script:test:js"]  # verify runs in CI; vitest never does (the control stays reported)
    assert not any(f.code == "CI_ONLY_CHECK" for f in findings)  # the same npm run verify is also the local check


def test_the_same_script_in_workflows_of_different_events_is_not_repetition(tmp_path):
    assert repetition(_wrapped(tmp_path)) is None
    # control: two steps of one workflow running it are a repeat
    root = tmp_path / "same"
    _wrapped(root, workflows={"ci.yml": "on: push\n"})
    write(root / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  v:\n    runs-on: ubuntu-latest\n    steps:\n"
                                                     "      - run: npm run verify\n      - run: npm run verify\n")
    found = repetition(root)
    assert found is not None and "within one workflow file" in found.evidence["scope"]


def test_a_runner_behind_a_package_script_is_resolved_one_hop_and_cycles_stop(tmp_path):
    from assertiva.ci import scripts_running

    found = scripts_running(_wrapped(tmp_path), "unittest")
    assert {(s["script"], s.get("via_package_script")) for s in found} == {("tools/verify.py", "verify")}
    assert scripts_running(tmp_path, "pytest") == []  # it runs unittest, not pytest
    # control: a wrapper that only mentions the runner does not run it
    quiet = _wrapped(tmp_path / "quiet", wrapper="print('unittest')\n")
    assert scripts_running(quiet, "unittest") == []


def test_tests_run_through_a_package_script_are_not_reported_missing_from_ci(tmp_path, capsys):
    from assertiva import cli

    cli.main(["audit", str(_wrapped(tmp_path / "p")), "--output", "json", "--report-dir", str(tmp_path / "r")])
    codes = {f["code"]: f for f in json.loads(capsys.readouterr().out)["findings"]}
    assert "CI_PYTEST_NOT_OBSERVED" not in codes
    assert codes["CI_TESTS_RUN_THROUGH_SCRIPT"]["severity"] == "info"
    assert codes["CI_TESTS_RUN_THROUGH_SCRIPT"]["evidence"]["scripts"][0]["via_package_script"] == "verify"


def test_a_command_table_launched_through_a_variable_is_inferred_not_static():
    """Randomizer dogfood: tools/verify.py keeps `[python, "-m", "unittest", ...]` in a table and runs `subprocess.run(command)`."""
    from assertiva.ci import _python_script_basis

    table = ("import subprocess, sys\nSTEPS = [('unit', [sys.executable, '-m', 'unittest', 'discover'])]\n"
             "for name, command in STEPS:\n    subprocess.run(command)\n")
    assert _python_script_basis(table, "unittest") == "INFERRED"
    assert _python_script_basis(table, "pytest") is None
    direct = "import subprocess, sys\nsubprocess.run([sys.executable, '-m', 'pytest'])\n"
    assert _python_script_basis(direct, "pytest") == "STATIC"
    # controls: a table that is never launched, and a launcher whose lists do not name the runner
    assert _python_script_basis("STEPS = [['python', '-m', 'unittest']]\nprint(STEPS)\n", "unittest") is None
    assert _python_script_basis("import subprocess\nsubprocess.run(['node', 'x.mjs'])\nX = ['-m', 'other']\n", "unittest") is None


def test_a_local_check_that_may_run_inside_an_opaque_ci_script_is_not_a_high_gap(tmp_path):
    root = _wrapped(tmp_path / "opaque", workflows={"ci.yml": "on: push\n"})
    write(root / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  v:\n    runs-on: ubuntu-latest\n    steps:\n"
                                                     "      - run: npm run verify\n      - run: ./tools/custom-gate\n")
    found = next(f for f in surface_findings(discover_surface(root)) if f.code == "LOCAL_CHECK_NOT_OBSERVED_IN_CI")
    assert found.severity == "medium" and found.evidence["basis"].startswith("UNKNOWN") and found.evidence["may_run_inside"]
    # control: when every CI step is classified, the gap is shown and keeps its default severity
    plain = _wrapped(tmp_path / "plain", workflows={"ci.yml": "on: push\n"})
    write(plain / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  v:\n    runs-on: ubuntu-latest\n    steps:\n"
                                                      "      - run: npm ci\n      - run: python -m unittest discover -s tests\n")
    shown = next(f for f in surface_findings(discover_surface(plain)) if f.code == "LOCAL_CHECK_NOT_OBSERVED_IN_CI")
    assert shown.severity != "medium" and "may_run_inside" not in shown.evidence
