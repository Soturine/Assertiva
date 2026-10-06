"""`assertiva improve`: isolated candidate, qualification, approval boundary, post-apply."""

import sys

import pytest

from assertiva.candidate import CandidateChangeKind, DeltaState, QualificationCheck, QualificationStage, StageStatus
from assertiva.evidence import ControlOutcome, NegativeControl
from assertiva.improve import (
    apply_approved,
    discard_session,
    load_session,
    qualify_candidate,
    start_improve,
)
from assertiva.workspace import Approval, StaleBaselineError, file_digest, tree_fingerprint

from conftest import write

pytestmark = pytest.mark.integration

PY = sys.executable
STRONG_TEST = "from calc import add\n\ndef test_add_distinguishes_operands():\n    assert add(2, 3) == 5\n"
MULTIPLY_CONTROL = NegativeControl(
    control_id="add-becomes-multiply",
    path="calc.py",
    find="return a + b",
    replace="return a * b",
    claim="add() returns the sum",
)


def stage(qualification, name):
    return qualification.check(name)


def delta(qualification, name):
    return next(d for d in qualification.metric_deltas if d.name == name)


@pytest.fixture
def session(calc_project):
    session = start_improve(calc_project, python=PY)
    yield session
    discard_session(session)


def test_improve_does_not_modify_original_before_approval(calc_project):
    original = tree_fingerprint(calc_project)
    session = start_improve(calc_project, python=PY)
    try:
        write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
        (session.workspace / "tests" / "test_calc.py").unlink()
        qualify_candidate(session, negative_controls=[MULTIPLY_CONTROL])
        assert tree_fingerprint(calc_project) == original
    finally:
        discard_session(session)
    assert tree_fingerprint(calc_project) == original


def test_session_survives_between_invocations(session, calc_project):
    loaded = load_session(calc_project)
    assert loaded is not None
    assert loaded.workspace == session.workspace
    assert loaded.baseline == session.baseline
    assert loaded.baseline_evidence.runs[0].status is StageStatus.PASS


def test_baseline_is_measured_in_isolation(session):
    run = session.baseline_evidence.runs[0]
    assert run.status is StageStatus.PASS
    assert {inv.invocation_id for inv in run.invocations} == {
        "tests/test_calc.py::test_add_runs",
        "tests/test_calc.py::test_add_value",
    }
    assert session.baseline_evidence.observed_in == "isolated-baseline-copy"


def test_candidate_evidence_is_compared_with_metric_semantics(session):
    write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
    result = qualify_candidate(session)
    q = result.qualification
    assert delta(q, "weak_oracle_tests").state is DeltaState.UNCHANGED
    assert delta(q, "test_invocations").state is DeltaState.CHANGED  # count is contextual
    assert stage(q, QualificationCheck.CANDIDATE_TESTS).status is StageStatus.PASS
    assert stage(q, QualificationCheck.ORIGINAL_REGRESSION).status is StageStatus.PASS
    assert [(c.path, c.kind) for c in q.changes] == [("tests/test_strong.py", CandidateChangeKind.ADD)]
    assert result.candidate_evidence.observed_in == "isolated-candidate-copy"


def test_branch_coverage_is_compared_when_measurable(calc_project):
    write(calc_project / "calc.py", "def sign(x):\n    if x < 0:\n        return -1\n    return 1\n\ndef add(a, b):\n    return a + b\n")
    session = start_improve(calc_project, python=PY)
    try:
        write(session.workspace / "tests" / "test_sign.py", "from calc import sign\n\ndef test_negative():\n    assert sign(-5) == -1\n")
        q = qualify_candidate(session).qualification
    finally:
        discard_session(session)
    assert delta(q, "branch_coverage").state is DeltaState.IMPROVED
    assert stage(q, QualificationCheck.COVERAGE_AND_ORACLES).status is StageStatus.PASS


def test_fewer_tests_can_still_be_better_evidence(session):
    (session.workspace / "tests" / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add_value():\n    assert add(2, 3) == 5\n", encoding="utf-8"
    )
    q = qualify_candidate(session).qualification
    assert delta(q, "test_invocations").state is DeltaState.CHANGED
    assert delta(q, "weak_oracle_tests").state is DeltaState.IMPROVED


def test_weakened_test_cannot_hide_production_regression(session):
    """Candidate breaks behavior and edits the test to match: candidate tests go green,
    but the unchanged original tests must still be run against the candidate."""
    (session.workspace / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (session.workspace / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n"
        "def test_add_runs():\n    assert add(1, 2) is not None\n\n"
        "def test_add_value():\n    assert add(2, 2) == 0\n",
        encoding="utf-8",
    )
    q = qualify_candidate(session).qualification
    assert stage(q, QualificationCheck.CANDIDATE_TESTS).status is StageStatus.PASS
    regression = stage(q, QualificationCheck.ORIGINAL_REGRESSION)
    assert regression.status is StageStatus.FAIL
    assert "tests/test_calc.py::test_add_value" in regression.summary
    assert not q.ready_for_review


def test_negative_control_survivor_is_reported_and_candidate_can_kill_it(session):
    write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
    result = qualify_candidate(session, negative_controls=[MULTIPLY_CONTROL])
    baseline_controls = {r.control_id: r.outcome for r in result.baseline_controls}
    candidate_controls = {r.control_id: r.outcome for r in result.candidate_evidence.negative_controls}
    assert baseline_controls == {"add-becomes-multiply": ControlOutcome.SURVIVED}
    assert candidate_controls == {"add-becomes-multiply": ControlOutcome.KILLED}
    q = result.qualification
    assert stage(q, QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS).status is StageStatus.PASS
    assert delta(q, "negative_controls_survived").state is DeltaState.IMPROVED


def test_negative_control_surviving_candidate_fails_stage(session):
    q = qualify_candidate(session, negative_controls=[MULTIPLY_CONTROL]).qualification
    assert stage(q, QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS).status is StageStatus.FAIL


def test_inapplicable_negative_control_is_invalid_not_killed(session):
    control = NegativeControl("missing", "calc.py", "return nothing_like_this", "return 0", "n/a")
    result = qualify_candidate(session, negative_controls=[control])
    assert result.candidate_evidence.negative_controls[0].outcome is ControlOutcome.INVALID
    stage_result = stage(result.qualification, QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS)
    assert stage_result.status is StageStatus.UNKNOWN


def test_unavailable_stages_are_never_reported_as_pass(session):
    write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
    q = qualify_candidate(session).qualification
    for name in (QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS, QualificationCheck.BUILD_AND_ARTIFACT):
        assert stage(q, name).status is StageStatus.NOT_RUN
        assert stage(q, name).limitations
    # five pillars; a pillar whose checks all did not run is NOT_RUN, never PASS
    assert [s.stage for s in q.stages] == list(QualificationStage) and len(q.checks) == len(QualificationCheck)
    assert {s.stage: s.status for s in q.stages}[QualificationStage.FAULT_SENSITIVITY] is StageStatus.NOT_RUN


def test_post_apply_verifies_applied_state(session, calc_project):
    write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
    result = qualify_candidate(session)
    approval = Approval(frozenset({"tests/test_strong.py"}), approved_by="reviewer")
    applied = apply_approved(session, result, approval)
    assert file_digest(calc_project / "tests" / "test_strong.py") == file_digest(session.workspace / "tests" / "test_strong.py")
    assert applied.evidence.label == "applied"
    assert applied.evidence.runs[0].status is StageStatus.PASS
    assert "tests/test_strong.py::test_add_distinguishes_operands" in {
        inv.invocation_id for inv in applied.evidence.runs[0].invocations
    }
    assert applied.files_match_candidate


def test_session_apply_refuses_stale_baseline(session, calc_project):
    (session.workspace / "tests" / "test_calc.py").write_text(STRONG_TEST, encoding="utf-8")
    result = qualify_candidate(session)
    (calc_project / "tests" / "test_calc.py").write_text("def test_user():\n    assert 'mine'\n", encoding="utf-8")
    with pytest.raises(StaleBaselineError):
        apply_approved(session, result, Approval(frozenset({"tests/test_calc.py"}), "reviewer"))
    assert (calc_project / "tests" / "test_calc.py").read_text(encoding="utf-8") == "def test_user():\n    assert 'mine'\n"


def _with_workflow(root, steps):
    body = "".join(f"      - run: {step}\n" for step in steps)
    write(root / ".github" / "workflows" / "ci.yml", f"on: [push]\njobs:\n  test:\n    steps:\n{body}")


def test_pipeline_equivalent_partial_reproduction_is_unknown_not_pass(calc_project):
    _with_workflow(calc_project, ["pytest tests -q", "docker build .", "./scripts/deploy-preview"])
    session = start_improve(calc_project, python=PY)
    try:
        write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
        result = stage(qualify_candidate(session).qualification, QualificationCheck.PIPELINE_EQUIVALENT)
    finally:
        discard_session(session)
    assert result.status is StageStatus.UNKNOWN
    assert "reproduced 1/3" in result.summary
    assert any("docker build ." in item and "not authorized" in item for item in result.limitations)


def test_pipeline_equivalent_pass_requires_every_delivery_check(calc_project):
    _with_workflow(calc_project, ["python -m pytest tests -q --junitxml=report.xml"])
    session = start_improve(calc_project, python=PY)
    try:
        write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
        result = stage(qualify_candidate(session).qualification, QualificationCheck.PIPELINE_EQUIVALENT)
    finally:
        discard_session(session)
    assert result.status is StageStatus.PASS


def test_pipeline_equivalent_fails_when_reproduced_check_fails(calc_project):
    _with_workflow(calc_project, ["pytest tests -q"])
    session = start_improve(calc_project, python=PY)
    try:
        (session.workspace / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
        result = stage(qualify_candidate(session).qualification, QualificationCheck.PIPELINE_EQUIVALENT)
    finally:
        discard_session(session)
    assert result.status is StageStatus.FAIL


def test_pipeline_equivalent_without_pipeline_is_not_run(session):
    result = stage(qualify_candidate(session).qualification, QualificationCheck.PIPELINE_EQUIVALENT)
    assert result.status is StageStatus.NOT_RUN
    assert result.limitations


def test_project_without_runner_adapter_is_unknown_not_green(tmp_path):
    root = tmp_path / "custom"
    write(root / "Makefile", "check:\n\t./run-proprietary-checks\n")
    session = start_improve(root, python=PY)
    try:
        write(session.workspace / "checks" / "new.rule", "x\n")
        q = qualify_candidate(session).qualification
    finally:
        discard_session(session)
    assert stage(q, QualificationCheck.CANDIDATE_TESTS).status is StageStatus.UNKNOWN
    assert stage(q, QualificationCheck.ORIGINAL_REGRESSION).status is StageStatus.UNKNOWN
    assert not any(s.status is StageStatus.PASS for s in q.checks)
