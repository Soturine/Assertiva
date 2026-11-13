"""Opt-in CI gate over a finished audit report (``assertiva audit --fail-on CONDITION``).

Without ``--fail-on`` nothing changes: exit 0 means the audit ran to completion and wrote its report, whatever the
audited tests did (2 is refusal or misuse, 3 a read-only violation). With it, each named condition is checked against
the report, never against anything re-run, and exit 1 means the gate failed. The decision and its reasons are
written into the report (``gate``) so the exit status can always be explained.

Decision matrix (a run is one entry of ``states.current.runs``; *executed* means provenance ENGINE_EXECUTED):

| condition          | fails the gate when                                                                   |
|--------------------|---------------------------------------------------------------------------------------|
| ``test-failure``   | an executed run is FAIL                                                               |
| ``not-passing``    | no run was executed, or an executed run is FAIL, BLOCKED, UNKNOWN or NOT_RUN          |
| ``imported-failure`` | ingested results (JUnit, CTRF, Allure, a CI export) report FAIL                     |
| ``artifact``       | an artifact qualification ran and is not PASS                                         |
| ``high-findings``  | a finding of severity high                                                            |
| ``findings``       | any finding                                                                           |

A condition that has nothing to judge (``artifact`` with no artifact, ``imported-failure`` with nothing ingested)
does not fail the gate and says so; ``not-passing`` is the one that refuses an empty run. Limitations never fail a
gate by themselves: they are reported with the evidence.
"""

from __future__ import annotations

CONDITIONS = {
    "test-failure": "an executed run is FAIL",
    "not-passing": "no run was executed, or an executed run is not PASS (FAIL, BLOCKED, UNKNOWN, NOT_RUN)",
    "imported-failure": "ingested test results report FAIL",
    "artifact": "an artifact qualification ran and is not PASS",
    "high-findings": "a finding of severity high",
    "findings": "any finding",
}
GATE_FAILED = 1


def evaluate(report: dict, conditions: list[str]) -> dict:
    """The gate's verdict for ``conditions`` over ``report``: PASS or FAIL, with one line per condition."""
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        raise ValueError(f"unknown --fail-on condition(s): {', '.join(unknown)}; known: {', '.join(CONDITIONS)}")
    current = (report.get("states") or {}).get("current") or {}
    runs = current.get("runs") or []
    executed = [r for r in runs if r.get("provenance") == "ENGINE_EXECUTED"]
    imported = [r for r in runs if r.get("provenance") != "ENGINE_EXECUTED"]
    artifacts = current.get("artifacts") or []
    findings = report.get("findings") or []

    def label(run: dict) -> str:
        return f"{run.get('adapter')} {run.get('status')}"

    checks = []
    for condition in dict.fromkeys(conditions):
        if condition == "test-failure":
            bad = [label(r) for r in executed if r.get("status") == "FAIL"]
            note = None if executed else "no run was executed: nothing to judge (use not-passing to refuse that)"
        elif condition == "not-passing":
            bad = [label(r) for r in executed if r.get("status") != "PASS"] or ([] if executed else ["no run was executed"])
            note = None
        elif condition == "imported-failure":
            bad = [label(r) for r in imported if r.get("status") == "FAIL"]
            note = None if imported else "no results were ingested: nothing to judge"
        elif condition == "artifact":
            bad = [f"{a.get('artifact') or a.get('kind')} {a.get('status')}" for a in artifacts if a.get("status") != "PASS"]
            note = None if artifacts else "no artifact was qualified: nothing to judge"
        elif condition == "high-findings":
            bad = [f["code"] for f in findings if f.get("severity") == "high"]
            note = None
        else:  # findings
            bad = [f["code"] for f in findings]
            note = None
        checks.append({"condition": condition, "fails_when": CONDITIONS[condition], "result": "FAIL" if bad else "PASS",
                       "because": bad[:20], "count": len(bad), **({"note": note} if note else {})})
    return {"result": "FAIL" if any(c["result"] == "FAIL" for c in checks) else "PASS", "conditions": checks,
            "exit_code_on_fail": GATE_FAILED,
            "basis": "the report of this audit only; nothing was re-run to decide"}
