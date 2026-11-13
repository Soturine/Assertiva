"""`assertiva audit` finishing is not the audited project's tests passing: the verdict lives in the report."""

import json
import re
import sys
from pathlib import Path

import pytest

from assertiva import cli

from conftest import write


@pytest.mark.integration
def test_audit_command_success_is_not_the_audited_suite_passing(tmp_path, capsys):
    project = tmp_path / "failing"
    write(project / "lib.py", "def two():\n    return 2\n")
    write(project / "conftest.py", "")
    write(project / "tests" / "test_lib.py",
          "from lib import two\n\ndef test_two():\n    assert two() == 2\n\ndef test_broken():\n    assert two() == 3\n")
    code = cli.main(["audit", str(project), "--execute", "--python", sys.executable, "--output", "json", "--report-dir", str(tmp_path / "reports")])
    report = json.loads(capsys.readouterr().out)

    assert code == 0  # the command ran to completion and reported; 2 means refusal or misuse, 3 a read-only violation
    state = report["states"]["current"]
    assert state["runs"][0]["status"] == "FAIL"
    assert (state["metrics"]["passed"]["value"], state["metrics"]["failed"]["value"]) == (1, 1)
    assert report["status"] == "FINDINGS" and "NATIVE_TESTS_FAILING" in {f["code"] for f in report["findings"]}
    assert "native pytest-native run in an isolated copy: FAIL (2 invocations)" in report["claim_boundary"]["observed"]

    page = Path(report["report_path"]).read_text(encoding="utf-8")
    assert re.search(r'class="c-headline">.*?>Needs review<', page, re.S)  # the page concludes "needs review", not success
    assert sorted(p.name for p in (tmp_path / "reports").iterdir()) == ["audit.html", "audit.json"]


# --- opt-in CI gate (v1.0): --fail-on, the decision matrix, and the default that does not change -------------------

def _report(runs=(), artifacts=(), findings=()):
    return {"states": {"current": {"runs": list(runs), "artifacts": list(artifacts)}}, "findings": list(findings)}


def _run(status, provenance="ENGINE_EXECUTED", adapter="pytest-native"):
    return {"adapter": adapter, "status": status, "provenance": provenance}


def test_the_gate_decision_matrix():
    from assertiva.gate import evaluate

    def result(report, *conditions):
        return evaluate(report, list(conditions))["result"]

    passing, failing = _report([_run("PASS")]), _report([_run("FAIL")])
    assert result(passing, "test-failure") == "PASS" and result(failing, "test-failure") == "FAIL"
    for status in ("BLOCKED", "UNKNOWN", "NOT_RUN"):  # never a pass, but not a test failure either
        assert result(_report([_run(status)]), "test-failure") == "PASS"
        assert result(_report([_run(status)]), "not-passing") == "FAIL"
    assert result(_report(), "not-passing") == "FAIL"  # nothing executed is never a passing gate
    empty = evaluate(_report(), ["test-failure"])["conditions"][0]
    assert empty["result"] == "PASS" and "nothing to judge" in empty["note"]
    imported = _report([_run("PASS"), _run("FAIL", provenance="EXTERNAL_UNVERIFIED", adapter="junit")])
    assert result(imported, "test-failure") == "PASS"  # an imported result is not an executed one...
    assert result(imported, "imported-failure") == "FAIL"  # ...and has its own condition
    assert result(imported, "not-passing") == "PASS"
    assert result(_report([_run("PASS")], artifacts=[{"artifact": "w.whl", "status": "UNKNOWN"}]), "artifact") == "FAIL"
    high = _report([_run("PASS")], findings=[{"code": "X", "severity": "high"}, {"code": "Y", "severity": "low"}])
    assert result(high, "high-findings") == "FAIL" and result(high, "findings") == "FAIL"
    assert result(_report([_run("PASS")], findings=[{"code": "Y", "severity": "low"}]), "high-findings") == "PASS"
    gate = evaluate(failing, ["test-failure", "test-failure", "findings"])
    assert [c["condition"] for c in gate["conditions"]] == ["test-failure", "findings"] and gate["exit_code_on_fail"] == 1
    import pytest

    with pytest.raises(ValueError):
        evaluate(passing, ["everything"])


@pytest.mark.integration
def test_fail_on_turns_a_failing_suite_into_exit_1_and_records_why(tmp_path, capsys):
    project = tmp_path / "failing"
    write(project / "lib.py", "def two():\n    return 2\n")
    write(project / "conftest.py", "")
    write(project / "tests" / "test_lib.py", "from lib import two\n\ndef test_broken():\n    assert two() == 3\n")
    base = ["audit", str(project), "--execute", "--python", sys.executable, "--output", "json", "--report-dir", str(tmp_path / "r")]
    assert cli.main(base) == 0  # the default contract is unchanged
    assert "gate" not in json.loads(capsys.readouterr().out)
    assert cli.main([*base, "--fail-on", "test-failure"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["gate"]["result"] == "FAIL" and report["gate"]["conditions"][0]["because"] == ["pytest-native FAIL"]
    stored = json.loads((tmp_path / "r" / "audit.json").read_text(encoding="utf-8"))
    assert stored["gate"] == report["gate"]  # the written report explains the exit status
    write(project / "tests" / "test_lib.py", "from lib import two\n\ndef test_ok():\n    assert two() == 2\n")
    assert cli.main([*base, "--fail-on", "test-failure", "--fail-on", "not-passing"]) == 0
    assert json.loads(capsys.readouterr().out)["gate"]["result"] == "PASS"


def test_fail_on_needs_a_new_audit(tmp_path, capsys):
    assert cli.main(["audit", str(tmp_path), "--assessment", "a.json", "--fail-on", "findings"]) == 2
