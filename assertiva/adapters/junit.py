"""Portable JUnit XML results: a fallback for runners without a native adapter.

It says "these test results exist", not "this framework is understood": JUnit XML has
no parameter identity, xfail/xpass, materialization, fixture graph, coverage or retry
semantics, so those stay unknown.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import Outcome, RunEvidence, TestInvocation

MESSAGE_LIMIT = 1000
FORMAT_LIMITS = [
    "JUnit XML has no parameter identity, xfail/xpass, retry or materialization semantics; those are unknown",
    "no coverage, fixture graph or declaration provenance is available from JUnit XML",
    "results were produced outside Assertiva; the revision and environment they ran against are not verified",
]
_OUTCOME_TAGS = (("failure", Outcome.FAILED), ("error", Outcome.ERROR), ("skipped", Outcome.SKIPPED))


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def load_junit(path: str | Path) -> RunEvidence:
    path = Path(path)
    run = RunEvidence(adapter_id="junit-xml", mode="report", status=StageStatus.UNKNOWN, command=[f"read {path}"])
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        run.status = StageStatus.BLOCKED
        run.limitations.append(f"JUnit XML could not be read: {exc}")
        return run
    run.limitations += FORMAT_LIMITS
    suites: list[dict] = []
    system_out = 0

    def visit(element: ET.Element, prefix: str) -> None:
        nonlocal system_out
        name = prefix
        if element.tag in ("testsuite", "testsuites") and element.get("name"):
            name = f"{prefix}/{element.get('name')}" if prefix else element.get("name")
        if element.tag == "testsuite":
            props = {p.get("name"): p.get("value") for p in element.findall("properties/property")}
            suites.append({"name": name, "timestamp": element.get("timestamp"), "properties": props})
        for child in element:
            if child.tag in ("testsuite", "testsuites"):
                visit(child, name)
            elif child.tag == "testcase":
                outcome, message = Outcome.PASSED, None
                for tag, state in _OUTCOME_TAGS:
                    node = child.find(tag)
                    if node is not None:
                        outcome = state
                        message = (node.get("message") or (node.text or "")).strip()[:MESSAGE_LIMIT] or None
                        break
                for stream in ("system-out", "system-err"):
                    system_out += sum(len(s.text or "") for s in child.findall(stream))
                case = "::".join(x for x in (child.get("classname"), child.get("name")) if x)
                invocation_id = f"{name}::{case}" if name else case
                run.invocations.append(
                    TestInvocation(
                        invocation_id=invocation_id, declaration_id=invocation_id, materialization_id=invocation_id,
                        outcome=outcome, duration_s=_float(child.get("time")), message=message,
                    )
                )
            elif child.tag in ("system-out", "system-err"):
                system_out += len(child.text or "")

    visit(root, "")
    run.metadata = {"source": str(path), "suites": suites[:50], "system_out_chars": system_out}
    outcomes = [inv.outcome for inv in run.invocations]
    if any(o in (Outcome.FAILED, Outcome.ERROR) for o in outcomes):
        run.status = StageStatus.FAIL
    elif not outcomes or all(o is Outcome.SKIPPED for o in outcomes):
        run.status = StageStatus.UNKNOWN
        run.limitations.append("the report contains no executed test cases")
    else:
        run.status = StageStatus.PASS
    run.wall_clock_s = round(sum(inv.duration_s or 0 for inv in run.invocations), 6) or None
    return run
