"""AXF-04 / DG-0101-01: a finding whose evidence list is cut states the complete count, so an assessment can never
declare the whole finding reviewed after reading only the listed items (Derivanta M1: 35 survivors, 20 listed,
"20/20 reviewed" accepted; M2: 70 survivors, 50 names, 20 sites)."""

import ast
from pathlib import Path

import pytest

from assertiva.assessment import AssessmentError, apply_assessment
from assertiva.audit import _mutation_findings
from assertiva.evidence import StateEvidence
from assertiva.models import MutantRecord, MutantStatus as S, MutationRun
from assertiva.report import _mutation_summary, engine_findings, survivor_sites

SOURCE = "".join(f"def f{i}(a, b):\n    return a + b\n" for i in range(20))


def run_with(survived: int, uncovered: int = 0, killed: int = 10) -> MutationRun:
    """Two mutants per line (sites < mutants), some not covered at all."""
    mutants, n = [], 0
    for status, count in ((S.SURVIVED, survived), (S.NO_COVERAGE, uncovered), (S.KILLED, killed)):
        for _ in range(count):
            line = 2 + 2 * ((n // 2) % 20)
            mutants.append(MutantRecord(f"m{n}", status, status.value, path="calc.py", line=line, operator="op", replacement=f"r{n}"))
            n += 1
    return MutationRun(source="cr.json", tool="cosmic-ray", mutants=mutants, sources={"calc.py": SOURCE}, matches_state=True,
                       counts={S.SURVIVED.value: survived, S.NO_COVERAGE.value: uncovered, S.KILLED.value: killed})


def survivors_finding(run: MutationRun) -> dict:
    [finding] = engine_findings(_mutation_findings(StateEvidence("current", "here", mutation=[run])))
    return finding


def report_for(finding: dict) -> dict:
    return {"workflow": "audit", "run_id": "r1", "findings": [finding], "recommendations": []}


def review(finding: dict, disposition: str, scope: dict | None, subjects=None) -> dict:
    entry = {"finding": finding["id"], "disposition": disposition, "rationale": "read the survivors", "evidence": ["calc.py:2"]}
    if scope:
        entry["scope"] = scope
    if subjects:
        entry["subjects"] = subjects
    return apply_assessment(report_for(finding), {"run_id": "r1", "summary": "s", "dispositions": [entry]})


def test_the_finding_counts_every_undetected_mutant_and_says_the_list_is_cut():
    finding = survivors_finding(run_with(survived=35))
    evidence = finding["evidence"]
    assert evidence["count"] == 35 and evidence["listed"] == 20 == len(evidence["survivors"])
    assert evidence["truncated"] is True and evidence["sites"] == 18  # two mutants per line: fewer sites than mutants
    assert len(evidence["mutant_ids"]) == 20 and evidence["mutant_ids"][0] == "m0"


def test_a_review_of_the_listed_twenty_cannot_close_thirty_five():
    finding = survivors_finding(run_with(survived=35))
    with pytest.raises(AssessmentError, match="35 items"):
        review(finding, "CONFIRMED", {"reviewed": 20, "of": 20})  # the M1 assessment, accepted by 0.10.0
    with pytest.raises(AssessmentError, match="needs every item"):
        review(finding, "CONFIRMED", None)
    with pytest.raises(AssessmentError, match="reviewed 20 of 35"):
        review(finding, "CONFIRMED", {"reviewed": 20, "of": 35})


def test_a_partial_review_is_recorded_as_partial_and_a_complete_one_as_complete():
    finding = survivors_finding(run_with(survived=35))
    partial = review(finding, "PARTIAL", {"reviewed": 20, "of": 35}, subjects=[{"subject": "m0", "disposition": "CONFIRMED"}])
    assert partial["findings"][0]["assessment"]["scope"] == {"reviewed": 20, "of": 35}
    whole = review(finding, "CONFIRMED", {"reviewed": 35, "of": 35})
    assert whole["findings"][0]["assessment"]["disposition"] == "CONFIRMED"


def test_uncovered_mutants_are_counted_and_listed_not_only_counted():
    evidence = survivors_finding(run_with(survived=3, uncovered=2))["evidence"]
    assert evidence["count"] == 5 and evidence["truncated"] is False
    assert sum(label.endswith("[no coverage]") for label in evidence["survivors"]) == 2  # 0.10.0 listed survivors only


def test_the_report_keeps_every_undetected_mutant_with_its_id():
    run = run_with(survived=70, uncovered=5)
    sites = survivor_sites(run)
    assert len(sites) == 75 and len({s["mutant_id"] for s in sites}) == 75  # 0.10.0: 20 sites for 70 survivors
    assert {s["status"] for s in sites} == {"SURVIVED", "NO_COVERAGE"}
    summary = _mutation_summary(run)
    assert summary["survivors_total"] == 70 and summary["survivors_truncated"] is True and len(summary["survivor_sites"]) == 75


def test_a_small_run_is_listed_whole_and_a_complete_review_needs_no_extra_scope_rules():
    finding = survivors_finding(run_with(survived=2))
    assert finding["evidence"]["truncated"] is False and finding["evidence"]["count"] == 2
    assert review(finding, "CONFIRMED", {"reviewed": 2, "of": 2})["findings"][0]["assessment"]["scope"]["of"] == 2


# --- the same rule for every engine finding: a cut list carries its complete count ----------------------------------

def _cut_lists_without_count():
    root = Path(__file__).parents[1] / "assertiva"
    out = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not (isinstance(call, ast.Call) and getattr(call.func, "id", None) == "Finding"):
                continue
            evidence = call.args[2] if len(call.args) > 2 else next((k.value for k in call.keywords if k.arg == "evidence"), None)
            if not isinstance(evidence, ast.Dict):
                continue
            keys = {k.value for k in evidence.keys if isinstance(k, ast.Constant)}
            cut = any(isinstance(n, ast.Slice) and isinstance(n.upper, ast.Constant) for v in evidence.values for n in ast.walk(v))
            spread = any(k is None for k in evidence.keys)  # `**_undetected(run)` carries its own count
            if cut and not spread and not keys & {"count", "total"}:
                out.append(f"{path.name}:{call.lineno} {ast.literal_eval(call.args[0]) if call.args else '?'}")
    return out


def test_no_engine_finding_cuts_a_list_without_its_complete_count():
    assert _cut_lists_without_count() == []


# --- pinned by the targeted mutation of assessment.py (0.10.1 candidate): survivors on the review-scope path ----------

from assertiva.assessment import item_count  # noqa: E402


def test_the_item_count_prefers_the_complete_count_and_falls_back_to_a_single_list_only():
    assert item_count({"evidence": {"count": 35, "survivors": ["a"] * 20}}) == 35
    assert item_count({"evidence": {"tests": ["a", "b", "c"]}}) == 3  # no count, one list: its length
    assert item_count({"evidence": {"tests": ["a"], "files": ["b", "c"]}}) is None  # two lists: not decidable
    assert item_count({"evidence": {}}) is None


def test_a_complete_review_of_more_than_256_items_is_accepted():
    finding = survivors_finding(run_with(survived=300, killed=0))  # `of is not items` would refuse this one
    assert review(finding, "CONFIRMED", {"reviewed": 300, "of": 300})["findings"][0]["assessment"]["scope"]["of"] == 300


@pytest.mark.parametrize("reviewed", [0, -1])
def test_a_scope_must_review_at_least_one_item(reviewed):
    finding = survivors_finding(run_with(survived=3))
    with pytest.raises(AssessmentError, match="0 < n <= total"):
        review(finding, "PARTIAL", {"reviewed": reviewed, "of": 3}, subjects=[{"subject": "m0", "disposition": "CONFIRMED"}])


def test_a_single_item_finding_can_be_confirmed_without_a_scope():
    finding = survivors_finding(run_with(survived=1))
    assert review(finding, "CONFIRMED", None)["findings"][0]["assessment"]["disposition"] == "CONFIRMED"
