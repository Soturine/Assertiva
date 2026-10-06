"""Assurance Report: one model for audit and improve, rendered as self-contained HTML.

The model never mixes states: CURRENT (audit), BASELINE / CANDIDATE (improve) and
APPLIED (only after approval). Charts are drawn only from measured pairs and always
sit next to a table with the same numbers. Visual identity is intentionally minimal.
"""

from __future__ import annotations

import difflib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .candidate import DeltaState, MetricDirection, StageStatus
from .process import MAX_DEPTH, current_depth
from .evidence import StateEvidence, compare_states, mutant_label, state_metrics, to_jsonable

REPORT_VERSION = "1"

_SEVERITY = {
    "CI_TEST_EXECUTION_GAP": "high", "LOCAL_CHECK_NOT_OBSERVED_IN_CI": "high", "HIGH_COVERAGE_WEAK_ORACLE": "high",
    "SUITE_SMOKE_DOMINANT": "high", "MUTATION_SURVIVORS": "high", "MUTATION_REPORT_UNREADABLE": "medium",
    "MUTATION_REPORT_SOURCE_MISMATCH": "medium",
    "ARTIFACT_QUALIFICATION_FAILED": "high", "PROJECT_LINK_ESCAPES_ROOT": "high", "BROKEN_PROJECT_LINK": "medium",
    "NESTED_REPOSITORY": "info", "ERROR_CONTRACT_FIELD_NOT_OBSERVED": "medium",
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
                "exit_code": run.exit_code, "invocations": len(run.invocations), "collection_errors": run.collection_errors,
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
        "coverage": [to_jsonable(c) for c in (state.coverage or [run.coverage for run in state.runs if run.coverage])],
        "limitations": list(state.limitations),
    }


def _mutation_summary(run) -> dict:
    return {
        "tool": run.tool, "tool_version": run.tool_version, "source": run.source, "error": run.error,
        "per_mutant": run.per_mutant, "matches_state": run.matches_state, "counts": dict(run.counts),
        "evaluated": run.evaluated, "survivors": [mutant_label(m) for m in run.survivors()[:50]],
        "limitations": list(run.limitations),
    }


def _finding(finding: Any) -> dict:
    data = to_jsonable(finding)
    data["severity"] = data.get("severity") or _SEVERITY.get(data["code"], "medium")
    return data


def _recommendations(findings: list[dict]) -> list[dict]:
    return [
        {"finding": f["code"], "recommendation": f.get("recommendation") or _RECOMMENDATION[f["code"]], "status": "PROPOSED"}
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


def audit_model(
    root: Path, baseline, findings: list, current: StateEvidence, surface, limitations: list[str], adapters: list[str], status: str,
) -> dict:
    findings_data = [_finding(f) for f in findings]
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
        "status": status,
        "project": {"name": root.name, "root": str(root), "revision": baseline.revision, "dirty": baseline.dirty},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "states": {"current": state_summary(current), "baseline": None, "candidate": None, "applied": None},
        "findings": findings_data,
        "recommendations": _recommendations(findings_data),
        "verification_surface": _surface(surface),
        "evidence_delta": None,
        "change_set": None,
        "candidate_qualification": None,
        "claim_boundary": {"observed": observed, "not_evidenced": not_evidenced, "limitations": limitations},
        "remaining_unknowns": list(not_evidenced),
        "provenance": {"assertiva_version": __version__, "adapters": adapters, "read_only_verified": True},
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
        "provenance": {"assertiva_version": __version__, "interpreter": session.python, "read_only_until_approval": True},
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


# --- HTML ----------------------------------------------------------------------------

def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _fmt(metric: dict | None) -> str:
    if not metric or metric.get("value") is None:
        return "—"
    value, unit = metric["value"], metric.get("unit")
    text = f"{value:.2f}" if isinstance(value, float) else str(value)
    if not unit:
        return text
    return text + unit if unit == "%" else f"{text} {unit}"


_STATE_LABELS = {"current": "Current", "baseline": "Baseline", "candidate": "Candidate", "applied": "Applied"}
_STATE_NOTES = {
    "current": "observed (read-only)",
    "baseline": "observed in isolated baseline copy",
    "candidate": "observed in isolated candidate — not applied",
    "applied": "observed after approved application",
}


def _metrics_table(report: dict) -> tuple[str, str]:
    states = [(k, v) for k, v in report["states"].items() if v]
    if not states:
        return "<p>No state was measured.</p>", ""
    names = sorted({name for _, s in states for name in s["metrics"]})
    if not names:
        return "<p>No metric was measured. Nothing is charted.</p>", ""
    delta = {d["name"]: bucket for bucket, items in (report.get("evidence_delta") or {}).items() for d in items}
    notes = {d["name"]: d.get("note") for items in (report.get("evidence_delta") or {}).values() for d in items}
    head = "".join(f'<th scope="col">{_STATE_LABELS[k]}<br><span class="note">{_STATE_NOTES[k]}</span></th>' for k, _ in states)
    rows = []
    for name in names:
        direction = next((s["metrics"][name]["direction"] for _, s in states if name in s["metrics"]), "")
        cells = "".join(f"<td>{_e(_fmt(s['metrics'].get(name)))}</td>" for _, s in states)
        state = delta.get(name, "")
        badge = f'<span class="chip {state}">{_e(state.upper())}</span>' if state else ""
        if notes.get(name):
            badge += f'<br><span class="note">{_e(notes[name])}</span>'
        rows.append(f'<tr><th scope="row">{_e(name)}</th>{cells}<td>{_e(direction)}</td><td>{badge}</td></tr>')
    table = (
        '<div class="scroll"><table id="metrics-table"><caption>Metrics by state (direction-aware; no aggregate score)</caption>'
        f'<thead><tr><th scope="col">Metric</th>{head}<th scope="col">Direction</th><th scope="col">Delta</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )
    sources = [
        f"{_STATE_LABELS[k]}: {c.get('tool') or 'unknown tool'}" + (f" ({c['scope']})" if c.get("scope") else "")
        + (f" — {c['error']}" if c.get("error") else "") + "".join(f"; {lim}" for lim in c.get("limitations") or ())
        for k, s in states for c in s.get("coverage") or []
    ]
    if sources:
        table += "<p>Coverage sources: " + _e(" · ".join(sources)) + "</p>"
    return table, _chart(states, names)


def _chart(states: list, names: list[str]) -> str:
    if len(states) < 2:
        return ""
    directional = {MetricDirection.HIGHER_IS_BETTER.value, MetricDirection.LOWER_IS_BETTER.value}
    plotted = [
        n for n in names
        if all(n in s["metrics"] and s["metrics"][n]["value"] is not None for _, s in states)
        and states[0][1]["metrics"][n]["direction"] in directional
    ]
    if not plotted:
        return ""
    bar_h, gap, label_w, width = 14, 10, 210, 640
    height = len(plotted) * (len(states) * bar_h + gap) + gap
    parts, y = [], gap
    for name in plotted:
        values = [s["metrics"][name]["value"] for _, s in states]
        scale = 100.0 if states[0][1]["metrics"][name]["unit"] == "%" else (max(values) or 1)
        parts.append(f'<text x="0" y="{y + bar_h}" class="lbl">{_e(name)}</text>')
        for i, ((key, _), value) in enumerate(zip(states, values)):
            w = max(1.0, (width - label_w - 70) * float(value) / float(scale))
            parts.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{bar_h - 2}" class="bar {key}"></rect>')
            parts.append(f'<text x="{label_w + w + 6:.1f}" y="{y + bar_h - 3}" class="val">{_e(value)}</text>')
            y += bar_h
        y += gap
    legend = " · ".join(f'<span class="swatch {k}"></span>{_STATE_LABELS[k]}' for k, _ in states)
    return (
        f'<figure><svg role="img" aria-labelledby="chart-title" viewBox="0 0 {width} {height}" width="100%">'
        f'<title id="chart-title">Directional metrics compared across states; the metrics table is the textual equivalent.</title>'
        f'{"".join(parts)}</svg><figcaption>{legend}. Same numbers as the metrics table.</figcaption></figure>'
    )


def _mutation_html(report: dict) -> str:
    rows = []
    for key, state in report["states"].items():
        for run in (state or {}).get("mutation", []):
            counts = ", ".join(f"{k.lower()}: {v}" for k, v in sorted(run["counts"].items())) or "—"
            status = "unreadable: " + run["error"] if run["error"] else ("source mismatch" if run["matches_state"] is False else counts)
            survivors = _list(run["survivors"], "none listed" if run["per_mutant"] else "no per-mutant identity in this format")
            rows.append(
                f'<tr><th scope="row">{_e(_STATE_LABELS[key])}</th><td>{_e(run["tool"] or "unknown")}</td>'
                f'<td>{_e(status)}</td><td>{survivors}</td><td>{_e("; ".join(run["limitations"]))}</td></tr>'
            )
    if not rows:
        return ""
    return (
        '<section id="mutation-evidence" aria-labelledby="h-mut"><h2 id="h-mut">Mutation evidence</h2>'
        "<p>Ingested from existing tools. A high score never hides a surviving mutant.</p>"
        '<div class="scroll"><table><caption>Mutation reports by state</caption><thead><tr><th scope="col">State</th>'
        '<th scope="col">Tool</th><th scope="col">Result</th><th scope="col">Survivors</th><th scope="col">Limitations</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
    )


def _negative_html(report: dict) -> str:
    states = [(k, s) for k, s in report["states"].items() if s and s.get("negative_paths")]
    if not states:
        return ""
    tests = sorted({t for _, s in states for t in s["negative_paths"]})
    head = "".join(f'<th scope="col">{_STATE_LABELS[k]}</th>' for k, _ in states)
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(t)}</code></th>'
        + "".join(f"<td>{_e(', '.join(s['negative_paths'][t]) or 'any error accepted') if t in s['negative_paths'] else '—'}</td>" for _, s in states)
        + "</tr>"
        for t in tests
    )
    return (
        '<section id="negative-paths" aria-labelledby="h-neg"><h2 id="h-neg">Negative-path evidence</h2>'
        "<p>What each failure-path test observes (static E3 signals). A post-rejection assertion is a state signal, not rollback proof.</p>"
        f'<div class="scroll"><table><caption>Observed failure-contract dimensions per test</caption><thead><tr><th scope="col">Test</th>{head}</tr></thead>'
        f"<tbody>{rows}</tbody></table></div></section>"
    )


def _artifact_html(report: dict) -> str:
    rows = []
    for key, state in report["states"].items():
        for a in (state or {}).get("artifacts", []):
            checks = "".join(
                f'<li><span class="chip {c["status"].lower()}">{_e(c["status"])}</span> {_e(c["name"])}: {_e(c["detail"])}</li>'
                for c in a["checks"]
            )
            fidelity = (
                '<p class="note">Proves: ' + ", ".join(f"{_e(k.lower().replace('_', ' '))} {_e(v)}" for k, v in a.get("fidelity", {}).items()) + "</p>"
                if a.get("fidelity") else ""
            )
            rows.append(
                f'<tr><th scope="row">{_e(_STATE_LABELS[key])}</th><td>{_e(a["kind"])} <code>{_e(a["artifact"] or "not built")}</code><br>'
                f'<span class="note">sha256 {_e((a["sha256"] or "—")[:16])}</span></td>'
                f'<td><span class="chip {a["status"].lower()}">{_e(a["status"])}</span></td><td><ul>{checks}</ul>{fidelity}</td>'
                f'<td>{_list(a["limitations"] + (["missing from artifact: " + ", ".join(a["omitted_files"][:10])] if a["omitted_files"] else []), "None.")}</td></tr>'
            )
    if not rows:
        return ""
    return (
        '<section id="artifact-evidence" aria-labelledby="h-art"><h2 id="h-art">Built artifact</h2>'
        "<p>Verified from the installed artifact in an isolated environment, outside the source tree.</p>"
        '<div class="scroll"><table><caption>Artifact qualification by state</caption><thead><tr><th scope="col">State</th>'
        '<th scope="col">Artifact</th><th scope="col">Status</th><th scope="col">Checks</th><th scope="col">Limitations</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
    )


def selection_summary(selection) -> dict | None:
    if selection is None:
        return None
    data = to_jsonable(selection)
    data["full"] = selection.full
    data["counts"] = {"selected": len(selection.selected), "not_selected": len(selection.not_selected),
                      "mapped": len(selection.selected) + len(selection.not_selected)}
    return data


def _history_html(report: dict) -> str:
    history = report.get("history")
    if not history:
        return ""
    if not history.get("enabled"):
        return ('<section id="history" aria-labelledby="h-history"><h2 id="h-history">History</h2>'
                f'{_list(history.get("limitations") or [], "History was not used.")}</section>')
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(e["invocation_id"])}</code></th><td><span class="chip">{_e(e["stability"])}</span></td>'
        f'<td>{_e(e["note"])}</td><td>{_e(e["failure_signature"] or "")}</td><td>{e["fingerprint_occurrences"] or ""}</td></tr>'
        for e in history["invocations"]
    )
    timings = _list([f'{t["invocation_id"]}: p50 {t["p50"]}s' + (f', p95 {t["p95"]}s' if t["p95"] is not None else "") + f' ({t["samples"]} samples)'
                     for t in history["durations"]], "Not enough samples for duration percentiles yet.")
    table = ('<div class="scroll"><table><caption>Invocations with history signals</caption><thead><tr><th scope="col">Invocation</th>'
             '<th scope="col">Stability</th><th scope="col">Evidence</th><th scope="col">Failure signature</th>'
             f'<th scope="col">Same fingerprint recorded</th></tr></thead><tbody>{rows}</tbody></table></div>') if rows else "<p>No instability or failure in the recorded history for these invocations.</p>"
    return ('<section id="history" aria-labelledby="h-history"><h2 id="h-history">History</h2>'
            f'<p>{history["states_recorded"]} recorded state(s) for this project.</p>{table}<h3>Durations</h3>{timings}'
            f'{_list(history["limitations"], "")}</section>')


def _delivery_html(report: dict) -> str:
    delivery = report.get("delivery")
    review = report.get("review_candidates") or []
    if not delivery and not review:
        return ""
    matrix = (delivery or {}).get("matrix") or {}
    declared = [f'{dim}: {", ".join(info["values"])} ({info["source"]})' for dim, info in sorted((matrix.get("declared") or {}).items())]
    ci = [f'{dim}: {", ".join(values)}' for dim, values in sorted((matrix.get("ci") or {}).items())]
    lineage = [f'{item["artifact"]} sha256 {(item["sha256"] or "?")[:12]} · tested {item["tested"]} · published {item["published"] if isinstance(item["published"], str) else len(item["published"])} '
               f'· deployed {item["deployed"] if isinstance(item["deployed"], str) else len(item["deployed"])}' for item in (delivery or {}).get("artifact_lineage") or []]
    candidates = [f'{c["kind"]}: {c["subject"]} — {c["tests"]} test(s), e.g. {", ".join(c["examples"][:3])}' for c in review]
    return (
        '<section id="delivery" aria-labelledby="h-delivery"><h2 id="h-delivery">Delivery and review candidates</h2>'
        f'<h3>Declared by the project</h3>{_list(declared, "No runtime or target declaration was recognized.")}'
        f'<h3>Selected by CI configuration</h3>{_list(ci, "CI configuration states no runtime, target or operating system.")}'
        f'<h3>Artifact lineage</h3>{_list(lineage, "No artifact was built and tested in this run.")}'
        '<h3>Review candidates</h3><p class="note">Concentrations worth a human look: not duplicates, not findings, never a gate; nothing is removed.</p>'
        f'{_list(candidates, "None.")}</section>'
    )


def _selection_html(report: dict) -> str:
    selection = report.get("test_selection")
    if not selection:
        return ""
    counts = selection["counts"]
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(test)}</code></th><td>{_e(reasons[0]["reason"])}</td>'
        f'<td>{_e(reasons[0]["tier"] or reasons[0]["trigger"] or "")}</td><td>{_e(" → ".join(reasons[0]["path"]))}</td></tr>'
        for test, reasons in sorted(selection["selected"].items())[:200]
    )
    widening = _list([f'{w["trigger"]}{" (full suite)" if w["full"] else ""}: {w["path"] or ""} {w["reason"]}'.strip()
                      for w in selection["widening"]], "No widening was needed.")
    unknowns = _list([f'{u["node"]}: {u["reason"]}' for u in selection["unknown_dependencies"]], "No unknown relation is reachable from a test.")
    affected = sorted((selection.get("affected_components") or {}).items())
    components = f"<h3>Affected components</h3>{_list([f'{name}: {why}' for name, why in affected], '')}" if affected else ""
    return (
        '<section id="selection" aria-labelledby="h-selection"><h2 id="h-selection">Impact-based test selection</h2>'
        f'<p>Base <code>{_e(selection["base"] or "none")}</code> · {len(selection["changes"])} changed file(s) · '
        f'confidence <span class="chip">{_e(selection["confidence"])}</span> · selected {counts["selected"]} of {counts["mapped"]} mapped test files'
        f'{" · " + _e(selection["fallback"]) if selection["fallback"] else ""}</p>'
        + components
        + f'<h3>Widening</h3>{widening}<h3>Unknown dependencies</h3>{unknowns}'
        '<div class="scroll"><table><caption>Selected tests and why</caption><thead><tr><th scope="col">Test</th><th scope="col">Reason</th>'
        f'<th scope="col">Tier / trigger</th><th scope="col">Proof path</th></tr></thead><tbody>{rows}</tbody></table></div>'
        f'<p class="note">{_e(selection["limitations"][0] if selection["limitations"] else "")}</p></section>'
    )


def _budget_html(report: dict) -> str:
    budget = report.get("execution_budget")
    if not budget:
        return ""
    rows = "".join(
        f'<tr><th scope="row">{_e(d["stage"])}</th><td><span class="chip {d["decision"].lower()}">{_e(d["decision"])}</span></td>'
        f'<td>{_e(d["reason"])}</td></tr>'
        for d in budget["decisions"]
    )
    return (
        '<section id="budget" aria-labelledby="h-budget"><h2 id="h-budget">Execution budget</h2>'
        f'<p>Level: <strong>{_e(budget["level"])}</strong>; nesting depth {_e(budget["depth"])} of {_e(budget["max_depth"])}. '
        "Expensive evidence runs only when requested or needed, equivalent evidence is reused, and refusals are never PASS.</p>"
        '<div class="scroll"><table><caption>What ran, what was reused or refused, and why</caption><thead><tr>'
        f'<th scope="col">Evidence</th><th scope="col">Decision</th><th scope="col">Reason</th></tr></thead><tbody>{rows}</tbody></table></div></section>'
    )


def _runs_html(report: dict) -> str:
    rows = []
    for key, state in report["states"].items():
        for run in (state or {}).get("runs", []):
            how = "ingested report (not executed by Assertiva)" if run["mode"] == "report" else f"executed in {state['observed_in']}"
            rows.append(
                f'<tr><th scope="row">{_e(_STATE_LABELS[key])}</th><td>{_e(run["adapter"])}</td><td>{_e(how)}</td>'
                f'<td><span class="chip {run["status"].lower()}">{_e(run["status"])}</span></td><td>{_e(run["invocations"])}</td>'
                f'<td><code>{_e(" ".join(run["command"])[:160])}</code></td></tr>'
            )
            if run.get("matrix") or run.get("attachments"):
                cells = " · ".join(f"{name}: {value}" for name, value in run["matrix"].items()) or "none"
                attached = run.get("attachments") or 0
                extra = f" · {attached} attachment reference(s)" if attached else ""
                rows.append(f'<tr><td></td><td colspan="5">Execution matrix: {_e(cells)}{_e(extra)}</td></tr>')
    body = (
        '<div class="scroll"><table><caption>Where each state\'s test results came from</caption><thead><tr><th scope="col">State</th>'
        '<th scope="col">Adapter</th><th scope="col">Provenance</th><th scope="col">Status</th><th scope="col">Invocations</th>'
        f'<th scope="col">Command</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        if rows else "<p>No test results were produced or ingested.</p>"
    )
    return f'<section id="runs" aria-labelledby="h-runs"><h2 id="h-runs">Test runs and provenance</h2>{body}</section>'


def _list(items: list[str], empty: str) -> str:
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>" if items else f"<p>{_e(empty)}</p>"


def _stages_html(report: dict) -> str:
    q = report.get("candidate_qualification")
    if not q:
        return ""
    rows = "".join(
        f'<tr><th scope="row">{_e(s["stage"])}</th><td><span class="chip {s["status"].lower()}">{_e(s["status"])}</span></td><td></td></tr>'
        + "".join(
            f'<tr><td>{_e(c["check"])}</td><td><span class="chip {c["status"].lower()}">{_e(c["status"])}</span></td>'
            f'<td>{_e(c["summary"])}{_list(c["limitations"], "") if c["limitations"] else ""}</td></tr>'
            for c in s["checks"]
        )
        for s in q["stages"]
    )
    return (
        '<section id="qualification" aria-labelledby="h-qual"><h2 id="h-qual">Candidate qualification (test-the-tests)</h2>'
        f'<p>Ready for review: <strong>{"yes" if q["ready_for_review"] else "no"}</strong>. Five assurance pillars, each with its checks; a check that did not run is never shown as PASS.</p>'
        '<div class="scroll"><table><caption>Qualification stages</caption><thead><tr><th scope="col">Stage</th>'
        f'<th scope="col">Status</th><th scope="col">Evidence and limitations</th></tr></thead><tbody>{rows}</tbody></table></div>'
        f"{_stability_html(q)}</section>"
    )


def _stability_html(q: dict) -> str:
    records = (q.get("stability") or {}).get("records") or []
    if not records:
        return ""
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(r["invocation_id"])}</code></th><td>{_e(" / ".join(o or "?" for o in r["outcomes"]))}</td>'
        f'<td>{_e(" / ".join(f"{d:.3f}s" if d is not None else "?" for d in r["durations_s"]))}</td>'
        f'<td><span class="chip {r["verdict"].lower()}">{_e(r["verdict"])}</span></td></tr>'
        for r in records
    )
    return (
        '<div class="scroll"><table><caption>Bounded reruns (first outcome first; later passes never replace it)</caption>'
        '<thead><tr><th scope="col">Invocation</th><th scope="col">Outcomes</th><th scope="col">Durations</th>'
        f'<th scope="col">Verdict</th></tr></thead><tbody>{rows}</tbody></table></div>'
    )


def _changes_html(report: dict) -> str:
    cs = report.get("change_set")
    if not cs:
        return ""
    applied = set(cs.get("applied") or [])
    items = []
    for c in cs["changes"]:
        state = "applied" if c["change_id"] in applied else "Not applied"
        items.append(
            f'<details><summary><span class="chip {c["kind"].lower()}">{_e(c["kind"])}</span> {_e(c["path"])} — {_e(state)}</summary>'
            f'<p>{_e(c["reason"])}. Original fingerprint: <code>{_e((c["original_fingerprint"] or "none")[:12])}</code>, '
            f'candidate: <code>{_e((c["candidate_fingerprint"] or "none")[:12])}</code>.</p><pre>{_e(c["diff"])}</pre></details>'
        )
    return (
        '<section id="changes" aria-labelledby="h-changes"><h2 id="h-changes">Change set</h2>'
        "<p>Every change requires explicit human approval. Retirement candidates keep the original in the project until approved.</p>"
        + ("".join(items) or "<p>The candidate has no changes.</p>") + "</section>"
    )


def _findings_html(report: dict) -> str:
    findings = report["findings"]
    if not findings and report["workflow"] != "audit":
        return ""
    cards = "".join(
        f'<details class="finding" data-severity="{_e(f["severity"])}"><summary><span class="chip {f["severity"]}">{_e(f["severity"].upper())}</span> '
        f'<code>{_e(f["code"])}</code> {_e(f["summary"])}</summary><pre>{_e(json.dumps(f["evidence"], indent=2))}</pre></details>'
        for f in findings
    )
    recs = "".join(f"<li><code>{_e(r['finding'])}</code>: {_e(r['recommendation'])}</li>" for r in report.get("recommendations") or [])
    return (
        '<section id="findings" aria-labelledby="h-findings"><h2 id="h-findings">Findings</h2>'
        '<div class="filters"><label for="sev">Severity</label> <select id="sev"><option value="">All</option>'
        '<option>high</option><option>medium</option><option>info</option></select> '
        '<label for="q">Search</label> <input id="q" type="search"></div>'
        f"{cards or '<p>No findings within the executed adapter scope.</p>'}"
        f'<h3>Recommendations (proposed, not applied)</h3>{"<ul>" + recs + "</ul>" if recs else "<p>None.</p>"}</section>'
    )


def _surface_html(report: dict) -> str:
    checks = report.get("verification_surface") or []
    kinds = sorted({c["kind"] for c in checks})
    rows = "".join(
        f'<tr data-kind="{_e(c["kind"])}"><th scope="row">{_e(c["check_id"])}</th><td>{_e(c["kind"])}</td><td>{_e(c["origin"])}</td>'
        f'<td>{_e(c["gate"])}</td><td><code>{_e(c["command"] or c["tool"] or "")}</code></td><td>{_e(c["evidence_tier"])}</td>'
        f'<td>{_e("; ".join(c["limitations"]))}</td></tr>'
        for c in checks
    )
    options = "".join(f"<option>{_e(k)}</option>" for k in kinds)
    body = (
        f'<div class="filters"><label for="kind">Kind</label> <select id="kind"><option value="">All</option>{options}</select></div>'
        '<div class="scroll"><table id="surface"><caption>Declared verification checks (configuration is not run evidence)</caption>'
        '<thead><tr><th scope="col">Check</th><th scope="col">Kind</th><th scope="col">Origin</th><th scope="col">Gate</th>'
        f'<th scope="col">Command / tool</th><th scope="col">Tier</th><th scope="col">Limitations</th></tr></thead><tbody>{rows}</tbody></table></div>'
        if checks else "<p>No verification checks were recognized. The delivery surface is UNKNOWN, not empty.</p>"
    )
    return f'<section id="surface-section" aria-labelledby="h-surface"><h2 id="h-surface">Verification surface</h2>{body}</section>'


_CSS = """
:root{--bg:#fbfbfa;--fg:#1d1f21;--muted:#5d6166;--card:#fff;--line:#d9dadc;--accent:#2b5fab;
--pass:#1f7a3d;--fail:#b3261e;--warn:#8a5a00;--unk:#55595e;--c-baseline:#8a8f96;--c-candidate:#2b5fab;--c-applied:#1f7a3d;--c-current:#2b5fab}
@media (prefers-color-scheme: dark){:root:not([data-theme=light]){--bg:#151618;--fg:#e8e9ea;--muted:#a3a7ad;--card:#1e2023;--line:#3a3d42;
--accent:#8db4ef;--pass:#7fd39a;--fail:#ff9b92;--warn:#f2c46b;--unk:#b3b7bd;--c-baseline:#7c818a;--c-candidate:#8db4ef;--c-applied:#7fd39a;--c-current:#8db4ef}}
:root[data-theme=dark]{--bg:#151618;--fg:#e8e9ea;--muted:#a3a7ad;--card:#1e2023;--line:#3a3d42;--accent:#8db4ef;--pass:#7fd39a;
--fail:#ff9b92;--warn:#f2c46b;--unk:#b3b7bd;--c-baseline:#7c818a;--c-candidate:#8db4ef;--c-applied:#7fd39a;--c-current:#8db4ef}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer,nav{max-width:1100px;margin:0 auto;padding:0 16px}header{padding-top:24px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.2rem;margin-top:2rem;border-bottom:1px solid var(--line);padding-bottom:4px}
.note,.meta{color:var(--muted);font-size:.85em;font-weight:normal}a{color:var(--accent)}
nav ul{display:flex;flex-wrap:wrap;gap:4px 14px;padding:0;list-style:none}
:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;background:var(--card)}
caption{text-align:left;color:var(--muted);padding:6px 0}th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
.chip{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:0 8px;font-size:.8em;font-weight:600}
.pass{color:var(--pass)}.fail{color:var(--fail);font-weight:700}.blocked{color:var(--warn);border-style:double}
.unknown{color:var(--unk);border-style:dotted}.not_run{color:var(--unk);border-style:dashed;opacity:.8}
.improved,.killed,.stable,.applied{color:var(--pass)}.regressed,.high,.survived,.flaky_signal,.consistent_failure{color:var(--fail)}
.medium,.retire_candidate,.reused{color:var(--warn)}.executed{color:var(--pass)}.info,.changed,.unchanged,.insufficient_evidence{color:var(--unk)}
details{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 10px;margin:6px 0}summary{cursor:pointer}
pre{overflow-x:auto;font-size:.85em}.filters{margin:8px 0}figure{margin:12px 0}
svg .lbl,svg .val{fill:var(--fg);font-size:11px}.bar.baseline{fill:var(--c-baseline)}.bar.candidate{fill:var(--c-candidate)}
.bar.applied{fill:var(--c-applied)}.bar.current{fill:var(--c-current)}.swatch{display:inline-block;width:10px;height:10px;margin:0 4px}
.swatch.baseline{background:var(--c-baseline)}.swatch.candidate{background:var(--c-candidate)}.swatch.applied{background:var(--c-applied)}
.boundary{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.boundary>div{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 14px}
button{font:inherit;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:2px 10px}
"""

_JS = """
(function(){var r=document.documentElement,b=document.getElementById('theme');
b&&b.addEventListener('click',function(){var d=r.getAttribute('data-theme')==='dark'||(!r.getAttribute('data-theme')&&matchMedia('(prefers-color-scheme: dark)').matches);
r.setAttribute('data-theme',d?'light':'dark');b.setAttribute('aria-pressed',String(!d));});
function f(){var s=(document.getElementById('sev')||{}).value||'',q=((document.getElementById('q')||{}).value||'').toLowerCase();
document.querySelectorAll('.finding').forEach(function(e){e.hidden=(s&&e.dataset.severity!==s)||(q&&e.textContent.toLowerCase().indexOf(q)<0);});}
['sev','q'].forEach(function(i){var e=document.getElementById(i);e&&e.addEventListener('input',f);});
var k=document.getElementById('kind');k&&k.addEventListener('input',function(){document.querySelectorAll('#surface tbody tr').forEach(function(t){t.hidden=k.value&&t.dataset.kind!==k.value;});});})();
"""


def render_html(report: dict) -> str:
    project = report["project"]
    title = f"Assertiva {report['workflow']} — {project.get('name') or 'project'}"
    table, chart = _metrics_table(report)
    boundary = report["claim_boundary"]
    sections = [("summary", "Summary"), ("metrics", "States and metrics")]
    if report.get("test_selection"):
        sections.append(("selection", "Test selection"))
    if report.get("history"):
        sections.append(("history", "History"))
    if report.get("delivery") or report.get("review_candidates"):
        sections.append(("delivery", "Delivery"))
    if report.get("candidate_qualification"):
        sections.append(("qualification", "Qualification"))
    if any((s or {}).get("negative_paths") for s in report["states"].values()):
        sections.append(("negative-paths", "Negative paths"))
    if any((s or {}).get("mutation") for s in report["states"].values()):
        sections.append(("mutation-evidence", "Mutation"))
    if any((s or {}).get("artifacts") for s in report["states"].values()):
        sections.append(("artifact-evidence", "Artifact"))
    if report.get("change_set"):
        sections.append(("changes", "Change set"))
    if report["findings"] or report["workflow"] == "audit":
        sections.append(("findings", "Findings"))
    sections += [
        ("runs", "Runs"), ("budget", "Budget"), ("surface-section", "Verification surface"), ("green", "What does green prove?"),
        ("unknowns", "Remaining unknowns"), ("provenance", "Provenance"),
    ]
    nav = "".join(f'<li><a href="#{i}">{_e(t)}</a></li>' for i, t in sections)
    delta = report.get("evidence_delta")
    delta_html = (
        "<p>Evidence delta — " + ", ".join(f"{k}: {len(v)}" for k, v in delta.items()) + ". Test count is contextual.</p>"
        if delta else ""
    )
    states_present = [ _STATE_LABELS[k] for k, v in report["states"].items() if v]
    applied_note = "" if report["states"].get("applied") or report["workflow"] != "improve" else "<p><strong>Not applied.</strong> Candidate values were observed in an isolated copy.</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)}</title><style>{_CSS}</style></head>
<body>
<header><h1>{_e(title)}</h1>
<p class="meta">Status <span class="chip {_e(report['status'].lower())}">{_e(report['status'])}</span> · revision <code>{_e((project.get('revision') or 'none')[:12])}</code>
{' (uncommitted changes)' if project.get('dirty') else ''} · generated {_e(report['generated_at'])}
<button id="theme" type="button" aria-pressed="false" aria-label="Toggle dark theme">Theme</button></p></header>
<nav aria-label="Report sections"><ul>{nav}</ul></nav>
<main>
<section id="summary" aria-labelledby="h-summary"><h2 id="h-summary">Summary</h2>
<p>Workflow: <strong>{_e(report['workflow'])}</strong>. States shown: {_e(', '.join(states_present) or 'none')}.</p>{applied_note}{delta_html}</section>
<section id="metrics" aria-labelledby="h-metrics"><h2 id="h-metrics">States and metrics</h2>{table}{chart}</section>
{_stages_html(report)}{_negative_html(report)}{_mutation_html(report)}{_artifact_html(report)}{_changes_html(report)}{_runs_html(report)}{_budget_html(report)}{_findings_html(report)}{_selection_html(report)}{_history_html(report)}{_delivery_html(report)}{_surface_html(report)}
<section id="green" aria-labelledby="h-green"><h2 id="h-green">What does green prove?</h2><div class="boundary">
<div><h3>Observed</h3>{_list(boundary['observed'], 'Nothing was observed.')}</div>
<div><h3>Not evidenced</h3>{_list(boundary['not_evidenced'], 'Nothing listed.')}</div>
<div><h3>Limitations</h3>{_list(boundary.get('limitations') or [], 'None recorded.')}</div></div></section>
<section id="unknowns" aria-labelledby="h-unknowns"><h2 id="h-unknowns">Remaining unknowns</h2>{_list(report.get('remaining_unknowns') or [], 'None recorded.')}</section>
<section id="provenance" aria-labelledby="h-prov"><h2 id="h-prov">Provenance</h2><pre>{_e(json.dumps(report['provenance'], indent=2))}</pre></section>
</main>
<footer><p class="meta">Assertiva Assurance Report v{REPORT_VERSION}. Offline, self-contained. Evidence over green status.</p></footer>
<script>{_JS}</script>
</body></html>
"""
