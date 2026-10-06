"""Bounded stability evidence and execution provenance."""

import json
import sys

import pytest

from assertiva import process
from assertiva.candidate import QualificationCheck, StageStatus
from assertiva.improve import discard_session, qualify_candidate, start_improve
from assertiva.models import Outcome

from conftest import write


def counter_test(counter, fail_when):
    """A test whose outcome depends on how many times it has run (state kept outside any copy)."""
    return (
        "from pathlib import Path\n\n"
        "def test_counted():\n"
        f"    path = Path(r'{counter}')\n"
        "    n = int(path.read_text()) + 1 if path.exists() else 1\n"
        "    path.write_text(str(n))\n"
        f"    assert not ({fail_when})\n"
    )


def stage(q, name=QualificationCheck.STABILITY_AND_COST):
    return q.check(name)


@pytest.fixture
def session(calc_project):
    session = start_improve(calc_project, python=sys.executable)
    yield session
    discard_session(session)


@pytest.mark.integration
def test_alternating_outcome_is_a_flaky_signal_and_first_failure_is_kept(session, tmp_path):
    write(session.workspace / "tests" / "test_flaky.py", counter_test(tmp_path / "count", "n % 2 == 1"))
    result = qualify_candidate(session)
    record = next(r for r in result.stability.records if r.invocation_id == "tests/test_flaky.py::test_counted")
    assert record.verdict == "FLAKY_SIGNAL"
    assert record.outcomes[0] is Outcome.FAILED and Outcome.PASSED in record.outcomes[1:]
    q = result.qualification
    assert stage(q).status is StageStatus.FAIL
    assert stage(q, QualificationCheck.CANDIDATE_TESTS).status is StageStatus.FAIL  # a later pass does not erase it


@pytest.mark.integration
def test_consistent_pass_is_stable_within_the_observed_runs_only(session):
    write(session.workspace / "tests" / "test_new.py", "def test_new():\n    assert 2 * 3 == 6\n")
    result = qualify_candidate(session)
    [record] = result.stability.records
    assert record.verdict == "STABLE" and len(record.outcomes) == 3
    assert stage(result.qualification).status is StageStatus.PASS
    assert "no instability observed in 3 executions" in stage(result.qualification).summary


@pytest.mark.integration
def test_consistent_failure_is_not_instability_but_not_pass(session):
    write(session.workspace / "tests" / "test_new.py", "def test_new():\n    assert 2 * 3 == 7\n")
    result = qualify_candidate(session)
    [record] = result.stability.records
    assert record.verdict == "CONSISTENT_FAILURE"
    assert stage(result.qualification).status is not StageStatus.PASS


@pytest.mark.integration
def test_only_relevant_invocations_are_rerun(session):
    write(session.workspace / "tests" / "test_new.py", "def test_new():\n    assert 1 == 1\n")
    write(session.workspace / "tests" / "test_calc.py",
          (session.workspace / "tests" / "test_calc.py").read_text(encoding="utf-8"))  # unchanged content
    result = qualify_candidate(session)
    assert {r.invocation_id for r in result.stability.records} == {"tests/test_new.py::test_new"}


@pytest.mark.integration
def test_disabled_stability_is_not_run(session):
    write(session.workspace / "tests" / "test_new.py", "def test_new():\n    assert True\n")
    result = qualify_candidate(session, stability_reruns=0)
    assert stage(result.qualification).status is StageStatus.NOT_RUN


def test_command_trace_records_start_before_end_with_timeout_and_returncode(tmp_path):
    trace = tmp_path / "trace.jsonl"
    process.TRACE_PATH = trace
    try:
        with process.traced_stage("demo-stage"):
            result = process.run_command([sys.executable, "-c", "raise SystemExit(3)"], tmp_path, timeout_s=30)
    finally:
        process.TRACE_PATH = None
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    kinds = [e["event"] for e in events]
    assert kinds == ["stage_start", "command_start", "command_end", "stage_end"]
    start, end = events[1], events[2]
    assert start["timeout_s"] == 30 and start["stage"] == "demo-stage" and sys.executable in start["command"][0]
    assert end["returncode"] == 3 and end["timed_out"] is False and result.returncode == 3


def test_timeout_is_classified_not_hung(tmp_path):
    result = process.run_command([sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, timeout_s=1)
    assert result.timed_out and result.returncode is None
    assert "timed out after 1" in result.summary()


@pytest.mark.integration
def test_qualification_records_stage_durations(session):
    write(session.workspace / "tests" / "test_new.py", "def test_new():\n    assert True\n")
    result = qualify_candidate(session)
    assert {t["stage"] for t in result.timings} >= {"candidate-measure", "ORIGINAL_REGRESSION", "STABILITY_AND_COST"}
    assert all(t["duration_s"] >= 0 for t in result.timings)


@pytest.mark.integration
def test_cli_runs_leave_a_trace_outside_the_project(calc_project, capsys, assertiva_home):
    from pathlib import Path

    from assertiva import cli

    cli.main(["audit", str(calc_project), "--execute", "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    trace = Path(report["provenance"]["trace"])
    assert trace.is_file() and trace.is_relative_to(assertiva_home)
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert any(e["event"] == "command_end" and e["returncode"] == 0 for e in events)
    # every command is attributable to a phase, so a hang names what was running
    assert all(e["stage"] for e in events if e["event"].startswith("command"))
    assert {"current:pytest-native"} <= {e["stage"] for e in events}
    assert process.TRACE_PATH is None  # not left enabled for later callers
