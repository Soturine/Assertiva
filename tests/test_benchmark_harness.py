"""The benchmark sets are valid input: every test is labeled, reading never writes, the scorer counts (test, kind)
pairs as its README says, v1 (spent, now a regression set) keeps its recorded results, and v2 stays frozen."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))

import effectiveness as bench  # noqa: E402

from conftest import write  # noqa: E402


def test_every_benchmark_fixture_is_fully_labeled_and_left_unchanged():
    fixtures = sorted(p.parent for p in bench.CONFIRMATION.glob("*/*/labels.json"))
    assert {f.parent.name for f in fixtures} == {"v1", "v2"} and len(fixtures) >= 6
    for fixture in fixtures:
        result = bench.score(fixture)
        assert result["valid"], result["problems"]
        assert result["safety"]["fixture_unchanged"] and not result["cost"]["executed_project_code"]


def test_v1_is_a_regression_set_with_its_recorded_results():
    # v1 exposed the redundancy defect fixed in 0.7.3 and is spent for confirmation; its results are pinned so that
    # a change that loses a detection or adds a false positive shows here (update deliberately when a gap is closed)
    results = {r.name: bench.score(r) for r in sorted((bench.CONFIRMATION / "v1").iterdir()) if r.is_dir()}
    assert {n: r["overall"]["fp"] for n, r in results.items()} == {"js-shipping": 0, "kt-thermostat": 0, "py-loans": 0}
    missed = sorted(t for r in results.values() for k in r["per_kind"].values() for t in k["missed"])
    assert missed == ["src/rates.test.js › each@55"]  # known gap: test.each bodies are not read for oracles


def test_v2_is_frozen():
    assert bench.frozen_changes("v2") == []  # a frozen confirmation set is never edited; a new one gets a new name


def test_scoring_counts_test_and_kind_pairs_and_flags_unlabeled_tests(tmp_path):
    write(tmp_path / "tests" / "test_a.py",
          "def test_ok():\n    assert f(1) == 2\n\n\ndef test_tautology():\n    assert 1 == 1\n\n\ndef test_unlabeled():\n    assert g() is not None\n")
    write(tmp_path / "labels.json", json.dumps({"tests": {
        "tests/test_a.py::test_ok": {"expect": ["WEAK_ORACLE"], "why": "deliberately wrong label: a miss"},
        "tests/test_a.py::test_tautology": {"expect": ["FALSE_GREEN"], "why": "constant"}}}))
    result = bench.score(tmp_path)
    assert not result["valid"] and result["problems"] == ["unlabeled test: tests/test_a.py::test_unlabeled"]
    assert result["per_kind"]["FALSE_GREEN"]["tp"] == 1
    assert result["per_kind"]["WEAK_ORACLE"]["missed"] == ["tests/test_a.py::test_ok"]
