"""One test's chain of evidence, read back from the last audit (never re-run): what it claims, how it checks, what
ran it and on which copy of the code, which mutants it detected, what it does not observe, and what stays unknown.

Static facts come from reading the test now (they are flagged if the project changed since the audit); execution and
mutation come from the audit report. A link the evidence does not show is UNKNOWN, never filled in.
"""

from __future__ import annotations

import json
from pathlib import Path

from .dependencies import SKIPPED_DIRS
from .workspace import capture_baseline, read_only_guard, state_dir


class ExplainError(ValueError):
    """No audit to read, or no test matches."""


def _match(test: str, ids) -> list[str]:
    exact = [i for i in ids if i == test]
    return exact or [i for i in ids if i.endswith(test) or i.endswith("::" + test) or test in i]


def _outside_scope(root: Path, test: str, inventoried: set[str]) -> str | None:
    """`file::name` of a Python test function the configured inventory does not include (outside testpaths)."""
    import ast

    name = test.split("::")[-1]
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in inventoried or SKIPPED_DIRS & set(path.relative_to(root).parts) or not path.name.startswith("test"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name for n in tree.body):
            return f"{rel}::{name}"
    return None


def explain(root: str | Path, test: str, report_dir: str | Path | None = None) -> dict:
    from .adapters.test_facts import collect

    root = Path(root).resolve()
    stored = Path(report_dir or state_dir(root, "reports")) / "audit.json"
    if not stored.is_file():
        raise ExplainError(f"no audit report for this project ({stored}); run `assertiva audit` first")
    report = json.loads(stored.read_text(encoding="utf-8"))
    with read_only_guard(root):
        facts, _ = collect(root)
        digest = capture_baseline(root).digest
    matches = _match(test, [f.test_id for f in facts])
    if not matches:
        outside = _outside_scope(root, test, {f.path for f in facts})
        if outside:
            return {"test": outside, "scope": "OUTSIDE_RUNNER_SCOPE", "executed": [], "mutation": [], "candidates": [],
                    "not_observed": [], "audit": {"run_id": report.get("run_id"), "report": str(stored)},
                    "unknowns": ["no run in the audit executed this test: its file is outside the runner's configured test "
                                 "paths, so no run collects it and nothing it checks is evidence"]}
        raise ExplainError(f"no test matches {test!r} in the static inventory")
    if len(matches) > 1:
        raise ExplainError(f"{test!r} matches several tests: " + ", ".join(matches[:8]))
    fact = next(f for f in facts if f.test_id == matches[0])
    current = (report.get("states") or {}).get("current") or {}
    unknowns = []
    if (report.get("project") or {}).get("digest") != digest:
        unknowns.append("the project changed since the audit: execution and mutation below describe the audited tree")
    file, _, name = fact.test_id.partition("::")
    executions = []
    for run in current.get("runs") or []:
        outcomes = run.get("outcomes_by_invocation") or {}
        hits = {i: o for i, o in outcomes.items() if i == fact.test_id or i.startswith(fact.test_id + "[")
                or (i.startswith(file) and i.endswith(name.split("::")[-1]))}
        if hits:
            executions.append({"adapter": run.get("adapter"), "provenance": run.get("provenance"), "outcomes": hits,
                               "code_identity": (run.get("source_identity") or {}).get("status", "UNKNOWN"),
                               "limits": run.get("limits")})
    if not executions:
        unknowns.append("no run in the audit executed this test (static audit, deselected, or another runner's id)")
    mutation = []
    for run in current.get("mutation") or []:
        kills = {t: n for t, n in (run.get("kills_by_test") or {}).items() if t in (fact.test_id, name) or t.endswith(name)}
        mutation.append({"tool": run.get("tool"), "provenance": run.get("provenance"), "targets": run.get("targets"),
                         "detected": sum(kills.values()), "survivors_in_run": len(run.get("survivors") or []),
                         "killers_complete": run.get("killers_complete"),
                         "selection": (run.get("config") or {}).get("test_selection")})
    if not mutation:
        unknowns.append("no mutation evidence: whether this test would fail on a wrong value is not measured")
    elif all(m["detected"] == 0 for m in mutation):
        unknowns.append("this test is not named as detecting any mutant (tools often name only the first killer)")
    candidates = [{"kind": c.get("kind"), "summary": c.get("summary"), "basis": c.get("basis")}
                  for c in (report.get("test_effectiveness") or {}).get("candidates") or [] if fact.test_id in (c.get("tests") or [])]
    not_observed = sorted(set(fact.simulated)) and [f"{b} is replaced by a double" for b in sorted(set(fact.simulated))]
    if not fact.oracles:
        not_observed = [*(not_observed or []), "no oracle: nothing the test checks was found"]
    return {
        "test": fact.test_id, "language": fact.language,
        "claims": {"name": name.split("::")[-1], "declared_level": fact.declared_level},
        "oracle": {"kinds": list(fact.oracles), "assertions": fact.assertions, "surfaces": list(fact.surfaces),
                   "smells": list(fact.smells), "basis": "INFERRED: read from the test's source"},
        "exercises": {"boundaries": list(fact.boundaries), "simulated": list(fact.simulated), "doubles": list(fact.doubles)[:10]},
        "executed": executions, "mutation": mutation, "candidates": candidates,
        "not_observed": not_observed or [], "unknowns": unknowns, "audit": {"run_id": report.get("run_id"), "report": str(stored)},
    }
