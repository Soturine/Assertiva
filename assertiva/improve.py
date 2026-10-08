"""`assertiva improve` orchestration.

AUDIT -> baseline snapshot -> isolated candidate -> candidate changes -> qualification
-> baseline vs candidate -> explicit human approval -> approved apply -> post-apply
verification. The original project is read-only (and verified as such) until apply.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .adapters import runner_adapters
from .adapters.coverage_reports import load_coverage_report
from .adapters.mutation import load_mutation_report
from .candidate import (
    CandidateChangeKind,
    CandidateQualification,
    CandidateTestChange,
    DeltaState,
    PILLARS,
    CheckResult,
    QualificationCheck,
    QualificationStageResult,
    StageStatus,
    pillar,
)
from .config import load_config
from .evidence import (
    ControlOutcome,
    NegativeControl,
    NegativeControlResult,
    StateEvidence,
    attach_mutation,
    mutant_label,
    compare_states,
    measure,
    run_negative_control,
    runnable_copy,
    state_from_dict,
    to_jsonable,
)
from .history import Stability, classify_attempts, record_state
from .models import BudgetDecision, MutantStatus, Outcome, StabilityEvidence, StabilityRecord
from .process import scoped, traced_stage
from .reproduction import reproduce_check
from .verification import GateMode, VerificationOrigin, discover_surface
from .workspace import (
    Approval,
    Baseline,
    apply_changes,
    capture_baseline,
    change_set,
    create_workspace,
    entry_digest,
    read_only_guard,
    remove_tree,
    remove_workspace,
    snapshot,
    state_dir,
)

_SESSION = "session.json"


class SessionExistsError(RuntimeError):
    pass


@dataclass
class ImproveSession:
    root: Path
    directory: Path
    baseline: Baseline
    workspace: Path
    baseline_copy: Path
    python: str | None
    baseline_evidence: StateEvidence

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / _SESSION).write_text(json.dumps(to_jsonable(self), indent=2), encoding="utf-8")


@dataclass
class QualificationResult:
    qualification: CandidateQualification
    baseline_evidence: StateEvidence
    candidate_evidence: StateEvidence
    baseline_controls: list[NegativeControlResult] = field(default_factory=list)
    stability: StabilityEvidence = field(default_factory=StabilityEvidence)
    timings: list[dict] = field(default_factory=list)
    budget: list[BudgetDecision] = field(default_factory=list)
    history: dict | None = None


@dataclass
class AppliedResult:
    applied: list[CandidateTestChange]
    evidence: StateEvidence
    files_match_candidate: bool


def load_session(root: str | Path) -> ImproveSession | None:
    path = state_dir(root, "sessions") / _SESSION
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ImproveSession(
        root=Path(data["root"]),
        directory=Path(data["directory"]),
        baseline=Baseline(**data["baseline"]),
        workspace=Path(data["workspace"]),
        baseline_copy=Path(data["baseline_copy"]),
        python=data["python"],
        baseline_evidence=state_from_dict(data["baseline_evidence"]),
    )


@scoped
def start_improve(root: str | Path, python: str | None = None) -> ImproveSession:
    root = Path(root).resolve()
    if load_session(root) is not None:
        raise SessionExistsError(f"an improve session is already active for {root}")
    directory = state_dir(root, "sessions")
    with read_only_guard(root):
        baseline = capture_baseline(root)
        workspace = create_workspace(baseline)
        baseline_copy = snapshot(root, directory / "baseline")
        baseline_evidence = measure(baseline_copy, "baseline", "isolated-baseline-copy", python, reason="baseline for improve", origin=root)
        record_state(root, "improve", "baseline", baseline.digest, baseline.revision, baseline_evidence.runs,
                     coverage=_coverage_counts(baseline_evidence), artifacts=_artifact_identity(baseline_evidence))
    session = ImproveSession(root, directory, baseline, workspace, baseline_copy, python, baseline_evidence)
    session.save()
    return session


def discard_session(session: ImproveSession) -> None:
    remove_workspace(session.baseline, session.workspace)
    remove_tree(session.directory)


def _stage(check: QualificationCheck, status: StageStatus, summary: str, *limitations: str) -> CheckResult:
    return CheckResult(check, status, summary, limitations=tuple(limitations))


def _invocations(state: StateEvidence):
    return [inv for run in state.runs for inv in run.invocations]


def _execution_stage(changes: list[CandidateTestChange], candidate: StateEvidence) -> CheckResult:
    """EXECUTION: the candidate's tests are collected natively and the added/modified ones run without failure.

    One check for one claim: a missing runner, a blocked run or a collection error is reported once."""
    stage = QualificationCheck.CANDIDATE_TESTS
    if not candidate.runs:
        return _stage(stage, StageStatus.UNKNOWN, "no runner adapter could discover candidate tests", *candidate.limitations)
    changed = {c.path for c in changes if c.kind is not CandidateChangeKind.RETIRE_CANDIDATE}
    errors = [e for run in candidate.runs for e in run.collection_errors]
    in_changed = [e for run in candidate.runs for e in run.collection_errors if run.metadata.get("error_sources", {}).get(e) in changed]
    if in_changed:
        return _stage(stage, StageStatus.FAIL, "candidate test files failed to collect: " + ", ".join(in_changed))
    if errors:
        return _stage(stage, StageStatus.FAIL, "collection errors: " + ", ".join(errors[:10]))
    if any(run.status is StageStatus.BLOCKED for run in candidate.runs):
        return _stage(stage, StageStatus.BLOCKED, "runner could not execute", *[l for r in candidate.runs for l in r.limitations])
    invocations = _invocations(candidate)
    if not invocations:
        return _stage(stage, StageStatus.UNKNOWN, "no candidate invocations were collected")
    touched = [inv for inv in invocations if changed & set(inv.source_paths)]
    if not touched:  # nothing to execute beyond discovery, which succeeded
        return _stage(stage, StageStatus.PASS, f"{len(invocations)} invocations collected natively without errors")
    bad = sorted(inv.invocation_id for inv in touched if inv.outcome in (Outcome.FAILED, Outcome.ERROR))
    if bad:
        return _stage(stage, StageStatus.FAIL, "failing candidate invocations: " + ", ".join(bad[:10]))
    if all(inv.outcome in (Outcome.SKIPPED, Outcome.NOT_RUN, None) for inv in touched):
        return _stage(stage, StageStatus.UNKNOWN, "every candidate invocation was skipped or not run")
    return _stage(stage, StageStatus.PASS, f"{len(touched)} added/modified invocations executed without failure")


def _regression_stage(session: ImproveSession, changes: list[CandidateTestChange], candidate: StateEvidence) -> CheckResult:
    """Run the unchanged original tests against the candidate."""
    stage = QualificationCheck.ORIGINAL_REGRESSION
    baseline = session.baseline_evidence
    if not baseline.runs or not candidate.runs:
        return _stage(stage, StageStatus.UNKNOWN, "no runner adapter produced baseline/candidate execution evidence")
    protected = {inv.invocation_id for inv in _invocations(baseline) if inv.outcome is Outcome.PASSED}
    if not protected:
        return _stage(stage, StageStatus.UNKNOWN, "the baseline had no passing invocations to protect")
    test_sources = {path for inv in _invocations(baseline) for path in inv.source_paths}
    restore = [c.path for c in changes if c.kind is not CandidateChangeKind.ADD and c.path in test_sources]
    if restore:
        adapters = runner_adapters(session.workspace, session.python)
        copy = runnable_copy(session.workspace, adapters, session.root)
        try:
            for path in restore:
                (copy / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(session.baseline_copy / path, copy / path, follow_symlinks=False)
            runs = [adapter.run(copy) for adapter in adapters]
        finally:
            remove_tree(copy)
    else:
        runs = candidate.runs
    if any(run.status is StageStatus.BLOCKED for run in runs):
        return _stage(stage, StageStatus.BLOCKED, "original regression run could not execute")
    outcomes = {inv.invocation_id: inv.outcome for run in runs for inv in run.invocations}
    broken = sorted(i for i in protected if outcomes.get(i) is not Outcome.PASSED)
    restored = f" (original versions of {len(restore)} changed test files restored)" if restore else ""
    if broken:
        return _stage(stage, StageStatus.FAIL, "original tests no longer pass against the candidate: " + ", ".join(broken[:10]) + restored)
    return _stage(stage, StageStatus.PASS, f"all {len(protected)} originally passing invocations still pass{restored}")


_WEAK_NEGATIVE = {"ERROR_TYPE", "PROTOCOL_STATUS"}


def _coverage_stage(deltas) -> CheckResult:
    """Coverage counts and percentages, never a blind percentage comparison across populations."""
    stage = QualificationCheck.COVERAGE_AND_ORACLES
    by = {d.name: d for d in deltas}
    regressed = [d.name for d in deltas if d.name in ("line_coverage", "branch_coverage", "weak_oracle_tests") and d.state is DeltaState.REGRESSED]
    for kind in ("line", "branch"):
        covered, total = by.get(f"{kind}_covered"), by.get(f"{kind}_total")
        if covered and total and covered.state is DeltaState.REGRESSED and None not in (total.baseline, total.candidate) and total.candidate >= total.baseline:
            regressed.append(f"{kind}_covered")  # fewer covered over a population that did not shrink
    if regressed:
        return _stage(stage, StageStatus.FAIL, "regressed: " + ", ".join(sorted(set(regressed))))
    def ambiguous(kind: str) -> bool:  # covered up and missed down is better under every reading
        covered, total = by.get(f"{kind}_covered"), by.get(f"{kind}_total")
        if not covered or not total or None in (covered.baseline, covered.candidate, total.baseline, total.candidate):
            return True
        return not (covered.candidate >= covered.baseline
                    and total.candidate - covered.candidate <= total.baseline - covered.baseline)

    notes = [f"{d.name}: {d.note}" for d in deltas if d.note and d.name.endswith("_coverage") and ambiguous(d.name[: -len("_coverage")])]
    if notes:
        return _stage(stage, StageStatus.UNKNOWN, "coverage population changed; percentages are not comparable", *notes)
    present = {d.name for d in deltas if d.name in ("line_coverage", "branch_coverage", "weak_oracle_tests") and d.state is not DeltaState.UNKNOWN}
    if present != {"line_coverage", "branch_coverage", "weak_oracle_tests"}:
        return _stage(stage, StageStatus.UNKNOWN, "partial evidence: " + (", ".join(sorted(present)) or "none"),
                      "coverage or oracle signals were not measured for both states")
    return _stage(stage, StageStatus.PASS, "no regression in " + ", ".join(sorted(present)))


def _negative_path_stage(changes, candidate: StateEvidence, deltas) -> CheckResult:
    """Static failure-contract dimensions (E3) combined with runtime outcomes (E1)."""
    stage = QualificationCheck.NEGATIVE_PATHS
    provenance = "dimensions are static AST signals (E3); outcomes come from the native run (E1); rollback and external side effects are not evidenced"
    weakened = [
        d.name for d in deltas
        if d.name in {"broad_error_expectations", "error_status_only_tests", "negative_paths_without_contract_detail"}
        and d.state is DeltaState.REGRESSED
    ]
    if weakened:
        return _stage(stage, StageStatus.FAIL, "negative-path evidence weakened: " + ", ".join(weakened), provenance)
    changed = {c.path for c in changes if c.kind is not CandidateChangeKind.RETIRE_CANDIDATE}
    sources = {inv.materialization_id: set(inv.source_paths) for inv in _invocations(candidate)}
    touched = {tid: dims for tid, dims in candidate.negative_paths.items() if changed & sources.get(tid, set())}
    if not touched:
        return _stage(stage, StageStatus.UNKNOWN, "the candidate does not add or modify negative-path tests", provenance)
    outcomes: dict[str, set] = {}
    for inv in _invocations(candidate):
        outcomes.setdefault(inv.materialization_id, set()).add(inv.outcome)
    shallow = [tid for tid, dims in touched.items() if set(dims) <= _WEAK_NEGATIVE]
    not_passing = [tid for tid in touched if outcomes.get(tid) != {Outcome.PASSED}]
    summary = "; ".join(f"{tid}: {', '.join(dims) or 'any error'}" for tid, dims in sorted(touched.items()))
    if not_passing:
        return _stage(stage, StageStatus.UNKNOWN, summary + " | not passing at runtime: " + ", ".join(not_passing), provenance)
    if shallow:
        return _stage(stage, StageStatus.UNKNOWN, summary + " | only type/status observed: " + ", ".join(shallow), provenance)
    return _stage(stage, StageStatus.PASS, summary, provenance)


def _mutation_stage(candidate: StateEvidence) -> CheckResult:
    """Negative controls and mutation reports are separate evidence; both are reported."""
    stage = QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS
    controls, runs = candidate.negative_controls, candidate.mutation
    if not controls and not runs:
        return _stage(
            stage, StageStatus.NOT_RUN, "no negative controls or mutation evidence were provided",
            "a green suite was not challenged with deliberately broken behavior",
        )
    failures, unknown, limitations, passed = [], [], [], []
    survived = [r.control_id for r in controls if r.outcome is ControlOutcome.SURVIVED]
    if survived:
        failures.append("NEGATIVE_CONTROL_SURVIVED: " + ", ".join(survived))
    invalid = [r for r in controls if r.outcome is ControlOutcome.INVALID]
    if invalid:
        unknown.append("invalid controls: " + ", ".join(r.control_id for r in invalid))
        limitations += [r.detail for r in invalid]
    if controls and not survived and not invalid:
        passed.append(f"{len(controls)} negative controls killed")
    blocked = [run for run in runs if run.error]
    for run in runs:
        limitations += [f"{run.source}: {item}" for item in run.limitations]
        if run.error:
            limitations.append(f"{run.source}: unreadable mutation report ({run.error})")
            continue
        if run.matches_state is False:
            unknown.append(f"mutation report {run.source} was produced for different source")
            continue
        tool = run.tool or "mutation report"
        survivors = run.survivors()
        if run.count(MutantStatus.SURVIVED):
            shown = ", ".join(mutant_label(m) for m in survivors[:5]) if survivors else f"{run.count(MutantStatus.SURVIVED)} survived (no per-mutant identity)"
            failures.append(f"MUTATION_SURVIVOR ({tool}): {shown}")
        if run.count(MutantStatus.NO_COVERAGE):
            failures.append(f"MUTATION_NO_COVERAGE ({tool}): {run.count(MutantStatus.NO_COVERAGE)} mutants not covered by any test")
        if run.count(MutantStatus.UNKNOWN):
            unknown.append(f"{tool}: {run.count(MutantStatus.UNKNOWN)} mutants with unknown/pending status")
        if not run.evaluated:
            unknown.append(f"{tool}: no evaluated mutants")
        elif not run.count(MutantStatus.SURVIVED) and not run.count(MutantStatus.NO_COVERAGE):
            passed.append(f"{tool}: all {run.evaluated} evaluated mutants detected")
    if failures:
        return _stage(stage, StageStatus.FAIL, "; ".join(failures), *limitations)
    if blocked:
        return _stage(stage, StageStatus.BLOCKED, "mutation evidence could not be read", *limitations)
    if unknown:
        return _stage(stage, StageStatus.UNKNOWN, "; ".join(unknown + passed), *limitations)
    return _stage(stage, StageStatus.PASS, "; ".join(passed), *limitations)


def _artifact_stage(candidate: StateEvidence) -> CheckResult:
    stage = QualificationCheck.BUILD_AND_ARTIFACT
    if not candidate.artifacts:
        return _stage(stage, StageStatus.NOT_RUN, "no build/package adapter supports this project", "source-tree tests do not prove a built artifact")
    parts, limitations = [], []
    for a in candidate.artifacts:
        checks = ", ".join(f"{c.name} {c.status.value}" for c in a.checks)
        parts.append(f"{a.kind} {a.artifact or '(not built)'}" + (f" sha256 {a.sha256[:12]}" if a.sha256 else "") + f": {checks}")
        limitations += a.limitations + [f"{c.name}: {c.detail}" for c in a.checks if c.status is not StageStatus.PASS]
        if a.omitted_files:
            limitations.append("files in packaged directories missing from the artifact: " + ", ".join(a.omitted_files[:10]))
    statuses = [a.status for a in candidate.artifacts]
    for status in (StageStatus.FAIL, StageStatus.BLOCKED, StageStatus.UNKNOWN, StageStatus.NOT_RUN):
        if status in statuses:
            return _stage(stage, status, "; ".join(parts), *limitations)
    return _stage(stage, StageStatus.PASS, "; ".join(parts), *limitations)


def _pipeline_stage(session: ImproveSession, authorized: set[str], candidate: StateEvidence, budget: list) -> CheckResult:
    """Reproduce the candidate's own delivery checks: DISCOVERED -> AUTHORIZED -> EXECUTED."""
    stage = QualificationCheck.PIPELINE_EQUIVALENT
    delivery = discover_surface(session.workspace).by_origin(VerificationOrigin.CI)
    if not delivery:
        return _stage(stage, StageStatus.NOT_RUN, "no delivery pipeline was discovered", "delivery-path verification is UNKNOWN")
    adapters = runner_adapters(session.workspace, session.python)
    config = load_config(session.root)
    baseline = session.baseline
    revision = {"label": "candidate workspace from", "digest": baseline.digest, "vcs_revision": baseline.revision, "dirty": True}
    gating: list[StageStatus] = []
    reproduced, partial = 0, False
    notes: list[str] = []
    copies: list[Path] = []

    def copy() -> Path:
        if not copies:
            copies.append(runnable_copy(session.workspace, adapters, session.root))
        return copies[0]

    try:
        for check in delivery:
            label = f"{check.command or check.tool or check.check_id} [{check.kind.value}]"
            done = reproduce_check(check, copy, adapters, session.python, revision,
                                   lambda c: c.check_id in authorized or config.authorizes(c), candidate.runs,
                                   authorize_hint=f" (assertiva improve --run-check {check.check_id})")
            budget.extend(BudgetDecision(QualificationCheck.PIPELINE_EQUIVALENT.value, d.decision, f"{label}: {d.reason}")
                          for d in done.budget)
            if not done.executed:
                notes.append(f"not reproduced: {label}: {done.record['detail']}")
                continue
            status, detail = done.status, done.record["detail"]
            reproduced += 1
            if check.gate in (GateMode.ALLOWED_FAILURE, GateMode.ADVISORY) and status is not StageStatus.PASS:
                notes.append(f"{label}: {status.value} but allowed to fail ({check.gate.value}): {detail}")
            else:
                gating.append(status)
                notes.append(f"{label}: {status.value}: {detail}")
            if check.metadata.get("matrix"):
                partial = True
                notes.append(f"{label}: only the local environment was reproduced, not matrix {check.metadata['matrix']}")
            if check.metadata.get("condition"):
                notes.append(f"{label}: condition `{check.metadata['condition']}` was not evaluated")
    finally:
        for path in copies:
            remove_tree(path)
    summary = f"reproduced {reproduced}/{len(delivery)} delivery checks locally"
    if StageStatus.FAIL in gating:
        return _stage(stage, StageStatus.FAIL, summary + "; a reproduced gating check failed", *notes)
    if StageStatus.BLOCKED in gating:
        return _stage(stage, StageStatus.BLOCKED, summary + "; a reproduced check could not run", *notes)
    if reproduced < len(delivery) or partial or any(s is not StageStatus.PASS for s in gating):
        return _stage(stage, StageStatus.UNKNOWN, summary, *notes)
    return _stage(stage, StageStatus.PASS, summary + "; all gating checks passed", *notes)


def _coverage_counts(state: StateEvidence) -> dict | None:
    summary = next((c for c in [*state.coverage, *(r.coverage for r in state.runs)] if c and c.error is None), None)
    return {"tool": summary.tool, "counts": summary.counts} if summary else None


def _artifact_identity(state: StateEvidence) -> list[dict]:
    return [{"kind": a.kind, "artifact": a.artifact, "sha256": a.sha256, "status": a.status.value} for a in state.artifacts]


MAX_STABILITY_INVOCATIONS = 50
MAX_STABILITY_RERUNS = 2


def _stability(session: ImproveSession, changes, candidate: StateEvidence, reruns: int) -> StabilityEvidence:
    """Bounded reruns of relevant invocations. The first outcome is kept; later ones are added, never substituted."""
    evidence = StabilityEvidence()
    reruns = min(max(reruns, 0), MAX_STABILITY_RERUNS)
    adapters = runner_adapters(session.workspace, session.python)
    if not reruns or not adapters or not any(run.status is not StageStatus.BLOCKED for run in candidate.runs):
        return evidence
    changed = {c.path for c in changes if c.kind is not CandidateChangeKind.RETIRE_CANDIDATE}
    first = {inv.invocation_id: inv for inv in _invocations(candidate)}
    relevant = [
        iid for iid, inv in first.items()
        if changed & set(inv.source_paths) or inv.outcome in (Outcome.FAILED, Outcome.ERROR)
    ]
    if len(relevant) > MAX_STABILITY_INVOCATIONS:
        evidence.limitations.append(f"only the first {MAX_STABILITY_INVOCATIONS} of {len(relevant)} relevant invocations were rerun")
    selected = relevant[:MAX_STABILITY_INVOCATIONS]
    if not selected:
        return evidence
    later: dict[str, list] = {iid: [] for iid in selected}
    for _ in range(reruns):
        copy = runnable_copy(session.workspace, adapters, session.root)
        try:
            for adapter in adapters:
                run = adapter.run(copy, args=selected)
                evidence.commands.append(" ".join(run.command))
                for inv in run.invocations:
                    if inv.invocation_id in later:
                        later[inv.invocation_id].append(inv)
        finally:
            remove_tree(copy)
    evidence.attempts = 1 + reruns
    for iid in selected:
        attempts = [first[iid], *later[iid]]
        outcomes = tuple(inv.outcome for inv in attempts)
        evidence.records.append(StabilityRecord(iid, outcomes, tuple(inv.duration_s for inv in attempts), classify_attempts(outcomes).value))
        evidence.messages[iid] = tuple(inv.message for inv in attempts)
    return evidence


def _stability_stage(stability: StabilityEvidence, deltas) -> CheckResult:
    stage = QualificationCheck.STABILITY_AND_COST
    wall = next((d for d in deltas if d.name == "wall_clock_s"), None)
    cost = f"wall clock {wall.baseline}s -> {wall.candidate}s ({wall.state.value})" if wall else "wall clock unknown"
    bounds = ("absence of observed instability is not proof of stability", "order dependence was not measured", *stability.limitations)
    if not stability.records:
        return _stage(stage, StageStatus.NOT_RUN, f"no relevant invocation was rerun; {cost}", *bounds)
    unstable = Stability.OBSERVED_UNSTABLE_CURRENT_RUN.value
    by = {v: [r for r in stability.records if r.verdict == v] for v in (unstable, "INSUFFICIENT_EVIDENCE", "CONSISTENT_FAILURE")}
    if by[unstable]:
        shown = ", ".join(f"{r.invocation_id} ({'/'.join(o.value if o else '?' for o in r.outcomes)})" for r in by[unstable][:5])
        return _stage(stage, StageStatus.FAIL, f"{unstable}: {shown}; {cost}", *bounds)
    if by["INSUFFICIENT_EVIDENCE"] or by["CONSISTENT_FAILURE"]:
        notes = [f"{len(by['CONSISTENT_FAILURE'])} consistently failing (see CANDIDATE_TESTS)"] if by["CONSISTENT_FAILURE"] else []
        notes += [f"{len(by['INSUFFICIENT_EVIDENCE'])} with insufficient reruns"] if by["INSUFFICIENT_EVIDENCE"] else []
        return _stage(stage, StageStatus.UNKNOWN, "; ".join(notes) + f"; {cost}", *bounds)
    return _stage(
        stage, StageStatus.PASS,
        f"no instability observed in {stability.attempts} executions of {len(stability.records)} invocations; {cost}", *bounds,
    )


def _stages(session: ImproveSession, changes, candidate: StateEvidence, deltas, authorized: set[str], stability, timed, budget: list) -> list[QualificationStageResult]:
    plan = {
        QualificationCheck.CANDIDATE_TESTS: lambda: _execution_stage(changes, candidate),
        QualificationCheck.ORIGINAL_REGRESSION: lambda: _regression_stage(session, changes, candidate),
        QualificationCheck.COVERAGE_AND_ORACLES: lambda: _coverage_stage(deltas),
        QualificationCheck.NEGATIVE_PATHS: lambda: _negative_path_stage(changes, candidate, deltas),
        QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS: lambda: _mutation_stage(candidate),
        QualificationCheck.PIPELINE_EQUIVALENT: lambda: _pipeline_stage(session, authorized, candidate, budget),
        QualificationCheck.BUILD_AND_ARTIFACT: lambda: _artifact_stage(candidate),
        QualificationCheck.STABILITY_AND_COST: lambda: _stability_stage(stability, deltas),
    }
    return [pillar(stage, [timed(check.value, plan[check]) for check in checks]) for stage, checks in PILLARS.items()]


@scoped
def qualify_candidate(
    session: ImproveSession,
    negative_controls: list[NegativeControl] | None = None,
    mutation_reports: dict[str, str | Path] | None = None,
    authorized_checks: set[str] | None = None,
    stability_reruns: int = MAX_STABILITY_RERUNS,
    coverage_reports: dict[str, str | Path] | None = None,
) -> QualificationResult:
    """mutation_reports maps "baseline"/"candidate" to an existing mutation-tool report for that state."""
    controls = list(negative_controls or [])
    reports = dict(mutation_reports or {})
    unknown_states = set(reports) - {"baseline", "candidate"}
    if unknown_states:
        raise ValueError(f"mutation reports must target baseline or candidate, not {sorted(unknown_states)}")
    timings: list[dict] = []

    def timed(name, build):
        started = time.perf_counter()
        with traced_stage(name):
            value = build()
        timings.append({"stage": name, "duration_s": round(time.perf_counter() - started, 3)})
        return value

    changes = change_set(session.baseline, session.workspace)
    with read_only_guard(session.root):
        candidate = timed("candidate-measure", lambda: measure(session.workspace, "candidate", "isolated-candidate-copy", session.python, controls,
                                                         reason="candidate qualification", origin=session.root))
        adapters = runner_adapters(session.baseline_copy, session.python)
        baseline_controls = timed("baseline-controls", lambda: [run_negative_control(session.baseline_copy, c, adapters, session.root) for c in controls])
        baseline = StateEvidence(**{**vars(session.baseline_evidence), "negative_controls": baseline_controls, "mutation": [],
                                    "coverage": list(session.baseline_evidence.coverage)})
        if "baseline" in reports:
            attach_mutation(baseline, load_mutation_report(reports["baseline"]), session.baseline_copy)
        if "candidate" in reports:
            attach_mutation(candidate, load_mutation_report(reports["candidate"]), session.workspace)
        for state_name, report in (coverage_reports or {}).items():
            {"baseline": baseline, "candidate": candidate}[state_name].coverage.append(load_coverage_report(report))
        deltas = compare_states(baseline, candidate)
        budget: list[BudgetDecision] = []
        stability = timed("stability-reruns", lambda: _stability(session, changes, candidate, stability_reruns))
        budget.append(BudgetDecision(
            QualificationCheck.STABILITY_AND_COST.value,
            "EXECUTED" if stability.records else "NOT_RUN",
            f"reran {len(stability.records)} candidate-touched or failing invocations {stability.attempts - 1}x"
            if stability.records else "no relevant invocation to rerun, reruns disabled, or execution budget exhausted",
        ))
        stages = _stages(session, changes, candidate, deltas, set(authorized_checks or ()), stability, timed, budget)
    q = CandidateQualification(changes, deltas, stages)
    reruns = {}
    for r in stability.records:  # later attempts, kept beside the first outcome
        messages = stability.messages.get(r.invocation_id) or (None,) * len(r.outcomes)
        reruns[r.invocation_id] = list(zip(r.outcomes[1:], r.durations_s[1:], messages[1:]))
    history = record_state(
        session.root, "improve", "candidate", capture_baseline(session.workspace).digest, session.baseline.revision, candidate.runs,
        reruns=reruns, qualification={s.stage.value: s.status.value for s in q.stages},
        coverage=_coverage_counts(candidate), artifacts=_artifact_identity(candidate),
    )
    result = QualificationResult(q, baseline, candidate, baseline_controls, stability, timings, budget, history)
    (session.directory / "qualification.json").write_text(json.dumps(to_jsonable(result), indent=2), encoding="utf-8")
    return result


def load_qualified_changes(session: ImproveSession) -> list[CandidateTestChange]:
    path = session.directory / "qualification.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        CandidateTestChange(**{**c, "kind": CandidateChangeKind(c["kind"])})
        for c in data["qualification"]["changes"]
    ]


@scoped
def apply_approved(
    session: ImproveSession,
    qualified: QualificationResult | list[CandidateTestChange],
    approval: Approval | None,
) -> AppliedResult:
    changes = qualified.qualification.changes if isinstance(qualified, QualificationResult) else qualified
    applied = apply_changes(session.root, session.baseline, session.workspace, changes, approval)
    files_match = all(
        entry_digest(session.root, c.path) == c.candidate_fingerprint
        for c in applied
    )
    evidence = measure(session.root, "applied", "applied-project-copy", session.python, reason="post-apply verification")
    applied_tree = capture_baseline(session.root)
    record_state(session.root, "improve", "applied", applied_tree.digest, applied_tree.revision, evidence.runs,
                 coverage=_coverage_counts(evidence), artifacts=_artifact_identity(evidence))
    result = AppliedResult(applied, evidence, files_match)
    (session.directory / "applied.json").write_text(json.dumps(to_jsonable(result), indent=2), encoding="utf-8")
    return result
