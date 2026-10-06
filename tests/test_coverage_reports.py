"""Portable coverage: numerators and denominators survive; percentages over different populations
are never compared as if they measured the same thing."""

import json
import sys

import pytest

from assertiva.adapters.coverage_reports import load_coverage_report
from assertiva.candidate import DeltaState, QualificationCheck, StageStatus

from conftest import write

LCOV = """TN:
SF:src/price.js
FNF:2
FNH:1
DA:1,1
DA:2,0
LF:10
LH:8
BRF:4
BRH:3
end_of_record
SF:src/cart.js
LF:10
LH:6
BRF:6
BRH:2
end_of_record
"""
COBERTURA = """<?xml version="1.0" ?>
<coverage line-rate="0.75" branch-rate="0.5" lines-covered="15" lines-valid="20" branches-covered="5" branches-valid="10" version="7.0" timestamp="1">
  <sources><source>/project/src</source></sources>
  <packages/>
</coverage>
"""
COBERTURA_RATES_ONLY = '<?xml version="1.0" ?><coverage line-rate="0.8" branch-rate="0.6" version="1.9"><packages/></coverage>'
JACOCO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<report name="shop">
  <package name="com/example"><counter type="LINE" missed="1" covered="1"/></package>
  <counter type="INSTRUCTION" missed="30" covered="70"/>
  <counter type="BRANCH" missed="4" covered="12"/>
  <counter type="LINE" missed="5" covered="45"/>
  <counter type="METHOD" missed="2" covered="8"/>
</report>
"""


def counts(summary, kind):
    return summary.counts[kind]["covered"], summary.counts[kind]["total"]


def test_lcov_totals_keep_numerators_and_denominators(tmp_path):
    summary = load_coverage_report(write(tmp_path / "lcov.info", LCOV))
    assert counts(summary, "line") == (14, 20) and counts(summary, "branch") == (5, 10)
    assert counts(summary, "function") == (1, 2)
    assert summary.line_percent == 70.0 and summary.branch_percent == 50.0
    assert summary.tool == "lcov"


def test_cobertura_counts_and_rates_only(tmp_path):
    full = load_coverage_report(write(tmp_path / "coverage.xml", COBERTURA))
    assert counts(full, "line") == (15, 20) and counts(full, "branch") == (5, 10) and full.tool == "cobertura"
    rates = load_coverage_report(write(tmp_path / "rates.xml", COBERTURA_RATES_ONLY))
    assert rates.line_percent == 80.0 and rates.counts == {}
    assert any("denominator" in item for item in rates.limitations)


def test_jacoco_report_level_counters(tmp_path):
    summary = load_coverage_report(write(tmp_path / "jacoco.xml", JACOCO))
    assert counts(summary, "line") == (45, 50) and counts(summary, "branch") == (12, 16)
    assert counts(summary, "instruction") == (70, 100) and counts(summary, "method") == (8, 10)
    assert summary.tool == "jacoco"


def test_coverage_py_json_and_istanbul_summary(tmp_path):
    py = load_coverage_report(write(tmp_path / "coverage.json", json.dumps(
        {"meta": {"version": "7.16.2"}, "totals": {"covered_lines": 90, "num_statements": 100, "covered_branches": 30,
                                                    "num_branches": 40, "percent_covered": 85.7}})))
    assert counts(py, "line") == (90, 100) and counts(py, "branch") == (30, 40) and py.tool == "coverage.py"
    istanbul = load_coverage_report(write(tmp_path / "coverage-summary.json", json.dumps(
        {"total": {"lines": {"total": 8, "covered": 6, "pct": 75}, "branches": {"total": 6, "covered": 3, "pct": 50},
                   "functions": {"total": 2, "covered": 2, "pct": 100}, "statements": {"total": 9, "covered": 7, "pct": 77.7}}})))
    assert counts(istanbul, "line") == (6, 8) and counts(istanbul, "branch") == (3, 6) and istanbul.tool == "istanbul"


@pytest.mark.parametrize("content", ["{", "<html/>", "SF:x\nLH:notanumber\n"])
def test_unreadable_or_unknown_reports_are_errors(tmp_path, content):
    summary = load_coverage_report(write(tmp_path / "report.txt", content))
    assert summary.error and summary.counts == {} and summary.line_percent is None


def _state(covered, total):
    from assertiva.evidence import StateEvidence
    from assertiva.models import CoverageSummary

    state = StateEvidence("s", "test")
    state.coverage.append(CoverageSummary(counts={"branch": {"covered": covered, "total": total}}, tool="fixture"))
    return state


def test_more_covered_over_a_larger_population_is_not_a_blind_percentage_judgment():
    from assertiva.evidence import compare_states

    deltas = {d.name: d for d in compare_states(_state(80, 100), _state(90, 120))}
    assert deltas["branch_covered"].state is DeltaState.IMPROVED  # 80 -> 90
    assert deltas["branch_total"].state is DeltaState.CHANGED  # 100 -> 120
    percent = deltas["branch_coverage"]
    assert (percent.baseline, percent.candidate) == (80.0, 75.0)
    assert percent.state is DeltaState.CHANGED  # not REGRESSED: different populations
    assert "80/100" in percent.note and "90/120" in percent.note and "denominator" in percent.note


def test_same_population_keeps_percentage_direction():
    from assertiva.evidence import compare_states

    deltas = {d.name: d for d in compare_states(_state(80, 100), _state(90, 100))}
    assert deltas["branch_coverage"].state is DeltaState.IMPROVED and deltas["branch_total"].state is DeltaState.UNCHANGED


@pytest.mark.parametrize(("candidate", "population_unknown", "fails"), [
    ((90, 120), True, False),  # covered up, missed up (20 -> 30): no single judgment
    ((90, 105), False, False),  # covered up, missed down (20 -> 15): better under every reading
    ((70, 120), False, True),  # fewer covered over a population that did not shrink
])
def test_coverage_stage_judges_population_changes_by_counts(candidate, population_unknown, fails):
    from assertiva.evidence import compare_states
    from assertiva.improve import _coverage_stage

    stage = _coverage_stage(compare_states(_state(80, 100), _state(*candidate)))
    assert ("population changed" in stage.summary) is population_unknown
    assert (stage.status is StageStatus.FAIL) is fails
    if population_unknown:
        assert stage.status is StageStatus.UNKNOWN and any("80/100 -> 90/120" in lim for lim in stage.limitations)


@pytest.mark.integration
@pytest.mark.parametrize(("candidate", "expected"), [((90, 120), StageStatus.UNKNOWN), ((70, 120), StageStatus.FAIL)])
def test_coverage_stage_does_not_pass_when_the_population_changed(calc_project, candidate, expected):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    session = start_improve(calc_project, python=sys.executable)
    try:
        session.baseline_evidence.coverage = _state(80, 100).coverage
        write(session.workspace / "lcov.info", f"SF:a\nLF:10\nLH:10\nBRF:{candidate[1]}\nBRH:{candidate[0]}\nend_of_record\n")
        q = qualify_candidate(session, stability_reruns=0, coverage_reports={"candidate": session.workspace / "lcov.info"}).qualification
    finally:
        discard_session(session)
    stage = next(s for s in q.checks if s.check is QualificationCheck.COVERAGE_AND_ORACLES)
    assert stage.status is expected


def test_audit_ingests_any_coverage_format_for_any_stack(tmp_path):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    root = tmp_path / "js-ish"
    write(root / "README.md", "no adapter here\n")
    report = run_audit(root, coverage_reports=[write(tmp_path / "lcov.info", LCOV)])
    metrics = report["states"]["current"]["metrics"]
    assert metrics["branch_covered"]["value"] == 5 and metrics["branch_total"]["value"] == 10
    assert "lcov" in render_html(report)
