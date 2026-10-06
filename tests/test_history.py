"""Revision-aware history: what is kept, what is never kept, and the semantics computed from it."""

import json
import sqlite3
import sys

import pytest

from assertiva.candidate import StageStatus
from assertiva.history import (
    SCHEMA_VERSION, HistoryError, HistoryStore, Stability, classify, classify_attempts, duration_summary, fingerprint, summarize,
)
from assertiva import models
from assertiva.models import Outcome, RunEvidence


def run(outcome=Outcome.PASSED, message=None, duration=0.5, attempts=None, python="/venv/bin/python", test="tests/test_a.py::test_a"):
    return RunEvidence(adapter_id="pytest-native", mode="execute", status=StageStatus.PASS, command=[python, "-m", "pytest"],
                       invocations=[models.TestInvocation(test, test, test, outcome=outcome, duration_s=duration, message=message,
                                                   source_paths=("tests/test_a.py",), attempts=attempts)])


@pytest.fixture
def store(tmp_path):
    db = HistoryStore(tmp_path / "history.sqlite3")
    yield db
    db.close()


def stability(store, revision="rev1", state=None):
    [observations] = store.observations(["tests/test_a.py::test_a"]).values()
    return classify(observations, revision, current_state=state)[0]


def test_schema_is_versioned_and_newer_schemas_are_refused(tmp_path):
    HistoryStore(tmp_path / "h.sqlite3").close()
    db = sqlite3.connect(tmp_path / "h.sqlite3")
    assert db.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    db.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    db.commit()
    db.close()
    with pytest.raises(HistoryError):
        HistoryStore(tmp_path / "h.sqlite3")


def test_only_useful_evidence_is_kept_never_raw_output_or_secrets(store):
    message = "AssertionError: token=hunter2 at /tmp/pytest-of-x/pytest-9/test_a0/tests/test_a.py:12\n" + "x" * 50_000
    first = store.record("audit", "current", "rev1", "abc", [run(Outcome.FAILED, message)],
                         selection={"confidence": "PROVEN_PATHS"}, selection_reasons={"tests/test_a.py": "depends on calc.py"},
                         coverage={"tool": "coverage.py", "counts": {"line": {"covered": 5, "total": 8}}},
                         artifacts=[{"kind": "wheel", "artifact": "shop.whl", "sha256": "ab" * 32, "status": "PASS"}],
                         qualification={"EXECUTION": "PASS"})
    second = store.record("audit", "current", "rev2", "def", [run()])
    previous = store.previous_state(second)
    assert previous["coverage"]["counts"]["line"] == {"covered": 5, "total": 8} and previous["artifacts"][0]["sha256"] == "ab" * 32
    assert previous["qualification"] == {"EXECUTION": "PASS"} and store.previous_state(first) is None
    dump = "\n".join(store.db.iterdump())
    assert "hunter2" not in dump and "pytest-of-x" not in dump and "x" * 300 not in dump
    row = store.db.execute("SELECT outcome, selection_reason, fingerprint, failure_signature FROM invocations").fetchone()
    assert row[0] == "FAILED" and row[1] == "depends on calc.py" and row[2] and "test_a.py:12" in row[3]


def test_one_failure_is_never_flaky(store):
    for outcome in (Outcome.PASSED, Outcome.PASSED, Outcome.FAILED):
        store.record("audit", "current", "rev1", None, [run(outcome)])
    assert stability(store) is Stability.INSUFFICIENT_EVIDENCE


def test_repeated_failures_and_passes_at_one_revision_are_historically_flaky(store):
    for outcome in (Outcome.PASSED, Outcome.FAILED, Outcome.FAILED):
        store.record("audit", "current", "rev1", None, [run(outcome)])
    assert stability(store) is Stability.HISTORICALLY_FLAKY


def test_failures_and_passes_on_different_revisions_are_not_flakiness(store):
    store.record("audit", "current", "rev1", None, [run(Outcome.FAILED)])
    store.record("audit", "current", "rev1", None, [run(Outcome.FAILED)])
    store.record("audit", "current", "rev2", None, [run(Outcome.PASSED)])
    assert stability(store, "rev1") is Stability.CONSISTENT_FAILURE
    assert stability(store, "rev2") is Stability.INSUFFICIENT_EVIDENCE


def test_environment_specific_failure(store):
    for _ in range(2):
        store.record("audit", "current", "rev1", None, [run(Outcome.FAILED, python="/ci/py311/bin/python")])
    store.record("audit", "current", "rev1", None, [run(Outcome.PASSED, python="/ci/py312/bin/python")])
    assert stability(store) is Stability.ENVIRONMENT_SPECIFIC


def test_a_pass_after_retries_is_kept_as_instability_not_a_normal_pass(store):
    state = store.record("audit", "current", "rev1", None, [run(Outcome.PASSED, attempts=2)])
    assert stability(store, state=state) is Stability.OBSERVED_UNSTABLE_CURRENT_RUN
    assert store.db.execute("SELECT outcome, attempts FROM invocations").fetchone() == ("PASSED", 2)


@pytest.mark.parametrize(("outcomes", "expected"), [
    ((Outcome.FAILED, Outcome.PASSED), Stability.OBSERVED_UNSTABLE_CURRENT_RUN),
    ((Outcome.FAILED, Outcome.FAILED, Outcome.FAILED), Stability.CONSISTENT_FAILURE),
    ((Outcome.PASSED, Outcome.PASSED, Outcome.PASSED), Stability.NO_INSTABILITY_OBSERVED),
    ((Outcome.PASSED,), Stability.INSUFFICIENT_EVIDENCE),
    ((Outcome.PASSED, None), Stability.INSUFFICIENT_EVIDENCE),
])
def test_current_run_attempts(outcomes, expected):
    assert classify_attempts(outcomes) is expected


def test_percentiles_only_with_enough_samples():
    assert duration_summary([1.0, 2.0, 3.0]) == {"samples": 3, "p50": None, "p95": None}
    five = duration_summary([5.0, 1.0, 4.0, 2.0, 3.0])
    assert five["p50"] == 3.0 and five["p95"] is None
    twenty = duration_summary([float(n) for n in range(1, 21)])
    assert (twenty["p50"], twenty["p95"]) == (10.0, 19.0)


def test_fingerprints_ignore_noise_and_keep_meaning():
    a = fingerprint("AssertionError: expected 3 got 4 at /tmp/pytest-1/x/tests/test_a.py:12 0x7f3a9c 2026-10-06T10:00:01Z took 1.25s")
    b = fingerprint("AssertionError: expected 3 got 4 at C:\\Temp\\pytest-77\\y\\tests\\test_a.py:12 0x55aa01 2026-10-07T11:22:33Z took 9s")
    assert a == b and a[1].startswith("[run] AssertionError at test_a.py:12")
    assert fingerprint("AssertionError: expected 3 got 5 at tests/test_a.py:12")[0] != a[0]  # different values stay apart
    assert fingerprint("ValueError: expected 3 got 4 at tests/test_a.py:12")[0] != a[0]
    assert fingerprint("ImportError: no module named x", stage="collection")[0] != fingerprint("ImportError: no module named x")[0]
    assert fingerprint(None) is None and fingerprint("") is None


def test_summary_reports_failures_with_their_group(store):
    first = store.record("audit", "current", "rev1", None, [run(Outcome.FAILED, "ValueError: bad id 123e4567-e89b-12d3-a456-426614174000")])
    second = store.record("audit", "current", "rev1", None, [run(Outcome.FAILED, "ValueError: bad id 00000000-e89b-12d3-a456-426614174999")])
    summary = summarize(store, second, "rev1", [run(Outcome.FAILED, "ValueError: bad id 00000000-e89b-12d3-a456-426614174999")])
    [entry] = summary["invocations"]
    assert entry["stability"] == "CONSISTENT_FAILURE" and entry["fingerprint_occurrences"] == 2
    assert summary["states_recorded"] == 2 and first < second
    assert summary["previous_state"]["revision"] == "rev1"  # what was recorded before, for comparison


def test_history_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSERTIVA_HISTORY", "off")
    assert HistoryStore.for_project(tmp_path / "project") is None


@pytest.mark.integration
def test_audit_records_history_and_reports_a_consistent_failure(calc_project):
    from assertiva.audit import run_audit
    from assertiva.report import render_html
    from conftest import write

    write(calc_project / "tests" / "test_broken.py", "def test_broken():\n    assert 1 + 1 == 3\n")
    run_audit(calc_project, execute=True, python=sys.executable)
    report = run_audit(calc_project, execute=True, python=sys.executable)
    history = report["history"]
    assert history["enabled"] and history["states_recorded"] == 2
    [entry] = [e for e in history["invocations"] if e["invocation_id"].endswith("test_broken")]
    assert entry["stability"] == "CONSISTENT_FAILURE" and entry["fingerprint_occurrences"] == 2
    assert "History" in render_html(report)
    assert json.dumps(report)  # serializable
