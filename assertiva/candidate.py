from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CandidateChangeKind(str, Enum):
    ADD = "ADD"
    MODIFY = "MODIFY"
    RETIRE_CANDIDATE = "RETIRE_CANDIDATE"


class MetricDirection(str, Enum):
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    CONTEXTUAL = "CONTEXTUAL"
    INFORMATIONAL = "INFORMATIONAL"


class DeltaState(str, Enum):
    IMPROVED = "IMPROVED"
    REGRESSED = "REGRESSED"
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    UNKNOWN = "UNKNOWN"


class QualificationStage(str, Enum):
    STATIC_AND_DISCOVERY = "STATIC_AND_DISCOVERY"
    CANDIDATE_TESTS = "CANDIDATE_TESTS"
    ORIGINAL_REGRESSION = "ORIGINAL_REGRESSION"
    COVERAGE_AND_ORACLES = "COVERAGE_AND_ORACLES"
    NEGATIVE_PATHS = "NEGATIVE_PATHS"
    MUTATION_OR_NEGATIVE_CONTROLS = "MUTATION_OR_NEGATIVE_CONTROLS"
    PIPELINE_EQUIVALENT = "PIPELINE_EQUIVALENT"
    BUILD_AND_ARTIFACT = "BUILD_AND_ARTIFACT"
    PREVIEW_DEPLOY = "PREVIEW_DEPLOY"
    STABILITY_AND_COST = "STABILITY_AND_COST"


class StageStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MetricObservation:
    name: str
    value: float | int | None
    direction: MetricDirection
    unit: str | None = None
    evidence_tier: str | None = None
    provenance: str | None = None


@dataclass(frozen=True)
class MetricDelta:
    name: str
    baseline: float | int | None
    candidate: float | int | None
    state: DeltaState
    unit: str | None = None
    note: str | None = None  # why a delta is not directional (e.g. a changed denominator)


@dataclass(frozen=True)
class CandidateTestChange:
    change_id: str
    path: str
    kind: CandidateChangeKind
    reason: str
    original_fingerprint: str | None = None
    candidate_fingerprint: str | None = None
    original_preserved: bool = True
    human_approval_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.human_approval_required:
            raise ValueError("candidate project changes require human approval")
        if self.kind is CandidateChangeKind.RETIRE_CANDIDATE and not self.original_preserved:
            raise ValueError("retirement candidates must preserve the original until approval")


@dataclass(frozen=True)
class QualificationStageResult:
    stage: QualificationStage
    status: StageStatus
    summary: str
    evidence_refs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass
class CandidateQualification:
    changes: list[CandidateTestChange] = field(default_factory=list)
    metric_deltas: list[MetricDelta] = field(default_factory=list)
    stages: list[QualificationStageResult] = field(default_factory=list)

    @property
    def ready_for_review(self) -> bool:
        terminal_bad = {StageStatus.FAIL, StageStatus.BLOCKED}
        return bool(self.stages) and not any(stage.status in terminal_bad for stage in self.stages)


def compare_metric(baseline: MetricObservation, candidate: MetricObservation) -> MetricDelta:
    if baseline.name != candidate.name:
        raise ValueError("metric names must match")
    if baseline.direction is not candidate.direction:
        raise ValueError("metric directions must match")

    if baseline.value is None or candidate.value is None:
        state = DeltaState.UNKNOWN
    elif baseline.value == candidate.value:
        state = DeltaState.UNCHANGED
    elif baseline.direction is MetricDirection.HIGHER_IS_BETTER:
        state = DeltaState.IMPROVED if candidate.value > baseline.value else DeltaState.REGRESSED
    elif baseline.direction is MetricDirection.LOWER_IS_BETTER:
        state = DeltaState.IMPROVED if candidate.value < baseline.value else DeltaState.REGRESSED
    else:
        state = DeltaState.CHANGED

    return MetricDelta(
        name=baseline.name,
        baseline=baseline.value,
        candidate=candidate.value,
        state=state,
        unit=baseline.unit or candidate.unit,
    )


def compare_metric_sets(
    baseline: dict[str, MetricObservation],
    candidate: dict[str, MetricObservation],
) -> list[MetricDelta]:
    names = sorted(set(baseline) | set(candidate))
    deltas: list[MetricDelta] = []
    for name in names:
        before = baseline.get(name)
        after = candidate.get(name)
        if before is None or after is None:
            deltas.append(
                MetricDelta(
                    name=name,
                    baseline=before.value if before else None,
                    candidate=after.value if after else None,
                    state=DeltaState.UNKNOWN,
                    unit=(before.unit if before else None) or (after.unit if after else None),
                )
            )
            continue
        deltas.append(compare_metric(before, after))
    return deltas
