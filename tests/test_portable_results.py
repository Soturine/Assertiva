"""CTRF and Allure results in, CTRF out. The fixtures were produced by real tools (pytest 9.1.1 with pytest-json-ctrf
0.6.1, allure-pytest 2.16.2 and pytest-rerunfailures 16.7) on tests/fixtures/portable-results/test_shop.py, with the
host name and local paths replaced (see that directory's README)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters.portable_results import load_allure, load_ctrf, load_results, to_ctrf
from assertiva.models import Outcome

FIXTURES = Path(__file__).parent / "fixtures" / "portable-results"


def _by(run):
    return {inv.invocation_id: inv for inv in run.invocations}


def test_ctrf_keeps_outcomes_parameters_retries_and_flakiness():
    run = load_ctrf(FIXTURES / "ctrf-report.json")
    tests = _by(run)
    assert run.metadata["tool"] == "pytest" and run.status.value == "FAIL"
    assert tests["tests/test_shop.py::test_discount_fails"].outcome is Outcome.FAILED
    assert tests["tests/test_shop.py::test_discount_fails"].attempts == 2  # failed, retried, failed again
    flaky = tests["tests/test_shop.py::test_flaky_then_passes"]
    assert flaky.outcome is Outcome.PASSED and flaky.attempts == 2 and "flaky" in flaky.markers  # never a clean pass
    assert tests["tests/test_shop.py::test_coupon_skipped"].outcome is Outcome.SKIPPED
    rounding = [inv for inv in run.invocations if inv.declaration_id == "tests/test_shop.py::test_rounding"]
    assert len(rounding) == 2 and {inv.parameters_id for inv in rounding} == {"100-10", "5-0"}


def test_allure_separates_declarations_from_invocations_and_rebuilds_retries():
    run = load_allure(FIXTURES / "allure-results")
    tests = _by(run)
    assert len(run.invocations) == 6  # eight result files: two are retries of invocations already counted
    assert {inv.materialization_id for inv in run.invocations if inv.declaration_id == "tests.test_shop#test_rounding"} != set()
    assert tests["tests.test_shop#test_flaky_then_passes"].attempts == 2
    assert run.metadata["flaky"] == ["tests.test_shop#test_flaky_then_passes"]
    assert tests["tests.test_shop#test_discount_fails"].outcome is Outcome.FAILED
    assert "tests.test_shop#test_rounding[cents=5,expected=0]" in tests


def test_results_never_carry_host_names_or_absolute_paths(tmp_path):
    result = json.loads(next((FIXTURES / "allure-results").glob("*-result.json")).read_text(encoding="utf-8"))
    result.update(status="failed", statusDetails={"message": r"OSError at C:\Users\someone\proj\db.py", "trace": "x"},
                  labels=[{"name": "host", "value": "WORKSTATION-7"}, {"name": "thread", "value": "1-Main"}])
    (tmp_path / "a-result.json").write_text(json.dumps(result), encoding="utf-8")
    [inv] = load_allure(tmp_path).invocations
    text = json.dumps([inv.message, inv.markers])
    assert "someone" not in text and "WORKSTATION" not in text and "thread" not in text and "<path>" in inv.message


def test_unknown_statuses_stay_unknown_and_unreadable_results_block(tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({"results": {"tool": {"name": "x"}, "tests": [{"name": "t", "status": "other"}]}}))
    run = load_results(tmp_path / "r.json")
    assert run.adapter_id == "ctrf" and run.invocations[0].outcome is None and any("stays unknown" in x for x in run.limitations)
    (tmp_path / "bad.json").write_text('{"results": ')
    assert load_ctrf(tmp_path / "bad.json").status.value == "BLOCKED"


def test_exported_ctrf_reads_back_with_the_same_outcomes():
    original = load_ctrf(FIXTURES / "ctrf-report.json")
    exported = to_ctrf([original], "assertiva", "assertiva test")
    assert exported["reportFormat"] == "CTRF" and exported["results"]["summary"]["failed"] == 1
    again = load_ctrf_from(exported)
    assert {i.invocation_id: i.outcome for i in again.invocations} == {i.invocation_id: i.outcome for i in original.invocations}


def load_ctrf_from(data):
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "r.json"
        target.write_text(json.dumps(data), encoding="utf-8")
        return load_ctrf(target)


@pytest.mark.integration
def test_audit_imports_portable_results_and_exports_its_own_run_as_ctrf(calc_project, tmp_path, capsys):
    out = tmp_path / "reports"
    capsys.readouterr()
    cli.main(["audit", str(calc_project), "--execute", "--python", sys.executable, "--report-dir", str(out),
              "--test-results", str(FIXTURES / "ctrf-report.json"), "--ctrf", "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    adapters = [run["adapter"] for run in report["states"]["current"]["runs"]]
    [imported] = [r for r in report["states"]["current"]["runs"] if r["adapter"] == "ctrf"]
    assert imported["provenance"] == "EXTERNAL_UNVERIFIED" and imported["outcomes"]["FAILED"] == 1
    assert "ctrf" in adapters and report["exported"] == {"ctrf": "audit.ctrf.json"}
    exported = json.loads((out / "audit.ctrf.json").read_text(encoding="utf-8"))
    names = {t["name"] for t in exported["results"]["tests"]}
    assert "tests/test_calc.py::test_add_value" in names and not any(n.startswith("tests/test_shop.py") for n in names)
    assert not (calc_project / "audit.ctrf.json").exists()  # never written into the audited project
