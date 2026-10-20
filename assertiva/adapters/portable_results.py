"""Portable test results in and out: CTRF JSON and Allure result directories in; CTRF JSON out.

Like JUnit XML, they say "these results exist", not "this framework is understood". What each format carries is kept:
CTRF's per-attempt retries and flaky flag, Allure's declaration (``testCaseId``) apart from each parameterized
invocation (``historyId``) and its retries (repeated results of one invocation, first outcome kept). Host names,
threads, absolute paths and environment variables in the results are never copied into Assertiva's evidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import Outcome, RunEvidence, TestInvocation

MESSAGE_LIMIT = 1000
_LIMITS = [
    "results were produced outside Assertiva; the revision and environment they ran against are not verified",
    "no coverage, fixture graph or declaration provenance is available from portable results",
]
_CTRF = {"passed": Outcome.PASSED, "failed": Outcome.FAILED, "skipped": Outcome.SKIPPED, "pending": Outcome.SKIPPED}
_ALLURE = {"passed": Outcome.PASSED, "failed": Outcome.FAILED, "broken": Outcome.ERROR, "skipped": Outcome.SKIPPED}
_ABSOLUTE = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:home|Users|root|tmp|var|private)/)[^\s'\"]*")


def _scrub(text) -> str | None:
    """A message without absolute paths (they name users and machines), bounded."""
    if not text:
        return None
    return _ABSOLUTE.sub("<path>", str(text))[:MESSAGE_LIMIT]


def _status(run: RunEvidence) -> RunEvidence:
    outcomes = {inv.outcome for inv in run.invocations}
    run.status = StageStatus.FAIL if outcomes & {Outcome.FAILED, Outcome.ERROR} else StageStatus.PASS if run.invocations else StageStatus.UNKNOWN
    return run


def load_ctrf(path: str | Path) -> RunEvidence:
    path = Path(path)
    run = RunEvidence(adapter_id="ctrf", mode="report", status=StageStatus.UNKNOWN, command=[f"read {path}"], limitations=list(_LIMITS))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        results = data["results"]
        tool = results.get("tool") or {}
        run.metadata = {"format": f"CTRF {data.get('specVersion') or ''}".strip(), "tool": tool.get("name"), "tool_version": tool.get("version")}
        for test in results.get("tests") or []:
            raw = str(test.get("status"))
            outcome = _CTRF.get(raw)
            name = str(test["name"])
            source = str(test.get("filePath") or "").replace("\\", "/") or None
            attempts = 1 + int(test.get("retries") or 0)
            first = (test.get("retryAttempts") or [None])[0]
            message = test.get("message") or (first or {}).get("message") if outcome is not Outcome.PASSED else None
            run.invocations.append(TestInvocation(
                invocation_id=name, declaration_id=re.sub(r"\[.*\]$", "", name), materialization_id=name,
                parameters_id=(re.search(r"\[(.*)\]$", name) or [None, None])[1], outcome=outcome,
                duration_s=(test.get("duration") or 0) / 1000.0, message=_scrub(message), source_paths=(source,) if source else (),
                attempts=attempts if attempts > 1 else None,
                markers=("flaky",) if test.get("flaky") else (),
            ))
            if outcome is None:
                run.limitations.append(f"{name}: CTRF status {raw!r} has no outcome here; it stays unknown")
        if any(inv.attempts for inv in run.invocations):
            run.limitations.append("retried tests keep their final status; earlier attempts are counted, and a pass after "
                                   "failed attempts is flaky, not a clean pass")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        run.status, run.limitations = StageStatus.BLOCKED, [f"CTRF report could not be read: {type(exc).__name__}: {exc}"[:300]]
        return run
    return _status(run)


def load_allure(directory: str | Path) -> RunEvidence:
    directory = Path(directory)
    run = RunEvidence(adapter_id="allure", mode="report", status=StageStatus.UNKNOWN, command=[f"read {directory}"],
                      limitations=[*_LIMITS, "an Allure result directory keeps only the results written to it; a partial "
                                              "directory cannot show which tests did not run"])
    try:
        results = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*-result.json"))]
    except (OSError, ValueError) as exc:
        run.status, run.limitations = StageStatus.BLOCKED, [f"Allure results could not be read: {exc}"[:300]]
        return run
    by_invocation: dict[str, list[dict]] = {}
    for result in results:
        key = str(result.get("historyId") or result.get("fullName") or result.get("uuid"))
        by_invocation.setdefault(key, []).append(result)
    for key, attempts in by_invocation.items():
        attempts.sort(key=lambda r: r.get("start") or 0)
        final, first = attempts[-1], attempts[0]
        labels = {label.get("name"): label.get("value") for label in final.get("labels") or []}
        params = [f"{p.get('name')}={p.get('value')}" for p in final.get("parameters") or []]
        declaration = str(final.get("fullName") or final.get("name"))
        outcome = _ALLURE.get(str(final.get("status")))
        failing = next((a for a in attempts if a.get("status") in ("failed", "broken")), None)
        message = (failing or {}).get("statusDetails", {}).get("message") if failing else None
        start, stop = final.get("start"), final.get("stop")
        run.invocations.append(TestInvocation(
            invocation_id=declaration + (f"[{','.join(params)}]" if params else ""), declaration_id=declaration,
            materialization_id=str(final.get("testCaseId") or declaration), parameters_id=",".join(params) or None,
            outcome=outcome, duration_s=(stop - start) / 1000.0 if start and stop else None, message=_scrub(message),
            markers=tuple(f"{k}:{v}" for k, v in sorted(labels.items()) if k in ("suite", "parentSuite", "package", "framework", "tag")),
            attempts=len(attempts) if len(attempts) > 1 else None,
        ))
        if outcome is None:
            run.limitations.append(f"{declaration}: Allure status {final.get('status')!r} has no outcome here; it stays unknown")
        if first is not final and first.get("status") in ("failed", "broken") and outcome is Outcome.PASSED:
            run.metadata.setdefault("flaky", []).append(declaration)
    run.metadata.update({"format": "Allure results", "framework": next((labels.get("framework") for labels in
                         ({l.get("name"): l.get("value") for l in r.get("labels") or []} for r in results) if labels.get("framework")), None)})
    return _status(run)


def load_results(path: str | Path) -> RunEvidence:
    """Portable results by their shape: an Allure result directory, a CTRF JSON file, or JUnit XML."""
    from assertiva.adapters.junit import load_junit

    path = Path(path)
    if path.is_dir():
        return load_allure(path)
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096].lstrip()
    except OSError:
        head = ""
    if head.startswith("{") and '"results"' in head:
        return load_ctrf(path)
    return load_junit(path)


_TO_CTRF = {Outcome.PASSED: "passed", Outcome.FAILED: "failed", Outcome.ERROR: "failed", Outcome.SKIPPED: "skipped",
            Outcome.XFAILED: "passed", Outcome.XPASSED: "failed", Outcome.NOT_RUN: "other"}


def to_ctrf(runs: list[RunEvidence], tool: str, generated_by: str) -> dict:
    """CTRF 1.0 JSON for Assertiva's executed runs: one test per invocation with its first-attempt outcome and duration.
    Outcomes CTRF lacks keep their native value in ``rawStatus`` (an expected failure is a pass there, an unexpected
    pass a failure, as their runners report them); unknown outcomes are ``other``."""
    tests = []
    for run in runs:
        for inv in run.invocations:
            status = _TO_CTRF.get(inv.outcome, "other")
            entry = {"name": inv.invocation_id, "status": status, "duration": round((inv.duration_s or 0) * 1000)}
            if inv.outcome is not None and inv.outcome.value.lower() != status:
                entry["rawStatus"] = inv.outcome.value
            if inv.message and status in ("failed", "other"):
                entry["message"] = inv.message[:MESSAGE_LIMIT]
            if inv.source_paths:
                entry["filePath"] = inv.source_paths[0]
            if inv.attempts and inv.attempts > 1:
                entry["retries"] = inv.attempts - 1
            if inv.parameters_id:
                entry["parameters"] = {"id": inv.parameters_id}
            entry["extra"] = {"runner": run.adapter_id, "declaration": inv.declaration_id}
            tests.append(entry)
    counts = {k: sum(t["status"] == k for t in tests) for k in ("passed", "failed", "skipped", "pending", "other")}
    return {"reportFormat": "CTRF", "specVersion": "1.0.0", "generatedBy": generated_by,
            "results": {"tool": {"name": tool}, "summary": {"tests": len(tests), **counts, "start": 0, "stop": 0}, "tests": tests}}
