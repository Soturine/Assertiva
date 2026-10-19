"""Score Assertiva's test-effectiveness candidates against human labels on the confirmation fixtures.

    python benchmarks/effectiveness.py [--json OUT] [FIXTURE_DIR ...]

Each fixture directory holds a ``labels.json``: every test the extractors find is labeled with the candidate kinds a
careful reviewer expects (empty for a correct test, including deliberate look-alikes). A test the extractors find
without a label, or a label for a test they do not find, makes the fixture invalid rather than silently scored.
Scoring is per (test, kind): precision and recall per kind and overall, the look-alikes wrongly nominated, the time the
static reading took, and whether the fixture tree is unchanged afterwards (the reading never writes). Nothing is
executed. The confirmation fixtures are not used to tune rules (those use ``tests/fixtures/effectiveness-matrix``);
see ``benchmarks/README.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from assertiva.adapters.test_facts import collect  # noqa: E402
from assertiva.effectiveness import candidates  # noqa: E402
from assertiva.workspace import tree_fingerprint  # noqa: E402

CONFIRMATION = ROOT / "tests" / "fixtures" / "confirmation"
FROZEN = {"v2": ROOT / "benchmarks" / "confirmation-v2.sha256"}  # frozen sets: content digests of every file


def digest(path: Path) -> str:
    """sha256 of a fixture file with line endings normalized (a Windows checkout writes CRLF)."""
    import hashlib

    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def frozen_changes(name: str) -> list[str]:
    """Files of a frozen set that differ from its manifest, were added or were removed (empty: still frozen)."""
    root = CONFIRMATION / name
    listed = dict(reversed(line.split("  ", 1)) for line in FROZEN[name].read_text(encoding="utf-8").splitlines() if line.strip())
    present = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    return sorted([f"changed: {r}" for r, p in present.items() if r in listed and digest(p) != listed[r]]
                  + [f"added: {r}" for r in present if r not in listed] + [f"removed: {r}" for r in listed if r not in present])


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 3) if den else None


def score(fixture: Path) -> dict:
    labels = json.loads((fixture / "labels.json").read_text(encoding="utf-8"))["tests"]
    before = tree_fingerprint(fixture)
    started = time.perf_counter()
    facts, _ = collect(fixture)
    found = candidates(facts)
    elapsed = round(time.perf_counter() - started, 3)
    unchanged = tree_fingerprint(fixture) == before
    ids = {f.test_id for f in facts}
    problems = [f"unlabeled test: {t}" for t in sorted(ids - set(labels))] + [f"label for a test not found: {t}" for t in sorted(set(labels) - ids)]
    expected = {(t, k) for t, label in labels.items() for k in label["expect"]}
    predicted = {(t, c.kind) for c in found for t in c.tests}
    kinds = sorted({k for _, k in expected | predicted})
    per_kind = {}
    for kind in kinds:
        e = {p for p in expected if p[1] == kind}
        p = {q for q in predicted if q[1] == kind}
        per_kind[kind] = {"tp": len(e & p), "fp": len(p - e), "fn": len(e - p),
                          "precision": _ratio(len(e & p), len(p)), "recall": _ratio(len(e & p), len(e)),
                          "missed": sorted(t for t, _ in e - p), "false_positives": sorted(t for t, _ in p - e)}
    clean = {t for t, label in labels.items() if not label["expect"]}
    return {
        "fixture": fixture.relative_to(ROOT).as_posix() if fixture.is_relative_to(ROOT) else str(fixture),
        "valid": not problems, "problems": problems, "tests": len(ids), "labeled_pairs": len(expected),
        "overall": {"tp": len(expected & predicted), "fp": len(predicted - expected), "fn": len(expected - predicted),
                    "precision": _ratio(len(expected & predicted), len(predicted)), "recall": _ratio(len(expected & predicted), len(expected))},
        "per_kind": per_kind,
        "correct_tests_nominated": sorted(t for t, _ in predicted if t in clean),
        "cost": {"static_reading_s": elapsed, "executed_project_code": False},
        "safety": {"fixture_unchanged": unchanged},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("fixtures", nargs="*", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    fixtures = args.fixtures or sorted(p.parent for p in CONFIRMATION.glob("*/*/labels.json"))
    results = [score(f.resolve()) for f in fixtures]
    totals = {k: sum(r["overall"][k] for r in results) for k in ("tp", "fp", "fn")}
    summary = {"fixtures": results, "total": {**totals, "precision": _ratio(totals["tp"], totals["tp"] + totals["fp"]),
                                              "recall": _ratio(totals["tp"], totals["tp"] + totals["fn"])}}
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    for r in results:
        o = r["overall"]
        print(f"{r['fixture']}: tests {r['tests']}, precision {o['precision']}, recall {o['recall']} "
              f"(tp {o['tp']}, fp {o['fp']}, fn {o['fn']}), unchanged {r['safety']['fixture_unchanged']}, {r['cost']['static_reading_s']}s"
              + ("" if r["valid"] else f" INVALID: {r['problems']}"))
        for kind, k in r["per_kind"].items():
            if k["missed"] or k["false_positives"]:
                print(f"  {kind}: missed {k['missed']} false positives {k['false_positives']}")
    t = summary["total"]
    print(f"total: precision {t['precision']}, recall {t['recall']} (tp {t['tp']}, fp {t['fp']}, fn {t['fn']})")
    return 0 if all(r["valid"] and r["safety"]["fixture_unchanged"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
