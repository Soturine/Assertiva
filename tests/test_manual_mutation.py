"""TCC-A14 / TCC-A23: hand-written mutants keep their provenance; they are never an engine run or a project score."""

import json

from assertiva.adapters.mutation import MANUAL_FORMAT, load_mutation_report
from assertiva.evidence import StateEvidence, attach_mutation, state_metrics

PATCH = "a" * 64


def manifest(tmp_path, mutants):
    path = tmp_path / "manual.json"
    path.write_text(json.dumps({"format": MANUAL_FORMAT, "operator": "reviewer", "revision": "abc1234", "runner": "gradle test",
                                "mutants": mutants}), encoding="utf-8")
    return path


def test_manual_mutants_are_operator_provenance_with_exit_code_backed_statuses(tmp_path):
    run = load_mutation_report(manifest(tmp_path, [
        {"id": "A12", "file": "app/Session.kt", "operator": "boolean flip", "patch_sha256": PATCH, "tests": ["SessionTest"],
         "exit_code": 1, "status": "KILLED"},
        {"id": "A13", "file": "app/Mapper.kt", "operator": "role widened", "patch_sha256": "b" * 64, "exit_code": 0, "status": "SURVIVED"},
    ]))
    assert run.error is None and run.provenance == "OPERATOR_MANUAL" and not run.orchestrated
    assert run.counts == {"KILLED": 1, "SURVIVED": 1}
    assert any("not a mutation score" in limitation for limitation in run.limitations)
    assert run.mutants[0].killed_by == ("SessionTest",) and run.killers_complete is False


def test_a_status_the_exit_code_does_not_support_is_unknown(tmp_path):
    run = load_mutation_report(manifest(tmp_path, [
        {"id": "m1", "patch_sha256": PATCH, "exit_code": 0, "status": "KILLED"},     # recorded killed, runner passed
        {"id": "m2", "patch_sha256": PATCH, "status": "KILLED"},                     # no exit code
        {"id": "m3", "patch_sha256": "not-a-hash", "exit_code": 1, "status": "KILLED"},  # change not identified
    ]))
    assert [m.status.value for m in run.mutants] == ["UNKNOWN", "UNKNOWN", "UNKNOWN"]
    assert "exited 0" in run.mutants[0].status_reason and "exit code" in run.mutants[1].status_reason


def test_manual_mutants_never_become_the_states_mutation_metrics(tmp_path):
    state = StateEvidence(label="current", observed_in="copy")
    attach_mutation(state, load_mutation_report(manifest(tmp_path, [
        {"id": "m1", "patch_sha256": PATCH, "exit_code": 1, "status": "KILLED"}])), tmp_path)
    assert not any(name.startswith("mutation_") for name in state_metrics(state))


def test_a_summary_states_the_complete_survivor_count_and_its_truncation():
    from assertiva.models import MutantRecord, MutantStatus, MutationRun
    from assertiva.report import _mutation_summary

    run = MutationRun(source="t", tool="Cosmic Ray", mutants=[
        MutantRecord(mutant_id=str(i), status=MutantStatus.SURVIVED, native_status="x", path="a.py", line=i, operator="op")
        for i in range(1, 80)])
    summary = _mutation_summary(run)
    assert len(summary["survivors"]) == 50 and summary["survivors_total"] == 79 and summary["survivors_truncated"] is True
    small = _mutation_summary(MutationRun(source="t", mutants=run.mutants[:3]))
    assert small["survivors_total"] == 3 and small["survivors_truncated"] is False
