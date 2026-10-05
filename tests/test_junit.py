"""Portable JUnit XML evidence: 'I have test results' without 'I understand this framework'."""

import json

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
    assert report["states"]["current"]["metrics"]["test_invocations"]["value"] == 5
    assert report["states"]["current"]["runs"][0]["adapter"] == "junit-xml"
    assert any(f["code"] == "NATIVE_TESTS_FAILING" for f in report["findings"])
    assert any("junit-xml" in item and "not executed by Assertiva" in item for item in report["claim_boundary"]["observed"])
    assert any(f["code"] == "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED" for f in report["findings"])
