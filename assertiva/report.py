"""Assurance Report: one model for audit and improve, rendered as self-contained HTML.

The model never mixes states: CURRENT (audit), BASELINE / CANDIDATE (improve) and
APPLIED (only after approval). Rendering lives in report_html; this module owns the model.
"""

from __future__ import annotations

import difflib
import json
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .identity import runtime_identity
from .candidate import DeltaState, StageStatus
from .process import MAX_DEPTH, current_depth
from .evidence import StateEvidence, compare_states, mutant_label, state_metrics, to_jsonable
from .report_html import render_html  # noqa: F401  (presentation lives in report_html; re-exported for callers)

REPORT_VERSION = "1"

_SEVERITY = {
    "CI_TEST_EXECUTION_GAP": "high", "LOCAL_CHECK_NOT_OBSERVED_IN_CI": "high", "HIGH_COVERAGE_WEAK_ORACLE": "high",
    "SUITE_SMOKE_DOMINANT": "high", "MUTATION_SURVIVORS": "high", "MUTATION_REPORT_UNREADABLE": "medium",
    "MUTATION_REPORT_SOURCE_MISMATCH": "medium",
    "ARTIFACT_QUALIFICATION_FAILED": "high", "PROJECT_LINK_ESCAPES_ROOT": "high", "BROKEN_PROJECT_LINK": "medium",
    "NESTED_REPOSITORY": "info", "DECLARED_CHECK_FAILED": "high", "ERROR_CONTRACT_FIELD_NOT_OBSERVED": "medium",
    "STATE_AFTER_REJECTION_NOT_EVIDENCED": "info", "ASYNC_FAILURE_NOT_OBSERVED": "high", "ARTIFACT_QUALIFICATION_INCOMPLETE": "medium", "ARTIFACT_OMITS_SOURCE_FILES": "medium", "NATIVE_COLLECTION_ERRORS": "high", "NATIVE_TESTS_FAILING": "high",
    "WEAK_ORACLE_SIGNAL": "medium", "ERROR_STATUS_ONLY_SIGNAL": "medium",
    "BROAD_ERROR_EXPECTATION_SIGNAL": "medium", "LINE_BRANCH_COVERAGE_DIVERGENCE": "medium", "CI_ONLY_CHECK": "medium",
    "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED": "info", "NO_DELIVERY_PIPELINE_OBSERVED": "info",
    "UNCLASSIFIED_VERIFICATION": "info", "NO_TESTS_DISCOVERED": "info", "STATIC_INVENTORY_DIVERGES_FROM_NATIVE": "info",
}
_RECOMMENDATION = {
    "WEAK_ORACLE_SIGNAL": "Strengthen the listed tests to assert values, state or effects rather than existence or success status.",
    "SUITE_SMOKE_DOMINANT": "Prioritize behavioral oracles for the most critical flows before adding more smoke tests.",
    "HIGH_COVERAGE_WEAK_ORACLE": "Do not read the coverage figure as protection; challenge covered code with negative controls or mutation testing.",
    "LINE_BRANCH_COVERAGE_DIVERGENCE": "Add cases for the untaken branches (boundaries, invalid input, error paths).",
    "ERROR_STATUS_ONLY_SIGNAL": "Also assert the structured error (code/field/path) and the state after rejection.",
    "BROAD_ERROR_EXPECTATION_SIGNAL": "Expect the specific error type/code the contract defines instead of a broad base exception.",
    "CI_TEST_EXECUTION_GAP": "Run the unobserved test paths in CI or document why they are excluded from the delivery gate.",
    "LOCAL_CHECK_NOT_OBSERVED_IN_CI": "Run these local checks in CI (or the hook runner) so a green pipeline covers them.",
    "CI_ONLY_CHECK": "Make CI-only validators runnable locally so local green approximates pipeline green.",
    "UNCLASSIFIED_VERIFICATION": "Declare what the unclassified checks verify, or add an adapter; until then they stay UNKNOWN.",
    "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED": "Provide portable evidence (standard test-result and coverage reports) or an adapter for this toolchain.",
    "NATIVE_COLLECTION_ERRORS": "Fix collection errors first: tests that cannot be collected provide no evidence.",
    "NATIVE_TESTS_FAILING": "Triage failing tests before trusting any other metric in this report.",
    "MUTATION_SURVIVORS": "Add or strengthen tests that fail for the listed surviving mutants, or document why a mutant is equivalent.",
    "MUTATION_REPORT_SOURCE_MISMATCH": "Regenerate the mutation report for the audited revision.",
    "ARTIFACT_QUALIFICATION_FAILED": "Fix packaging (included packages, package data, metadata) so the installed artifact passes the same tests as the source tree.",
    "ERROR_CONTRACT_FIELD_NOT_OBSERVED": "Assert the machine code/field the error contract carries, as the other tests for the same error do.",
    "STATE_AFTER_REJECTION_NOT_EVIDENCED": "After the expected rejection, assert that no partial write or forbidden side effect happened.",
    "ASYNC_FAILURE_NOT_OBSERVED": "Await (or gather) the created task so its failure can fail the test.",
    "PROJECT_LINK_ESCAPES_ROOT": "Replace links that leave the project with project files or declared external dependencies.",
    "MATRIX_GAP": "Add the declared runtime/target to a CI job, or narrow what the project declares it supports.",
    "MATRIX_UNVERIFIED": "State the runtime/target explicitly in CI (matrix or setup version) so coverage of it can be checked.",
    "CI_SINGLE_OS": "If other operating systems are supported, run at least one CI job on each.",
    "PUBLISHED_ARTIFACT_NOT_QUALIFIED": "Test the built artifact (install it and run tests) in the job that publishes it, before publishing.",
    "ARTIFACT_LINEAGE_UNKNOWN": "Record the tested artifact's hash and publish exactly those bytes, or verify the hash before deploying.",
    "TESTED_ARTIFACT_DIFFERS_FROM_DELIVERED": "Rebuild and requalify, or publish the artifact that was actually tested.",
    "DECLARED_CHECK_FAILED": "Reproduce the failing check locally and fix the cause before trusting a green from the pipeline that runs it.",
    "ARTIFACT_OMITS_SOURCE_FILES": "Confirm the listed files are intentionally excluded from the artifact, or add them as package data.",
}


# --- model ---------------------------------------------------------------------------

def state_summary(state: StateEvidence | None) -> dict | None:
    if state is None:
        return None
    return {
        "label": state.label,
        "observed_in": state.observed_in,
        "metrics": {
            name: {"value": m.value, "direction": m.direction.value, "unit": m.unit, "evidence_tier": m.evidence_tier}
            for name, m in state_metrics(state).items()
        },
        "runs": [
            {
                "adapter": run.adapter_id, "mode": run.mode, "status": run.status.value, "command": run.command,
                # who produced the results: an engine run, or a report read by the engine (revision not verified)
                "provenance": run.metadata.get("provenance") or ("EXTERNAL_UNVERIFIED" if run.mode == "report" else "ENGINE_EXECUTED"),
                "cases_duration_sum_s": run.metadata.get("cases_duration_sum_s"),
                "declaration_identity": run.metadata.get("declaration_identity", "KNOWN"),
                "exit_code": run.exit_code, "invocations": len(run.invocations), "collection_errors": run.collection_errors,
                # per-outcome counts: a run's invocations include skipped and not-run cases, which never count as passed
                "outcomes": dict(Counter(inv.outcome.value for inv in run.invocations if inv.outcome is not None)),
                "limitations": run.limitations,
                # Adapter-defined execution dimensions (e.g. projects or targets) and attachment references.
                "matrix": dict(run.metadata.get("matrix") or {}),
                "attachments": sum(len(v) for v in (run.metadata.get("attachments") or {}).values()),
            }
            for run in state.runs
        ],
        "negative_controls": to_jsonable(state.negative_controls),
        "mutation": [_mutation_summary(run) for run in state.mutation],
        "artifacts": to_jsonable(state.artifacts),
        "negative_paths": {k: list(v) for k, v in state.negative_paths.items()},
        "coverage": [{**to_jsonable(c), "origin": c.origin or origin} for c, origin in
                     ([(c, "INGESTED") for c in state.coverage] or [(run.coverage, "MEASURED") for run in state.runs if run.coverage])],
        "limitations": list(state.limitations),
    }


def _mutation_summary(run) -> dict:
    return {
        "tool": run.tool, "tool_version": run.tool_version, "source": run.source, "error": run.error,
        "per_mutant": run.per_mutant, "matches_state": run.matches_state, "counts": dict(run.counts),
        "evaluated": run.evaluated, "survivors": [mutant_label(m) for m in run.survivors()[:50]],
        "limitations": list(run.limitations),
    }


def engine_findings(findings: list) -> list[dict]:
    """Engine findings as report records: a stable id within the run (the code, suffixed when it repeats), the engine's
    default severity, and a priority that starts as that severity (an attached assessment may restate it)."""
    out, seen = [], Counter()
    for finding in findings:
        data = to_jsonable(finding)
        data["severity"] = data.get("severity") or _SEVERITY.get(data["code"], "medium")
        seen[data["code"]] += 1
        data["id"] = data["code"] if seen[data["code"]] == 1 else f"{data['code']}-{seen[data['code']]}"
        data["origin"] = "engine"
        data["priority"] = data["severity"]
        out.append(data)
    return out


def recommendations(findings: list[dict]) -> list[dict]:
    return [
        {"finding": f["code"], "finding_id": f.get("id", f["code"]),
         "recommendation": f.get("recommendation") or _RECOMMENDATION[f["code"]], "status": "PROPOSED"}
        for f in findings
        if f.get("recommendation") or f["code"] in _RECOMMENDATION
    ]


def _delta_buckets(deltas) -> dict[str, list[dict]]:
    buckets: dict[str, list[dict]] = {"improved": [], "unchanged": [], "regressed": [], "changed": [], "unknown": []}
    for d in deltas:
        buckets[d.state.value.lower()].append(to_jsonable(d))
    return buckets


def _diff(before: Path, after: Path, path: str, limit: int = 400) -> str:
    def lines(p: Path) -> list[str] | None:
        if not p.is_file():
            return []
        try:
            return p.read_text(encoding="utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            return None

    old, new = lines(before), lines(after)
    if old is None or new is None:
        return "(binary file)"
    diff = list(difflib.unified_diff(old, new, f"baseline/{path}", f"candidate/{path}"))
    text = "".join(diff[:limit])
    return text + ("\n... diff truncated ...\n" if len(diff) > limit else "")


def _surface(surface) -> list[dict]:
    return [to_jsonable(check) for check in surface.checks] if surface else []


# What `read_only_verified` covers, so it is never read as more than was measured.
READ_ONLY_SCOPE = {
    "measured": "every entry of the project tree, including ignored files and caches, fingerprinted by content before and after (links by their target, never followed)",
    "not_measured": [
        "files outside the project tree (home directory, temporary directories, Assertiva's own state)",
        "targets of links that leave the project",
        "network effects and external services",
    ],
}


def execution_manifest(root: Path, baseline, current: StateEvidence, started: str, results=(), coverage=(), mutation=(), ci=(),
                       withheld=()) -> dict:
    """Identity of this audit: the code, what ran (who ran it, how, exit status, duration), what was only read."""
    import hashlib
    import platform
    import sys

    from .process import PASSTHROUGH, redact

    def digest(path) -> str | None:
        try:
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            return None

    return {
        "started_at": started,
        "ended_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "code": {"tree_digest": baseline.digest, "files": len(baseline.files), "vcs_revision": baseline.revision,
                 "local_changes": baseline.dirty, "note": None if baseline.revision else "no version control: the tree digest identifies the code"},
        "engine": {"assertiva_version": __version__, "runtime_version": sys.version.split()[0], "platform": platform.platform(terse=True)},
        "runs": [{"adapter": run.adapter_id, "provenance": run.metadata.get("provenance") or ("EXTERNAL_UNVERIFIED" if run.mode == "report" else "ENGINE_EXECUTED"),
                  "command": [redact(str(c)) for c in run.command], "exit_code": run.exit_code, "wall_clock_s": run.wall_clock_s,
                  "status": run.status.value, "invocations": len(run.invocations)} for run in current.runs],
        "read": [{"kind": kind, "path": str(path), "sha256": digest(path)} for kind, paths in
                 (("test_results", results), ("coverage", coverage), ("mutation", mutation), ("ci_run", ci)) for path in paths],
        "environment": {"withheld": list(withheld), "passed_through": sorted(PASSTHROUGH)},
    }


def _technologies(root: Path, files: list[str], runs) -> dict:
    """Languages and frameworks for the report header, each with how it is known (never a measurement)."""
    from .adapters.technologies import project_technologies

    executed = [run.adapter_id for run in runs if run.mode != "report" and run.status is not StageStatus.BLOCKED]
    return project_technologies(root, files, list(dict.fromkeys(executed)))


def _version(root: Path) -> dict | None:
    """The version the project declares for itself (manifest and value), for the report header."""
    from .adapters.technologies import project_version

    return project_version(root)


def audit_model(
    root: Path, baseline, findings: list, current: StateEvidence, surface, limitations: list[str], adapters: list[str], status: str,
) -> dict:
    findings_data = engine_findings(findings)
    observed, not_evidenced = [], []
    for run in current.runs:
        if run.mode == "report":
            observed.append(
                f"results ingested from {run.metadata.get('source')} via {run.adapter_id} (not executed by Assertiva): "
                f"{run.status.value} ({len(run.invocations)} cases)"
            )
        else:
            observed.append(f"native {run.adapter_id} run in an isolated copy: {run.status.value} ({len(run.invocations)} invocations)")
    if not current.runs:
        not_evidenced.append("no tests were executed; test outcomes are UNKNOWN")
    if current.static:
        observed.append("static oracle signals (E3 heuristics, not execution)")
    if surface and surface.checks:
        observed.append(f"{len(surface.checks)} declared verification checks (configuration, not run evidence)")
        not_evidenced.append("whether declared CI checks actually ran, on which revision, and whether they gate merges")
    if not any(run.coverage for run in current.runs) and not any(c.error is None for c in current.coverage):
        not_evidenced.append("coverage")
    for c in current.coverage:
        if c.error is None:
            observed.append(f"coverage report ingested from {c.source} ({c.tool}): read by Assertiva, not measured; the revision it measured is not verified")
    for run in current.runs:
        for name, value in (run.metadata.get("matrix") or {}).items():
            if value != "EXECUTED":
                not_evidenced.append(f"{run.adapter_id} {name}: {value.lower().replace('_', ' ')}, not executed")
    usable_mutation = [run for run in current.mutation if run.error is None and run.matches_state is not False]
    if usable_mutation:
        observed.append("ingested mutation report(s): " + ", ".join(f"{r.tool or 'unknown tool'} ({r.evaluated} evaluated)" for r in usable_mutation))
    else:
        not_evidenced.append("mutation / negative-control strength")
    for a in current.artifacts:
        verified = ", ".join(f"{c.name} {c.status.value}" for c in a.checks)
        (observed if a.status is StageStatus.PASS else not_evidenced).append(
            f"{a.kind} {a.artifact or '(not built)'}: {verified}"
        )
    if not current.artifacts:
        not_evidenced.append("build, package and installed-artifact behavior")
    not_evidenced.append("startup, health and deployment behavior")
    return {
        "report_version": REPORT_VERSION,
        "workflow": "audit",
        "run_id": uuid.uuid4().hex[:16],
        "status": status,
        "project": {"name": root.name, "root": str(root), "revision": baseline.revision, "dirty": baseline.dirty, "digest": baseline.digest,
                    "technologies": _technologies(root, list(baseline.files), current.runs), "version": _version(root)},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "states": {"current": state_summary(current), "baseline": None, "candidate": None, "applied": None},
        "findings": findings_data,
        "recommendations": recommendations(findings_data),
        "verification_surface": _surface(surface),
        "evidence_delta": None,
        "change_set": None,
        "candidate_qualification": None,
        "claim_boundary": {"observed": observed, "not_evidenced": not_evidenced, "limitations": limitations},
        "remaining_unknowns": list(not_evidenced),
        "provenance": {"assertiva_version": __version__, "runtime": runtime_identity(), "adapters": adapters, "read_only_verified": True,
                       "read_only_scope": READ_ONLY_SCOPE},
    }


def improve_report(session, result, applied=None) -> dict:
    from .verification import discover_surface

    q = result.qualification
    changes = [
        {**to_jsonable(c), "diff": _diff(session.baseline_copy / c.path, session.workspace / c.path, c.path)}
        for c in q.changes
    ]
    observed = [f"{c.check.value}: {c.summary}" for c in q.checks if c.status is StageStatus.PASS]
    not_evidenced = [f"{c.check.value} ({c.status.value}): {c.summary}" for c in q.checks if c.status is not StageStatus.PASS]
    not_evidenced.append("preview/deployment behavior: no authorized non-production preview adapter; production is never used to qualify tests")
    limitations = sorted({l for c in q.checks for l in c.limitations})
    if applied is None:
        limitations.insert(0, "Candidate evidence was observed in an isolated copy; the candidate is not applied to the project.")
    else:
        observed.append(f"APPLIED: {len(applied.applied)} approved changes applied; files match candidate: {applied.files_match_candidate}")
    applied_deltas = compare_states(result.baseline_evidence, applied.evidence) if applied else []
    return {
        "report_version": REPORT_VERSION,
        "workflow": "improve",
        "status": "APPLIED" if applied else ("READY_FOR_REVIEW" if q.ready_for_review else "NEEDS_ATTENTION"),
        "project": {
            "name": session.root.name, "root": str(session.root),
            "revision": session.baseline.revision, "dirty": session.baseline.dirty, "baseline_digest": session.baseline.digest,
            "technologies": _technologies(session.root, list(session.baseline.files), result.baseline_evidence.runs),
            "version": _version(session.root),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "states": {
            "current": None,
            "baseline": state_summary(result.baseline_evidence),
            "candidate": state_summary(result.candidate_evidence),
            "applied": state_summary(applied.evidence) if applied else None,
        },
        "findings": [],
        "recommendations": [],
        "verification_surface": _surface(discover_surface(session.workspace)),
        "evidence_delta": _delta_buckets(q.metric_deltas),
        "applied_delta": _delta_buckets(applied_deltas) if applied else None,
        "change_set": {"changes": changes, "approval_required": True, "applied": [c.change_id for c in applied.applied] if applied else []},
        "candidate_qualification": {
            "ready_for_review": q.ready_for_review,
            "stages": to_jsonable(q.stages),
            "baseline_negative_controls": to_jsonable(result.baseline_controls),
            "stability": to_jsonable(result.stability),
            "timings": list(result.timings),
        },
        "claim_boundary": {"observed": observed, "not_evidenced": not_evidenced, "limitations": limitations},
        "remaining_unknowns": [
            f"{s.check.value} ({s.status.value}): {s.summary}" for s in q.checks
            if s.status in (StageStatus.UNKNOWN, StageStatus.NOT_RUN, StageStatus.BLOCKED)
        ] + [f"metric {d.name}: not measured in both states" for d in q.metric_deltas if d.state is DeltaState.UNKNOWN]
        + ["preview/deployment behavior: no authorized non-production preview adapter"],
        "provenance": {"assertiva_version": __version__, "runtime": runtime_identity(), "interpreter": session.python, "read_only_until_approval": True},
        "execution_budget": execution_budget(
            "qualification", [*result.baseline_evidence.budget, *result.candidate_evidence.budget, *result.budget]
        ),
    }


def execution_budget(level: str, decisions) -> dict:
    """How much was executed, reused or refused, and why (never a quality score)."""
    return {
        "level": level, "depth": current_depth(), "max_depth": MAX_DEPTH,
        "decisions": [to_jsonable(d) for d in decisions],
    }


def write_report(report: dict, directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    target = directory / f"{name}.html"
    target.write_text(render_html(report), encoding="utf-8")
    return target


def selection_summary(selection) -> dict | None:
    if selection is None:
        return None
    data = to_jsonable(selection)
    data["full"] = selection.full
    data["counts"] = {"selected": len(selection.selected), "not_selected": len(selection.not_selected),
                      "mapped": len(selection.selected) + len(selection.not_selected)}
    return data
