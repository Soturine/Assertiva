"""Measure one project state (baseline / candidate / applied) and compare states.

Every measurement runs inside a disposable copy, so test side effects never reach the
measured directory. Metrics carry an explicit direction; there is no aggregate score.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .adapters import artifact_adapters, runner_adapters
from .candidate import MetricDelta, MetricDirection, MetricObservation, StageStatus, compare_metric_sets
from .models import (
    DETECTED,
    ArtifactCheck,
    ArtifactEvidence,
    BudgetDecision,
    CoverageSummary,
    MutantRecord,
    MutantStatus,
    MutationRun,
    Outcome,
    RunEvidence,
    TestInvocation,
)
from .process import execution_refusal, scoped, traced_stage
from .workspace import boundary_report, remove_tree, snapshot


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
    mutation: list[MutationRun] = field(default_factory=list)
    artifacts: list[ArtifactEvidence] = field(default_factory=list)
    budget: list[BudgetDecision] = field(default_factory=list)
    negative_paths: dict[str, list[str]] = field(default_factory=dict)  # test id -> dimensions (E3)

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
        remove_tree(copy)

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


def mutant_label(m: MutantRecord) -> str:
    where = f"{m.path}:{m.line}" if m.path else m.mutant_id
    return f"{where} {m.operator or ''}{f' ({m.replacement})' if m.replacement else ''}".strip()


def attach_mutation(state: StateEvidence, run: MutationRun, state_dir: str | Path) -> MutationRun:
    """Attach a mutation report to a state, checking it against that state's sources when possible."""
    if run.error is None and run.sources:
        def norm(text: str) -> str:
            return text.replace("\r\n", "\n")

        mismatched = [
            path for path, source in run.sources.items()
            if not (Path(state_dir) / path).is_file()
            or norm((Path(state_dir) / path).read_text(encoding="utf-8", errors="replace")) != norm(source)
        ]
        run.matches_state = not mismatched
        if mismatched:
            run.limitations.append(f"report source does not match the {state.label} state: " + ", ".join(sorted(mismatched)[:5]))
    state.mutation.append(run)
    return run


@scoped
def measure(
    source: str | Path,
    label: str,
    observed_in: str,
    python: str | None = None,
    negative_controls: list[NegativeControl] | tuple = (),
    artifacts: bool = True,
    reason: str = "state measurement",
) -> StateEvidence:
    source = Path(source)
    adapters = runner_adapters(source, python)
    state = StateEvidence(label=label, observed_in=observed_in)
    escaping = boundary_report(source)["external_links"]
    if escaping:
        state.limitations.append(
            "project links point outside its root (" + ", ".join(escaping[:5]) + "); executions may reach their targets"
        )
    if not adapters:
        state.limitations.append("no executable runner adapter recognized this project; test evidence is UNKNOWN")
    refusal = execution_refusal()
    state.budget.append(BudgetDecision(
        "tests",
        "BLOCKED" if refusal and adapters else ("EXECUTED" if adapters else "NOT_RUN"),
        refusal if refusal and adapters else (reason if adapters else "no runner adapter supports this project"),
    ))
    copy = snapshot(source)
    try:
        for adapter in adapters:
            with traced_stage(f"{label}:{adapter.adapter_id}"):
                state.runs.append(adapter.run(copy, coverage=True))
            for name, value in adapter.static_signals(copy).items():
                state.static[name] = state.static.get(name, 0) + value
            state.negative_paths.update(adapter.static_negative_paths(copy))
    finally:
        remove_tree(copy)
    with traced_stage(f"{label}:negative-controls"):
        state.negative_controls = [run_negative_control(source, control, adapters) for control in negative_controls]
    if artifacts:
        for adapter in artifact_adapters(source, python):
            with traced_stage(f"{label}:{adapter.adapter_id}"):
                evidence = adapter.qualify(source)
            state.artifacts.append(evidence)
            blocked = evidence.status is StageStatus.BLOCKED and evidence.limitations
            state.budget.append(BudgetDecision(
                f"artifact:{adapter.adapter_id}", "BLOCKED" if blocked else "EXECUTED",
                evidence.limitations[0] if blocked else f"{adapter.adapter_id} builds a deliverable for this project",
            ))
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
        "negative_path_tests": MetricDirection.CONTEXTUAL,
        "negative_paths_without_contract_detail": MetricDirection.LOWER_IS_BETTER,
        "negative_paths_with_state_after_rejection": MetricDirection.HIGHER_IS_BETTER,
    }
    for name, value in state.static.items():
        add(name, value, static_directions.get(name, MetricDirection.INFORMATIONAL), tier="E3")
    if state.negative_controls:
        valid = [r for r in state.negative_controls if r.outcome is not ControlOutcome.INVALID]
        add("negative_controls_killed", sum(r.outcome is ControlOutcome.KILLED for r in valid), MetricDirection.HIGHER_IS_BETTER)
        add("negative_controls_survived", sum(r.outcome is ControlOutcome.SURVIVED for r in valid), MetricDirection.LOWER_IS_BETTER)
        add("negative_controls_invalid", len(state.negative_controls) - len(valid), MetricDirection.LOWER_IS_BETTER)
    usable = [run for run in state.mutation if run.error is None and run.matches_state is not False]
    if usable:
        tier = "E0"
        add("mutation_evaluated", sum(r.evaluated for r in usable), MetricDirection.CONTEXTUAL, tier=tier)
        add("mutation_killed", sum(sum(r.count(s) for s in DETECTED) for r in usable), MetricDirection.HIGHER_IS_BETTER, tier=tier)
        add("mutation_survived", sum(r.count(MutantStatus.SURVIVED) for r in usable), MetricDirection.LOWER_IS_BETTER, tier=tier)
        add("mutation_no_coverage", sum(r.count(MutantStatus.NO_COVERAGE) for r in usable), MetricDirection.LOWER_IS_BETTER, tier=tier)
    if state.artifacts:
        statuses = {a.status for a in state.artifacts}
        value = 0 if StageStatus.FAIL in statuses else (1 if statuses == {StageStatus.PASS} else None)
        add("artifact_qualified", value, MetricDirection.HIGHER_IS_BETTER, tier="E0")
    return metrics


_MUTATION_COUNTS = ("mutation_killed", "mutation_survived", "mutation_no_coverage")


def compare_states(before: StateEvidence, after: StateEvidence) -> list[MetricDelta]:
    baseline, candidate = state_metrics(before), state_metrics(after)
    # Runtime is only better/worse when the same invocations ran; otherwise it is contextual.
    if "wall_clock_s" in baseline and "wall_clock_s" in candidate and before.invocation_ids() == after.invocation_ids():
        for metrics in (baseline, candidate):
            old = metrics["wall_clock_s"]
            metrics["wall_clock_s"] = MetricObservation(old.name, old.value, MetricDirection.LOWER_IS_BETTER, old.unit, old.evidence_tier, old.provenance)
    # Mutation counts are only better/worse over the same number of evaluated mutants.
    evaluated = (baseline.get("mutation_evaluated"), candidate.get("mutation_evaluated"))
    if all(evaluated) and evaluated[0].value != evaluated[1].value:
        for metrics in (baseline, candidate):
            for name in _MUTATION_COUNTS:
                old = metrics[name]
                metrics[name] = MetricObservation(old.name, old.value, MetricDirection.CONTEXTUAL, old.unit, old.evidence_tier, old.provenance)
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
        negative_paths={k: list(v) for k, v in data.get("negative_paths", {}).items()},
        budget=[BudgetDecision(**d) for d in data.get("budget", [])],
        mutation=[
            MutationRun(**{
                **m,
                "mutants": [
                    MutantRecord(**{**r, "status": MutantStatus(r["status"]), "killed_by": tuple(r["killed_by"])})
                    for r in m["mutants"]
                ],
            })
            for m in data.get("mutation", [])
        ],
        artifacts=[
            ArtifactEvidence(**{
                **a,
                "status": StageStatus(a["status"]),
                "checks": [ArtifactCheck(**{**c, "status": StageStatus(c["status"])}) for c in a["checks"]],
            })
            for a in data.get("artifacts", [])
        ],
    )
