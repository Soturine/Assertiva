"""Measure one project state (baseline / candidate / applied) and compare states.

Every measurement runs inside a disposable copy, so test side effects never reach the
measured directory. Metrics carry an explicit direction; there is no aggregate score.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .adapters import runner_adapters
from .candidate import MetricDelta, MetricDirection, MetricObservation, StageStatus, compare_metric_sets
from .models import CoverageSummary, Outcome, RunEvidence, TestInvocation
from .workspace import snapshot


@dataclass(frozen=True)
class NegativeControl:
    """A deliberate, behavior-breaking edit the tests that claim `claim` must detect."""

    control_id: str
    path: str
    find: str
    replace: str
    claim: str
    tests: tuple[str, ...] = ()


class ControlOutcome(str, Enum):
    KILLED = "KILLED"
    SURVIVED = "SURVIVED"
    INVALID = "INVALID"


@dataclass(frozen=True)
class NegativeControlResult:
    control_id: str
    claim: str
    outcome: ControlOutcome
    detail: str


@dataclass
class StateEvidence:
    label: str
    observed_in: str
    runs: list[RunEvidence] = field(default_factory=list)
    static: dict[str, int] = field(default_factory=dict)
    negative_controls: list[NegativeControlResult] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def invocation_ids(self) -> set[str]:
        return {inv.invocation_id for run in self.runs for inv in run.invocations}


def run_negative_control(source: Path, control: NegativeControl, adapters: list) -> NegativeControlResult:
    def result(outcome: ControlOutcome, detail: str) -> NegativeControlResult:
        return NegativeControlResult(control.control_id, control.claim, outcome, detail)

    if not adapters:
        return result(ControlOutcome.INVALID, "no runner adapter can execute this project")
    copy = snapshot(source)
    try:
        target = copy / control.path
        text = target.read_text(encoding="utf-8") if target.is_file() else ""
        if text.count(control.find) != 1:
            return result(ControlOutcome.INVALID, f"expected exactly one occurrence of the target in {control.path}")
        target.write_text(text.replace(control.find, control.replace), encoding="utf-8")
        runs = [adapter.run(copy, args=list(control.tests)) for adapter in adapters]
    finally:
        shutil.rmtree(copy, ignore_errors=True)

    if any(run.collection_errors for run in runs):
        return result(ControlOutcome.INVALID, "the control broke collection/compilation instead of behavior")
    killers = [
        inv.invocation_id
        for run in runs
        for inv in run.invocations
        if inv.outcome in (Outcome.FAILED, Outcome.ERROR)
    ]
    if killers:
        return result(ControlOutcome.KILLED, "detected by " + ", ".join(sorted(killers)[:5]))
    if all(run.status is StageStatus.PASS for run in runs):
        return result(ControlOutcome.SURVIVED, "tests stayed green with the behavior deliberately broken")
    return result(ControlOutcome.INVALID, "runner did not produce a usable result: " + ", ".join(r.status.value for r in runs))


def measure(
    source: str | Path,
    label: str,
    observed_in: str,
    python: str | None = None,
    negative_controls: list[NegativeControl] | tuple = (),
) -> StateEvidence:
    source = Path(source)
    adapters = runner_adapters(source, python)
    state = StateEvidence(label=label, observed_in=observed_in)
    if not adapters:
        state.limitations.append("no executable runner adapter recognized this project; test evidence is UNKNOWN")
    copy = snapshot(source)
    try:
        for adapter in adapters:
            state.runs.append(adapter.run(copy, coverage=True))
            for name, value in adapter.static_signals(copy).items():
                state.static[name] = state.static.get(name, 0) + value
    finally:
        shutil.rmtree(copy, ignore_errors=True)
    state.negative_controls = [run_negative_control(source, control, adapters) for control in negative_controls]
    return state


def _coverage(state: StateEvidence) -> CoverageSummary | None:
    summaries = [run.coverage for run in state.runs if run.coverage]
    return summaries[0] if len(summaries) == 1 else None


def state_metrics(state: StateEvidence) -> dict[str, MetricObservation]:
    metrics: dict[str, MetricObservation] = {}

    def add(name: str, value: Any, direction: MetricDirection, unit: str | None = None, tier: str = "E1") -> None:
        metrics[name] = MetricObservation(name, value, direction, unit, tier, f"{state.label}:{state.observed_in}")

    if state.runs:
        invocations = [inv for run in state.runs for inv in run.invocations]
        add("test_invocations", len(invocations), MetricDirection.CONTEXTUAL)
        add("test_declarations", len({inv.declaration_id for inv in invocations}), MetricDirection.CONTEXTUAL)
        add("inherited_materializations", sum(inv.inherited for inv in invocations), MetricDirection.CONTEXTUAL)
        add("passed", sum(inv.outcome is Outcome.PASSED for inv in invocations), MetricDirection.CONTEXTUAL)
        add("failed", sum(inv.outcome is Outcome.FAILED for inv in invocations), MetricDirection.LOWER_IS_BETTER)
        add("errors", sum(inv.outcome is Outcome.ERROR for inv in invocations), MetricDirection.LOWER_IS_BETTER)
        add("collection_errors", sum(len(run.collection_errors) for run in state.runs), MetricDirection.LOWER_IS_BETTER)
        add("skipped", sum(inv.outcome is Outcome.SKIPPED for inv in invocations), MetricDirection.CONTEXTUAL)
        add("xfailed", sum(inv.outcome is Outcome.XFAILED for inv in invocations), MetricDirection.CONTEXTUAL)
        add("xpassed", sum(inv.outcome is Outcome.XPASSED for inv in invocations), MetricDirection.LOWER_IS_BETTER)
        wall = [run.wall_clock_s for run in state.runs]
        add("wall_clock_s", round(sum(wall), 3) if None not in wall else None, MetricDirection.CONTEXTUAL, "s")
    coverage = _coverage(state)
    if coverage:
        add("line_coverage", coverage.line_percent, MetricDirection.HIGHER_IS_BETTER, "%")
        add("branch_coverage", coverage.branch_percent, MetricDirection.HIGHER_IS_BETTER, "%")
    static_directions = {
        "weak_oracle_tests": MetricDirection.LOWER_IS_BETTER,
        "broad_error_expectations": MetricDirection.LOWER_IS_BETTER,
        "error_status_only_tests": MetricDirection.LOWER_IS_BETTER,
        "expected_error_contracts": MetricDirection.CONTEXTUAL,
    }
    for name, value in state.static.items():
        add(name, value, static_directions.get(name, MetricDirection.INFORMATIONAL), tier="E3")
    if state.negative_controls:
        valid = [r for r in state.negative_controls if r.outcome is not ControlOutcome.INVALID]
        add("negative_controls_killed", sum(r.outcome is ControlOutcome.KILLED for r in valid), MetricDirection.HIGHER_IS_BETTER)
        add("negative_controls_survived", sum(r.outcome is ControlOutcome.SURVIVED for r in valid), MetricDirection.LOWER_IS_BETTER)
        add("negative_controls_invalid", len(state.negative_controls) - len(valid), MetricDirection.LOWER_IS_BETTER)
    return metrics


def compare_states(before: StateEvidence, after: StateEvidence) -> list[MetricDelta]:
    baseline, candidate = state_metrics(before), state_metrics(after)
    # Runtime is only better/worse when the same invocations ran; otherwise it is contextual.
    if "wall_clock_s" in baseline and "wall_clock_s" in candidate and before.invocation_ids() == after.invocation_ids():
        for metrics in (baseline, candidate):
            old = metrics["wall_clock_s"]
            metrics["wall_clock_s"] = MetricObservation(old.name, old.value, MetricDirection.LOWER_IS_BETTER, old.unit, old.evidence_tier, old.provenance)
    return compare_metric_sets(baseline, candidate)


# --- JSON persistence -----------------------------------------------------------------

def to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    return value


def _run_from(data: dict) -> RunEvidence:
    run = RunEvidence(**{**data, "status": StageStatus(data["status"]), "invocations": [], "coverage": None})
    run.coverage = CoverageSummary(**data["coverage"]) if data.get("coverage") else None
    run.invocations = [
        TestInvocation(**{
            **inv,
            "markers": tuple(inv["markers"]),
            "source_paths": tuple(inv["source_paths"]),
            "outcome": Outcome(inv["outcome"]) if inv["outcome"] else None,
        })
        for inv in data["invocations"]
    ]
    return run


def state_from_dict(data: dict) -> StateEvidence:
    return StateEvidence(
        label=data["label"],
        observed_in=data["observed_in"],
        runs=[_run_from(run) for run in data["runs"]],
        static=dict(data["static"]),
        negative_controls=[
            NegativeControlResult(**{**r, "outcome": ControlOutcome(r["outcome"])}) for r in data["negative_controls"]
        ],
        limitations=list(data["limitations"]),
    )
