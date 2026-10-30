"""AG-10 / AG-12: the caller sets the per-run limit without writing the audited project, and every run says which limit,
selection and duration it had, side by side with the artifact qualification of the same revision."""

import json
import sys

import pytest

from assertiva import cli
from assertiva.workspace import tree_fingerprint

from conftest import write


def run(capsys, *args):
    code = cli.main([*args, "--python", sys.executable, "--output", "json"])
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip() else None)


def slow_project(root, sleep_s, config=None):
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "test_calc.py",
          f"import time\nfrom calc import add\n\ndef test_add():\n    time.sleep({sleep_s})\n    assert add(2, 2) == 4\n")
    if config:
        write(root / ".assertiva.toml", config)
    return root


def native(report):
    return next(r for r in report["execution_manifest"]["runs"] if r["adapter"].startswith("pytest"))


@pytest.mark.parametrize("value", ["0", "-5", "abc", str(8 * 24 * 3600)])
def test_an_invalid_limit_is_refused_before_anything_runs(tmp_path, capsys, value):
    with pytest.raises(SystemExit) as exit_:
        cli.main(["audit", str(tmp_path), "--timeout-s", value])
    assert exit_.value.code == 2


@pytest.mark.integration
def test_the_command_line_limit_wins_and_is_recorded_without_touching_the_project(tmp_path, capsys, assertiva_home):
    project = slow_project(tmp_path / "p", 3, config="[tests]\ntimeout_s = 600\n")
    before = tree_fingerprint(project)
    code, report = run(capsys, "audit", str(project), "--execute", "--timeout-s", "1")
    assert code == 0 and tree_fingerprint(project) == before
    entry = native(report)
    assert entry["status"] == "BLOCKED"
    assert entry["limits"] == {"timeout_s": 1.0, "timeout_source": "command line (--timeout-s)", "selection": "full suite"}


@pytest.mark.integration
def test_a_long_suite_passes_when_the_limit_is_raised(tmp_path, capsys, assertiva_home):
    # the DrawLab shape at small scale: a suite longer than the project's own limit, raised for this audit only
    project = slow_project(tmp_path / "p", 2, config="[tests]\ntimeout_s = 1\n")
    code, blocked = run(capsys, "audit", str(project), "--execute")
    assert native(blocked)["status"] == "BLOCKED"
    assert native(blocked)["limits"]["timeout_source"] == "project configuration ([tests] timeout_s)"
    code, passed = run(capsys, "audit", str(project), "--execute", "--timeout-s", "60")
    assert native(passed)["status"] == "PASS" and native(passed)["limits"]["timeout_s"] == 60.0


@pytest.mark.artifact
def test_source_and_artifact_runs_of_one_revision_are_compared_side_by_side(tmp_path, capsys, assertiva_home):
    project = slow_project(tmp_path / "p", 0)
    write(project / "pyproject.toml", '[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = "setuptools.build_meta"\n\n'
                                      '[project]\nname = "calc"\nversion = "0.1.0"\n\n[tool.setuptools]\npy-modules = ["calc"]\n')
    code, report = run(capsys, "audit", str(project), "--execute", "--timeout-s", "300")
    rows = report["execution_manifest"]["comparison"]
    assert [r["what"] for r in rows] == ["pytest-native (execute)", "python-package tests against the installed wheel"]
    assert all(r["timeout_s"] == 300.0 and r["timeout_source"] == "command line (--timeout-s)" for r in rows)
    assert all(r["status"] == "PASS" and r["wall_clock_s"] is not None for r in rows)
