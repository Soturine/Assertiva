"""EXECUTION is one claim — the candidate's tests are collected and the changed ones run — answered by one check.

It used to be two checks (STATIC_AND_DISCOVERY and CANDIDATE_TESTS) that reported the same missing runner or blocked run
twice. Each case below is a branch of either former check; the pillar outcome must be the one the two checks produced
together, so merging them removes duplicate UNKNOWN/BLOCKED rows without weakening what the pillar catches."""

import pytest

from assertiva.candidate import (
    PILLARS, CandidateChangeKind, CandidateTestChange, QualificationCheck, QualificationStage, StageStatus, pillar,
)
from assertiva.evidence import StateEvidence
from assertiva.improve import _execution_stage
from assertiva.models import Outcome, RunEvidence
from assertiva.models import TestInvocation as Invocation

CHANGED = "tests/test_new.py"


def _inv(name: str, outcome: Outcome | None, path: str = CHANGED) -> Invocation:
    return Invocation(f"{path}::{name}", f"{path}::{name}", f"{path}::{name}", outcome=outcome, source_paths=(path,))


def _state(*runs: RunEvidence) -> StateEvidence:
    state = StateEvidence("candidate", "isolated-candidate-copy")
    state.runs.extend(runs)
    return state


def _run(*invocations, status=StageStatus.PASS, errors=(), sources=None) -> RunEvidence:
    run = RunEvidence("fake", "execute", status, list(invocations), list(errors))
    if sources:
        run.metadata["error_sources"] = sources
    return run


ADD = [CandidateTestChange("c1", CHANGED, CandidateChangeKind.ADD, "added in candidate")]

CASES = [
    # (state, changes, pillar status that STATIC_AND_DISCOVERY + CANDIDATE_TESTS produced)
    pytest.param(_state(), ADD, StageStatus.UNKNOWN, id="no-runner"),
    pytest.param(_state(_run(_inv("a", Outcome.PASSED), errors=["tests/test_old.py"], sources={"tests/test_old.py": "tests/test_old.py"})),
                 ADD, StageStatus.FAIL, id="collection-error-in-an-unchanged-file"),
    pytest.param(_state(_run(errors=[CHANGED], sources={CHANGED: CHANGED})), ADD, StageStatus.FAIL, id="changed-file-fails-to-collect"),
    pytest.param(_state(_run(_inv("a", Outcome.PASSED), status=StageStatus.BLOCKED)), ADD, StageStatus.BLOCKED, id="runner-blocked"),
    pytest.param(_state(_run()), ADD, StageStatus.UNKNOWN, id="nothing-collected"),
    pytest.param(_state(_run(_inv("a", Outcome.PASSED, "tests/test_old.py"))), [], StageStatus.PASS, id="no-test-changes"),
    pytest.param(_state(_run(_inv("a", Outcome.FAILED))), ADD, StageStatus.FAIL, id="changed-test-fails"),
    pytest.param(_state(_run(_inv("a", Outcome.SKIPPED))), ADD, StageStatus.UNKNOWN, id="changed-tests-only-skipped"),
    pytest.param(_state(_run(_inv("a", Outcome.PASSED), _inv("b", Outcome.PASSED, "tests/test_old.py"))), ADD, StageStatus.PASS, id="changed-tests-pass"),
]


@pytest.mark.parametrize("state, changes, expected", CASES)
def test_execution_pillar_keeps_every_outcome_of_the_two_former_checks(state, changes, expected):
    check = _execution_stage(changes, state)
    assert check.check is QualificationCheck.CANDIDATE_TESTS
    assert pillar(QualificationStage.EXECUTION, [check]).status is expected


def test_execution_is_one_check_and_a_missing_runner_is_reported_once():
    assert PILLARS[QualificationStage.EXECUTION] == (QualificationCheck.CANDIDATE_TESTS,)
    assert "STATIC_AND_DISCOVERY" not in QualificationCheck.__members__


def test_a_collection_error_outside_the_change_still_names_the_errors():
    state = _state(_run(_inv("a", Outcome.PASSED), errors=["tests/test_old.py"], sources={"tests/test_old.py": "tests/test_old.py"}))
    assert _execution_stage(ADD, state).summary == "collection errors: tests/test_old.py"
