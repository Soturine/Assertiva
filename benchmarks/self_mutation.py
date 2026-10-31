"""Engine-run mutation of Assertiva's own failures.py with named tests, written as a complete per-mutant record.

    python benchmarks/self_mutation.py TREE OUT.json [LABEL]

TREE is a checkout of this repository (a `git archive` export of a commit). The engine's orchestrator runs Cosmic Ray
on assertiva/failures.py with tests/test_failures.py and tests/test_failure_headline.py (what `audit --mutate FILE
--mutate-tests PATH` does after its native run). Budget: at most 300 mutants (the engine's cap), Cosmic Ray's 60 s per
mutant; run it under an outer time limit. Every mutant is written with file, line, operator, status and its stable
id; paths are relative to TREE, nothing else of the machine is recorded. The classification of survivors is a
conservative lead (see `classify`), never a claim of equivalence.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

TARGET = "assertiva/failures.py"
TESTS = ["tests/test_failures.py", "tests/test_failure_headline.py"]


def classify(line_text: str, operator: str | None) -> str:
    """A lead for a human, not a verdict: a mutation of a `|` inside a type annotation is an EQUIVALENCE_CANDIDATE (with
    postponed evaluation it does not change a normal call, but it can change __annotations__, typing.get_type_hints()
    and tools that read type metadata); every other survivor's behavioral impact is UNKNOWN until someone reads it."""
    annotation = bool(re.search(r"->|:\s*[\w\[\], .]*\|", line_text)) and "BitOr" in (operator or "")
    return "EQUIVALENCE_CANDIDATE_ANNOTATION" if annotation else "IMPACT_UNKNOWN"


def main(tree: str, out: str, label: str = "") -> dict:
    sys.path.insert(0, str(Path(tree).resolve()))
    from assertiva.adapters.mutation import run_mutation_tool

    root = Path(tree).resolve()
    started = time.perf_counter()
    run = run_mutation_tool(root, sys.executable, [TARGET], "cosmic-ray", root, TESTS)
    source = (root / TARGET).read_text(encoding="utf-8").splitlines()
    mutants = []
    for m in run.mutants:
        record = {"id": m.mutant_id, "stable_id": m.stable_id, "file": m.path, "line": m.line, "operator": m.operator,
                  "status": m.status.value}
        if m.status.value == "SURVIVED":
            record["lead"] = classify(source[m.line - 1] if m.line and m.line <= len(source) else "", m.operator)
        mutants.append(record)
    leads: dict[str, int] = {}
    for record in mutants:
        if "lead" in record:
            leads[record["lead"]] = leads.get(record["lead"], 0) + 1
    data = {"label": label, "tool": run.tool, "tool_version": run.tool_version, "provenance": "ENGINE_EXECUTED",
            "error": run.error, "finished": run.finished, "target": TARGET, "tests": TESTS,
            "selection": (run.config or {}).get("test_selection"), "counts": run.counts, "survivor_leads": leads,
            "leads_note": "EQUIVALENCE_CANDIDATE_ANNOTATION is a candidate, not proven equivalence; IMPACT_UNKNOWN is unread",
            "wall_clock_s": round(time.perf_counter() - started, 1), "mutants": mutants}
    Path(out).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    return {k: data[k] for k in ("label", "counts", "survivor_leads", "wall_clock_s", "error")}


if __name__ == "__main__":
    print(json.dumps(main(*sys.argv[1:4])))
