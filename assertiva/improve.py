"""`assertiva improve` orchestration.

AUDIT -> baseline snapshot -> isolated candidate -> candidate changes -> qualification
-> baseline vs candidate -> explicit human approval -> approved apply -> post-apply
verification. The original project is read-only (and verified as such) until apply.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .adapters import runner_adapters
from .adapters.commands import reproduction_plan
from .adapters.mutation import load_mutation_report
from .candidate import (
    CandidateChangeKind,
    CandidateQualification,
    CandidateTestChange,
    DeltaState,
    QualificationStage,
    QualificationStageResult,
    StageStatus,
)
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
    state_from_dict,
    to_jsonable,
)
from .models import MutantStatus, Outcome, StabilityEvidence, StabilityRecord
from .process import run_command, traced_stage
from .verification import GateMode, VerificationOrigin, discover_surface
from .workspace import (
    Approval,
    Baseline,
    apply_changes,
    capture_baseline,
    change_set,
    create_workspace,
    file_digest,
    read_only_guard,
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


def start_improve(root: str | Path, python: str | None = None) -> ImproveSession:
    root = Path(root).resolve()
    if load_session(root) is not None:
        raise SessionExistsError(f"an improve session is already active for {root}")
    directory = state_dir(root, "sessions")
    with read_only_guard(root):
        baseline = capture_baseline(root)
        workspace = create_workspace(baseline)
        baseline_copy = snapshot(root, directory / "baseline")
        baseline_evidence = measure(baseline_copy, "baseline", "isolated-baseline-copy", python)
    session = ImproveSession(root, directory, baseline, workspace, baseline_copy, python, baseline_evidence)
    session.save()
    return session


def discard_session(session: ImproveSession) -> None:
    remove_workspace(session.baseline, session.workspace)
    shutil.rmtree(session.directory, ignore_errors=True)


def _stage(stage: QualificationStage, status: StageStatus, summary: str, *limitations: str) -> QualificationStageResult:
    return QualificationStageResult(stage, status, summary, limitations=tuple(limitations))


def _invocations(state: StateEvidence):
    return [inv for run in state.runs for inv in run.invocations]


def _discovery_stage(candidate: StateEvidence) -> QualificationStageResult:
    stage = QualificationStage.STATIC_AND_DISCOVERY
    if not candidate.runs:
        return _stage(stage, StageStatus.UNKNOWN, "no runner adapter could discover candidate tests", *candidate.limitations)
    errors = [error for run in candidate.runs for error in run.collection_errors]
    if errors:
        return _stage(stage, StageStatus.FAIL, "collection errors: " + ", ".join(errors[:10]))
    if any(run.status is StageStatus.BLOCKED for run in candidate.runs):
        return _stage(stage, StageStatus.BLOCKED, "runner could not execute", *[l for r in candidate.runs for l in r.limitations])
    count = len(_invocations(candidate))
    if not count:
        return _stage(stage, StageStatus.UNKNOWN, "no candidate invocations were collected")
    return _stage(stage, StageStatus.PASS, f"{count} invocations collected natively without errors")


def _candidate_tests_stage(changes: list[CandidateTestChange], candidate: StateEvidence) -> QualificationStageResult:
    stage = QualificationStage.CANDIDATE_TESTS
    if not candidate.runs:
        return _stage(stage, StageStatus.UNKNOWN, "no runner adapter could execute candidate tests", *candidate.limitations)
    changed = {c.path for c in changes if c.kind is not CandidateChangeKind.RETIRE_CANDIDATE}
    touched = [inv for inv in _invocations(candidate) if changed & set(inv.source_paths)]
    errors = [e for run in candidate.runs for e in run.collection_errors if e.split("::")[0] in changed]
    if errors:
        return _stage(stage, StageStatus.FAIL, "candidate test files failed to collect: " + ", ".join(errors))
    if not touched:
        return _stage(stage, StageStatus.NOT_RUN, "the candidate does not add or modify executable tests")
    bad = sorted(inv.invocation_id for inv in touched if inv.outcome in (Outcome.FAILED, Outcome.ERROR))
    if bad:
        return _stage(stage, StageStatus.FAIL, "failing candidate invocations: " + ", ".join(bad[:10]))
    if all(inv.outcome in (Outcome.SKIPPED, Outcome.NOT_RUN, None) for inv in touched):
        return _stage(stage, StageStatus.UNKNOWN, "every candidate invocation was skipped or not run")
    return _stage(stage, StageStatus.PASS, f"{len(touched)} added/modified invocations executed without failure")


def _regression_stage(session: ImproveSession, changes: list[CandidateTestChange], candidate: StateEvidence) -> QualificationStageResult:
    """Run the unchanged original tests against the candidate."""
    stage = QualificationStage.ORIGINAL_REGRESSION
    baseline = session.baseline_evidence
    if not baseline.runs or not candidate.runs:
        return _stage(stage, StageStatus.UNKNOWN, "no runner adapter produced baseline/candidate execution evidence")
    protected = {inv.invocation_id for inv in _invocations(baseline) if inv.outcome is Outcome.PASSED}
    if not protected:
        return _stage(stage, StageStatus.UNKNOWN, "the baseline had no passing invocations to protect")
    test_sources = {path for inv in _invocations(baseline) for path in inv.source_paths}
    restore = [c.path for c in changes if c.kind is not CandidateChangeKind.ADD and c.path in test_sources]
    if restore:
        copy = snapshot(session.workspace)
        try:
            for path in restore:
                (copy / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(session.baseline_copy / path, copy / path)
            runs = [adapter.run(copy) for adapter in runner_adapters(copy, session.python)]
        finally:
            shutil.rmtree(copy, ignore_errors=True)
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


def _delta_stage(stage: QualificationStage, deltas, names: tuple[str, ...], required: tuple[str, ...], missing_note: str) -> QualificationStageResult:
    relevant = [d for d in deltas if d.name in names]
    regressed = [d.name for d in relevant if d.state is DeltaState.REGRESSED]
    if regressed:
        return _stage(stage, StageStatus.FAIL, "regressed: " + ", ".join(regressed))
    present = {d.name for d in relevant if d.state is not DeltaState.UNKNOWN}
    if not set(required) <= present:
        return _stage(stage, StageStatus.UNKNOWN, "partial evidence: " + (", ".join(sorted(present)) or "none"), missing_note)
    return _stage(stage, StageStatus.PASS, "no regression in " + ", ".join(sorted(present)))


_WEAK_NEGATIVE = {"ERROR_TYPE", "PROTOCOL_STATUS"}


def _negative_path_stage(changes, candidate: StateEvidence, deltas) -> QualificationStageResult:
    """Static failure-contract dimensions (E3) combined with runtime outcomes (E1)."""
    stage = QualificationStage.NEGATIVE_PATHS
    provenance = "dimensions are static AST signals (E3); outcomes come from the native run (E1); rollback and external side effects are not evidenced"
    weakened = [
        d.name for d in deltas
        if d.name in {"broad_error_expectations", "error_status_only_tests", "negative_paths_without_contract_detail"}
        and d.state is DeltaState.REGRESSED
    ]
    if weakened:
        return _stage(stage, StageStatus.FAIL, "negative-path evidence weakened: " + ", ".join(weakened), provenance)
    changed = {c.path for c in changes if c.kind is not CandidateChangeKind.RETIRE_CANDIDATE}
    touched = {tid: dims for tid, dims in candidate.negative_paths.items() if tid.split("::")[0] in changed}
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


def _mutation_stage(candidate: StateEvidence) -> QualificationStageResult:
    """Negative controls and mutation reports are separate evidence; both are reported."""
    stage = QualificationStage.MUTATION_OR_NEGATIVE_CONTROLS
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


def _artifact_stage(candidate: StateEvidence) -> QualificationStageResult:
    stage = QualificationStage.BUILD_AND_ARTIFACT
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


def _run_declared(argv: tuple[str, ...], copy: Path, python: str | None) -> tuple[StageStatus, str]:
    env = dict(os.environ)
    env["PATH"] = str(Path(python or sys.executable).parent) + os.pathsep + env.get("PATH", "")
    result = run_command(list(argv), copy, env=env)
    if result.error or result.timed_out:
        return StageStatus.BLOCKED, result.summary()
    return (StageStatus.PASS if result.ok else StageStatus.FAIL), result.summary()


def _pipeline_stage(session: ImproveSession, authorized: set[str]) -> QualificationStageResult:
    """Reproduce the candidate's own delivery checks: DISCOVERED -> AUTHORIZED -> EXECUTED."""
    stage = QualificationStage.PIPELINE_EQUIVALENT
    delivery = discover_surface(session.workspace).by_origin(VerificationOrigin.CI)
    if not delivery:
        return _stage(stage, StageStatus.NOT_RUN, "no delivery pipeline was discovered", "delivery-path verification is UNKNOWN")
    adapters = runner_adapters(session.workspace, session.python)
    gating: list[StageStatus] = []
    reproduced, partial = 0, False
    notes: list[str] = []
    copy = snapshot(session.workspace)
    try:
        for check in delivery:
            label = f"{check.command or check.tool or check.check_id} [{check.kind.value}]"
            runner = next(((a, args) for a in adapters if (args := a.reproduction_args(check)) is not None), None)
            if runner:
                run = runner[0].run(copy, args=runner[1])
                status, detail = run.status, f"{len(run.invocations)} invocations"
            else:
                plan = reproduction_plan(check, session.python or sys.executable)
                if plan.argv is None:
                    notes.append(f"not reproduced: {label}: {plan.reason}")
                    continue
                if plan.needs_authorization and check.check_id not in authorized:
                    notes.append(f"not reproduced: {label}: discovered, not authorized (assertiva improve --run-check {check.check_id})")
                    continue
                status, detail = _run_declared(plan.argv, copy, session.python)
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
        shutil.rmtree(copy, ignore_errors=True)
    summary = f"reproduced {reproduced}/{len(delivery)} delivery checks locally"
    if StageStatus.FAIL in gating:
        return _stage(stage, StageStatus.FAIL, summary + "; a reproduced gating check failed", *notes)
    if StageStatus.BLOCKED in gating:
        return _stage(stage, StageStatus.BLOCKED, summary + "; a reproduced check could not run", *notes)
    if reproduced < len(delivery) or partial or any(s is not StageStatus.PASS for s in gating):
        return _stage(stage, StageStatus.UNKNOWN, summary, *notes)
    return _stage(stage, StageStatus.PASS, summary + "; all gating checks passed", *notes)


MAX_STABILITY_INVOCATIONS = 50
MAX_STABILITY_RERUNS = 2


def _verdict(outcomes: tuple) -> str:
    if len(outcomes) < 2 or None in outcomes:
        return "INSUFFICIENT_EVIDENCE"
    failing = {Outcome.FAILED, Outcome.ERROR}
    if all(o in failing for o in outcomes):
        return "CONSISTENT_FAILURE"
    return "STABLE" if len(set(outcomes)) == 1 else "FLAKY_SIGNAL"


def _stability(session: ImproveSession, changes, candidate: StateEvidence, reruns: int) -> StabilityEvidence:
    """Bounded reruns of relevant invocations. The first outcome is kept; later ones are added, never substituted."""
    evidence = StabilityEvidence()
    reruns = min(max(reruns, 0), MAX_STABILITY_RERUNS)
    adapters = runner_adapters(session.workspace, session.python)
    if not reruns or not candidate.runs or not adapters:
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
        copy = snapshot(session.workspace)
        try:
            for adapter in adapters:
                run = adapter.run(copy, args=selected)
                evidence.commands.append(" ".join(run.command))
                for inv in run.invocations:
                    if inv.invocation_id in later:
                        later[inv.invocation_id].append(inv)
        finally:
            shutil.rmtree(copy, ignore_errors=True)
    evidence.attempts = 1 + reruns
    for iid in selected:
        attempts = [first[iid], *later[iid]]
        outcomes = tuple(inv.outcome for inv in attempts)
        evidence.records.append(StabilityRecord(iid, outcomes, tuple(inv.duration_s for inv in attempts), _verdict(outcomes)))
    return evidence


def _stability_stage(stability: StabilityEvidence, deltas) -> QualificationStageResult:
    stage = QualificationStage.STABILITY_AND_COST
    wall = next((d for d in deltas if d.name == "wall_clock_s"), None)
    cost = f"wall clock {wall.baseline}s -> {wall.candidate}s ({wall.state.value})" if wall else "wall clock unknown"
    bounds = ("absence of observed instability is not proof of stability", "order dependence was not measured", *stability.limitations)
    if not stability.records:
        return _stage(stage, StageStatus.NOT_RUN, f"no relevant invocation was rerun; {cost}", *bounds)
    by = {v: [r for r in stability.records if r.verdict == v] for v in ("FLAKY_SIGNAL", "INSUFFICIENT_EVIDENCE", "CONSISTENT_FAILURE")}
    if by["FLAKY_SIGNAL"]:
        shown = ", ".join(f"{r.invocation_id} ({'/'.join(o.value if o else '?' for o in r.outcomes)})" for r in by["FLAKY_SIGNAL"][:5])
        return _stage(stage, StageStatus.FAIL, f"FLAKY_SIGNAL: {shown}; {cost}", *bounds)
    if by["INSUFFICIENT_EVIDENCE"] or by["CONSISTENT_FAILURE"]:
        notes = [f"{len(by['CONSISTENT_FAILURE'])} consistently failing (see CANDIDATE_TESTS)"] if by["CONSISTENT_FAILURE"] else []
        notes += [f"{len(by['INSUFFICIENT_EVIDENCE'])} with insufficient reruns"] if by["INSUFFICIENT_EVIDENCE"] else []
        return _stage(stage, StageStatus.UNKNOWN, "; ".join(notes) + f"; {cost}", *bounds)
    return _stage(
        stage, StageStatus.PASS,
        f"no instability observed in {stability.attempts} executions of {len(stability.records)} invocations; {cost}", *bounds,
    )


def _stages(session: ImproveSession, changes, candidate: StateEvidence, deltas, authorized: set[str], stability, timed) -> list[QualificationStageResult]:
    plan = [
        (QualificationStage.STATIC_AND_DISCOVERY, lambda: _discovery_stage(candidate)),
        (QualificationStage.CANDIDATE_TESTS, lambda: _candidate_tests_stage(changes, candidate)),
        (QualificationStage.ORIGINAL_REGRESSION, lambda: _regression_stage(session, changes, candidate)),
        (QualificationStage.COVERAGE_AND_ORACLES, lambda: _delta_stage(
            QualificationStage.COVERAGE_AND_ORACLES, deltas,
            ("line_coverage", "branch_coverage", "weak_oracle_tests"),
            ("line_coverage", "branch_coverage", "weak_oracle_tests"),
            "coverage was not measured for both states",
        )),
        (QualificationStage.NEGATIVE_PATHS, lambda: _negative_path_stage(changes, candidate, deltas)),
        (QualificationStage.MUTATION_OR_NEGATIVE_CONTROLS, lambda: _mutation_stage(candidate)),
        (QualificationStage.PIPELINE_EQUIVALENT, lambda: _pipeline_stage(session, authorized)),
        (QualificationStage.BUILD_AND_ARTIFACT, lambda: _artifact_stage(candidate)),
        (QualificationStage.PREVIEW_DEPLOY, lambda: _stage(
            QualificationStage.PREVIEW_DEPLOY, StageStatus.NOT_RUN,
            "no authorized non-production preview adapter", "production is never used to qualify tests",
        )),
        (QualificationStage.STABILITY_AND_COST, lambda: _stability_stage(stability, deltas)),
    ]
    return [timed(stage.value, build) for stage, build in plan]


def qualify_candidate(
    session: ImproveSession,
    negative_controls: list[NegativeControl] | None = None,
    mutation_reports: dict[str, str | Path] | None = None,
    authorized_checks: set[str] | None = None,
    stability_reruns: int = MAX_STABILITY_RERUNS,
) -> QualificationResult:
    """mutation_reports maps "baseline"/"candidate" to an existing mutation-tool report for that state."""
    controls = list(negative_controls or [])
    reports = dict(mutation_reports or {})
    unknown_states = set(reports) - {"baseline", "candidate"}
    if unknown_states:
        raise ValueError(f"mutation reports must target baseline or candidate, not {sorted(unknown_states)}")
    timings: list[dict] = []

    def timed(name, build):
        started = time.monotonic()
        with traced_stage(name):
            value = build()
        timings.append({"stage": name, "duration_s": round(time.monotonic() - started, 3)})
        return value

    changes = change_set(session.baseline, session.workspace)
    with read_only_guard(session.root):
        candidate = timed("candidate-measure", lambda: measure(session.workspace, "candidate", "isolated-candidate-copy", session.python, controls))
        adapters = runner_adapters(session.baseline_copy, session.python)
        baseline_controls = timed("baseline-controls", lambda: [run_negative_control(session.baseline_copy, c, adapters) for c in controls])
        baseline = StateEvidence(**{**vars(session.baseline_evidence), "negative_controls": baseline_controls, "mutation": []})
        if "baseline" in reports:
            attach_mutation(baseline, load_mutation_report(reports["baseline"]), session.baseline_copy)
        if "candidate" in reports:
            attach_mutation(candidate, load_mutation_report(reports["candidate"]), session.workspace)
        deltas = compare_states(baseline, candidate)
        stability = timed("stability-reruns", lambda: _stability(session, changes, candidate, stability_reruns))
        stages = _stages(session, changes, candidate, deltas, set(authorized_checks or ()), stability, timed)
    result = QualificationResult(CandidateQualification(changes, deltas, stages), baseline, candidate, baseline_controls, stability, timings)
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


def apply_approved(
    session: ImproveSession,
    qualified: QualificationResult | list[CandidateTestChange],
    approval: Approval | None,
) -> AppliedResult:
    changes = qualified.qualification.changes if isinstance(qualified, QualificationResult) else qualified
    applied = apply_changes(session.root, session.baseline, session.workspace, changes, approval)
    files_match = all(
        (file_digest(session.root / c.path) if (session.root / c.path).is_file() else None) == c.candidate_fingerprint
        for c in applied
    )
    evidence = measure(session.root, "applied", "applied-project-copy", session.python)
    result = AppliedResult(applied, evidence, files_match)
    (session.directory / "applied.json").write_text(json.dumps(to_jsonable(result), indent=2), encoding="utf-8")
    return result
