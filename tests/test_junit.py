"""Portable JUnit XML evidence: 'I have test results' without 'I understand this framework'."""

import json

import pytest
import sys

from assertiva.adapters.junit import load_junit
from assertiva.candidate import StageStatus
from assertiva.models import Outcome

from conftest import write

NESTED = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="all">
  <testsuite name="api" tests="3" timestamp="2026-10-05T10:00:00">
    <properties><property name="browser" value="firefox"/></properties>
    <testcase classname="checkout" name="pays" time="0.25"/>
    <testcase classname="checkout" name="rejects card" time="0.10"><failure message="expected 402" type="AssertionError">trace</failure></testcase>
    <testcase classname="checkout" name="db down" time="0.05"><error message="connection refused"/></testcase>
  </testsuite>
  <testsuite name="ui" tests="2">
    <testcase classname="checkout" name="pays" time="1.5"/>
    <testcase classname="checkout" name="legacy" time="0"><skipped message="not on this platform"/></testcase>
  </testsuite>
</testsuites>
"""


def outcomes(run):
    return {inv.invocation_id: inv.outcome for inv in run.invocations}


def test_nested_suites_with_duplicate_names_stay_distinct(tmp_path):
    run = load_junit(write(tmp_path / "junit.xml", NESTED))
    assert outcomes(run) == {
        "all/api::checkout::pays": Outcome.PASSED,
        "all/api::checkout::rejects card": Outcome.FAILED,
        "all/api::checkout::db down": Outcome.ERROR,
        "all/ui::checkout::pays": Outcome.PASSED,
        "all/ui::checkout::legacy": Outcome.SKIPPED,
    }
    assert run.status is StageStatus.FAIL and run.mode == "report"
    failure = next(i for i in run.invocations if i.outcome is Outcome.FAILED)
    assert failure.message == "expected 402" and failure.duration_s == 0.10


def test_suite_properties_and_timestamps_are_preserved(tmp_path):
    run = load_junit(write(tmp_path / "junit.xml", NESTED))
    api = next(s for s in run.metadata["suites"] if s["name"] == "all/api")
    assert api["properties"] == {"browser": "firefox"} and api["timestamp"] == "2026-10-05T10:00:00"


def test_format_limits_are_declared_not_invented(tmp_path):
    run = load_junit(write(tmp_path / "junit.xml", NESTED))
    assert all(inv.parameters_id is None and not inv.inherited for inv in run.invocations)
    assert run.coverage is None
    text = " ".join(run.limitations)
    for missing in ("parameter", "xfail", "retry", "coverage", "materialization"):
        assert missing in text


def test_single_testsuite_root_and_partial_fields(tmp_path):
    run = load_junit(write(tmp_path / "j.xml", '<testsuite><testcase name="only name"/></testsuite>'))
    [inv] = run.invocations
    assert inv.invocation_id == "only name" and inv.duration_s is None and inv.outcome is Outcome.PASSED
    assert run.status is StageStatus.PASS


def test_empty_report_is_unknown_not_pass(tmp_path):
    run = load_junit(write(tmp_path / "j.xml", '<testsuites/>'))
    assert run.status is StageStatus.UNKNOWN and run.invocations == []


def test_all_skipped_is_unknown_not_pass(tmp_path):
    run = load_junit(write(tmp_path / "j.xml", '<testsuite><testcase name="a"><skipped/></testcase></testsuite>'))
    assert run.status is StageStatus.UNKNOWN


def test_malformed_xml_is_blocked(tmp_path):
    run = load_junit(write(tmp_path / "j.xml", "<testsuite><testcase"))
    assert run.status is StageStatus.BLOCKED and run.invocations == []
    assert run.limitations


def test_huge_output_is_bounded(tmp_path):
    noise = "x" * 500_000
    xml = f'<testsuite><testcase name="a"><failure message="{"m" * 50_000}">{noise}</failure><system-out>{noise}</system-out></testcase></testsuite>'
    run = load_junit(write(tmp_path / "j.xml", xml))
    [inv] = run.invocations
    assert len(inv.message) <= 1000
    assert run.metadata["system_out_chars"] == 500_000
    assert len(json.dumps(run.metadata)) < 5000


def test_summarizer_script_uses_the_same_parser(tmp_path):
    from scripts.summarize_junit import summarize

    summary = summarize(write(tmp_path / "junit.xml", NESTED))
    assert summary["executed"] == 5 and summary["passed"] == 2 and summary["failed"] == 2 and summary["skipped"] == 1
    assert {f["id"] for f in summary["failures"]} == {"all/api::checkout::rejects card", "all/api::checkout::db down"}


def test_audit_of_unknown_toolchain_uses_portable_results(tmp_path, capsys):
    from assertiva import cli

    project = tmp_path / "custom-stack"
    write(project / "build.custom", "verify: proprietary\n")
    junit = write(tmp_path / "results.xml", NESTED)
    cli.main(["audit", str(project), "--junit-xml", str(junit), "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert report["status"] != "UNKNOWN"
    assert report["states"]["current"]["metrics"]["imported_invocations"]["value"] == 5  # v1.0: counted as imported
    assert "test_invocations" not in report["states"]["current"]["metrics"]
    assert report["states"]["current"]["runs"][0]["adapter"] == "junit-xml"
    # v1.0 addendum CP-B: the file reports failures; Assertiva's runner did not run them, so they are not native
    assert not any(f["code"] in ("NATIVE_TESTS_FAILING", "NATIVE_COLLECTION_ERRORS") for f in report["findings"])
    imported = next(f for f in report["findings"] if f["code"] == "IMPORTED_TEST_RESULTS_FAILING")
    assert imported["evidence"]["provenance"] == "EXTERNAL_UNVERIFIED" and imported["evidence"]["count"] >= 1
    assert any("junit-xml" in item and "not executed by Assertiva" in item for item in report["claim_boundary"]["observed"])
    assert any(f["code"] == "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED" for f in report["findings"])


def test_imported_surefire_reruns_keep_their_failed_attempts(tmp_path):
    # a report imported with --junit-xml (not run by Assertiva's Maven adapter) still says a pass came after failures
    report = tmp_path / "TEST-demo.xml"
    report.write_text(
        '<testsuite name="demo"><testcase classname="demo.PriceTest" name="rounds">'
        '<flakyFailure message="expected 3 but was 2"/></testcase>'
        '<testcase classname="demo.PriceTest" name="totals"><failure message="boom"/>'
        '<rerunFailure message="boom"/><rerunFailure message="boom"/></testcase>'
        '<testcase classname="demo.PriceTest" name="plain"/></testsuite>', encoding="utf-8")
    run = load_junit(report)
    by_name = {inv.invocation_id.rsplit("::", 1)[-1]: inv for inv in run.invocations}
    assert by_name["rounds"].outcome is Outcome.PASSED and by_name["rounds"].attempts == 2
    assert "earlier attempts failed" in by_name["rounds"].message
    assert by_name["totals"].outcome is Outcome.FAILED and by_name["totals"].attempts == 3
    assert by_name["plain"].attempts is None  # JUnit XML alone does not say how many attempts ran
    assert any("passed only after earlier failed attempts" in lim for lim in run.limitations)


def test_imported_cases_never_add_to_executed_counts(tmp_path):
    """Randomizer dogfood (AXR-02): one host test executed natively plus N cases read from a JUnit file are two
    sources; the executed counters stay the host's, and the cases are counted as imported."""
    from assertiva.evidence import StateEvidence, state_metrics
    from assertiva.models import Outcome, RunEvidence, TestInvocation
    from assertiva.candidate import StageStatus

    host = RunEvidence(adapter_id="pytest-native", mode="execute", status=StageStatus.PASS,
                       invocations=[TestInvocation("tests/test_host.py::test_lua", "d", "m", outcome=Outcome.PASSED)])
    imported = load_junit(write(tmp_path / "lua.xml", NESTED))
    metrics = state_metrics(StateEvidence("current", "copy", runs=[host, imported]))
    assert metrics["test_invocations"].value == 1 and metrics["passed"].value == 1
    assert metrics["imported_invocations"].value == len(imported.invocations) == 5
    assert metrics["imported_failed"].value == sum(inv.outcome is Outcome.FAILED for inv in imported.invocations)


# --- v1.0 addendum CP-B: failures read from a file are not the native runner's failures ----------------------------

def _findings(report):
    return {f["code"]: f for f in report["findings"]}


@pytest.mark.integration
def test_imported_failures_next_to_a_passing_native_run_are_named_as_imported(tmp_path, capsys):
    from assertiva import cli

    project = tmp_path / "py"
    write(project / "lib.py", "def two():\n    return 2\n")
    write(project / "conftest.py", "")
    write(project / "tests" / "test_lib.py", "from lib import two\n\ndef test_two():\n    assert two() == 2\n")
    junit = write(tmp_path / "secret-ci-export" / "external.xml", NESTED)
    cli.main(["audit", str(project), "--execute", "--python", sys.executable, "--junit-xml", str(junit), "--output", "json",
              "--report-dir", str(tmp_path / "r")])
    report = json.loads(capsys.readouterr().out)
    codes = _findings(report)
    assert "NATIVE_TESTS_FAILING" not in codes  # the native run passed; Assertiva's runner did not fail
    imported = codes["IMPORTED_TEST_RESULTS_FAILING"]["evidence"]
    assert imported["provenance"] == "EXTERNAL_UNVERIFIED" and imported["count"] >= 1
    assert imported["sources"] == [{"adapter": "junit-xml", "file": "external.xml"}]  # never the absolute path
    assert "secret-ci-export" not in json.dumps(codes["IMPORTED_TEST_RESULTS_FAILING"])
    assert "not verified" in imported["revision"]
    metrics = report["states"]["current"]["metrics"]
    assert metrics["failed"]["value"] == 0 and metrics["imported_failed"]["value"] >= 1


@pytest.mark.integration
def test_control_a_native_run_that_fails_is_still_native(tmp_path, capsys):
    from assertiva import cli

    project = tmp_path / "py"
    write(project / "lib.py", "def two():\n    return 2\n")
    write(project / "conftest.py", "")
    write(project / "tests" / "test_lib.py", "from lib import two\n\ndef test_two():\n    assert two() == 3\n")
    cli.main(["audit", str(project), "--execute", "--python", sys.executable, "--output", "json", "--report-dir", str(tmp_path / "r")])
    codes = _findings(json.loads(capsys.readouterr().out))
    assert "NATIVE_TESTS_FAILING" in codes and "IMPORTED_TEST_RESULTS_FAILING" not in codes
