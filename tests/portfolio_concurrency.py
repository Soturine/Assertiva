"""Concurrency experiment for the portfolio registry (CP-F2): separate processes, one ASSERTIVA_HOME.

    python tests/portfolio_concurrency.py HOME PROJECT_DIR WORKERS ROUNDS

Each worker records ROUNDS sightings of one shared feedback entry and ROUNDS entries of its own. Afterwards the
registry must hold every sighting and every entry, as valid JSON, and no worker may have failed. Prints a JSON verdict.
Used by tests/test_portfolio.py and runnable by hand on any OS.
"""

from __future__ import annotations

import json
import os
import sys
from multiprocessing import get_context
from pathlib import Path


def worker(args):
    home, index, rounds = args
    os.environ["ASSERTIVA_HOME"] = home
    from assertiva import portfolio

    errors = []
    for r in range(rounds):
        try:
            portfolio.add_feedback("demo", "FALSE_POSITIVE", "SHARED", "one shared issue", "synthetic", "dev", run_id=f"w{index}-{r}")
            portfolio.add_feedback("demo", "MISSING_ANALYSIS", f"OWN-{index}-{r}", f"own issue {index}-{r}", "synthetic", "dev")
        except Exception as exc:  # recorded: an error is a finding of the experiment, not a crash of it
            errors.append(f"{type(exc).__name__}: {exc}"[:200])
    return errors


def main(home: str, project: str, workers: int, rounds: int) -> dict:
    os.environ["ASSERTIVA_HOME"] = home
    from assertiva import portfolio

    portfolio.add(project, name="demo")
    with get_context("spawn").Pool(workers) as pool:
        errors = [e for result in pool.map(worker, [(home, i, rounds) for i in range(workers)]) for e in result]
    text = (Path(home) / "portfolio" / "registry.json").read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        valid = True
    except ValueError:
        data, valid = {"feedback": {}}, False
    shared = next((f for f in data["feedback"].values() if f["rule"] == "SHARED"), {"sightings": []})
    own = [f for f in data["feedback"].values() if f["rule"].startswith("OWN-")]
    expected = workers * rounds
    return {"valid_json": valid, "errors": errors[:5], "error_count": len(errors), "shared_sightings": len(shared["sightings"]),
            "own_entries": len(own), "expected_each": expected,
            "lost": (expected - len(shared["sightings"])) + (expected - len(own)), "project_kept": "demo" in data.get("projects", {})}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))))
