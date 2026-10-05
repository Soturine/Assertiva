import pytest

from assertiva.candidate import (
    CandidateChangeKind,
    CandidateTestChange,
    DeltaState,
    MetricDirection,
    MetricObservation,
    compare_metric,
    compare_metric_sets,
)


def obs(name, value, direction, unit=None):
    return MetricObservation(name=name, value=value, direction=direction, unit=unit)


def test_higher_is_better_metric_improves():
    delta = compare_metric(
        obs("branch_coverage", 62.0, MetricDirection.HIGHER_IS_BETTER, "%"),
        obs("branch_coverage", 78.0, MetricDirection.HIGHER_IS_BETTER, "%"),
    )
    assert delta.state is DeltaState.IMPROVED


def test_lower_is_better_metric_improves():
    delta = compare_metric(
        obs("weak_oracles", 18, MetricDirection.LOWER_IS_BETTER),
        obs("weak_oracles", 7, MetricDirection.LOWER_IS_BETTER),
    )
    assert delta.state is DeltaState.IMPROVED


def test_test_count_change_is_contextual_not_automatically_better():
    delta = compare_metric(
        obs("test_definitions", 100, MetricDirection.CONTEXTUAL),
        obs("test_definitions", 120, MetricDirection.CONTEXTUAL),
    )
    assert delta.state is DeltaState.CHANGED


def test_missing_metric_is_unknown_not_invented():
    deltas = compare_metric_sets(
        {"mutation_score": obs("mutation_score", None, MetricDirection.HIGHER_IS_BETTER, "%")},
        {"mutation_score": obs("mutation_score", 70.0, MetricDirection.HIGHER_IS_BETTER, "%")},
    )
    assert deltas[0].state is DeltaState.UNKNOWN


def test_retirement_candidate_requires_preserving_original():
    with pytest.raises(ValueError):
        CandidateTestChange(
            change_id="retire-1",
            path="tests/test_duplicate.py",
            kind=CandidateChangeKind.RETIRE_CANDIDATE,
            reason="candidate consolidation",
            original_preserved=False,
        )


def test_all_candidate_project_changes_require_human_approval():
    with pytest.raises(ValueError):
        CandidateTestChange(
            change_id="modify-1",
            path="tests/test_checkout.py",
            kind=CandidateChangeKind.MODIFY,
            reason="strengthen oracle",
            human_approval_required=False,
        )
