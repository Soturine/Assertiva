"""A mutation report is evidence about the state it was produced for, and only the state it can be tied to.

0.7.2 compared only the mutated production sources: a report produced before the candidate's tests were written
matched the candidate (improve changes tests, not production code), and a report with no sources at all (PIT,
mutmut) passed the fault-sensitivity check and decided retirements without being tied to anything.
"""

from __future__ import annotations

import json

from assertiva.adapters.mutation import load_mutation_report
from assertiva.candidate import StageStatus
from assertiva.evidence import StateEvidence, attach_mutation
from assertiva.improve import _mutation_stage, _retirement
from assertiva.models import MutantRecord, MutantStatus, MutationRun

from conftest import write


def _mte(tmp_path, prod_source, test_source):
    report = tmp_path / "mte.json"
    report.write_text(json.dumps({
        "schemaVersion": "2", "thresholds": {}, "config": {"disableBail": True},
        "files": {"src/price.js": {"language": "javascript", "source": prod_source, "mutants": [
            {"id": "1", "mutatorName": "M", "status": "Killed", "killedBy": ["0"], "location": {"start": {"line": 1, "column": 1}}}]}},
        "testFiles": {"src/price.test.js": {"source": test_source, "tests": [{"id": "0", "name": "prices"}]}}}), encoding="utf-8")
    return load_mutation_report(report)


def test_a_report_produced_for_other_tests_is_not_evidence_about_these(tmp_path):
    state_dir = tmp_path / "candidate"
    write(state_dir / "src" / "price.js", "export const price = (x) => x * 2\n")
    write(state_dir / "src" / "price.test.js", "test('prices', () => expect(price(2)).toBe(4))\n")
    stale = _mte(tmp_path, "export const price = (x) => x * 2\n", "test('prices', () => expect(price(2)).toBeTruthy())\n")
    run = attach_mutation(StateEvidence("candidate", "copy"), stale, state_dir)
    assert run.matches_state is False and any("price.test.js" in lim for lim in run.limitations)


def test_a_report_whose_sources_and_tests_match_is_tied(tmp_path):
    state_dir = tmp_path / "candidate"
    write(state_dir / "src" / "price.js", "export const price = (x) => x * 2\n")
    write(state_dir / "src" / "price.test.js", "test('prices', () => expect(price(2)).toBe(4))\n")
    fresh = _mte(tmp_path, "export const price = (x) => x * 2\n", "test('prices', () => expect(price(2)).toBe(4))\n")
    assert attach_mutation(StateEvidence("candidate", "copy"), fresh, state_dir).matches_state is True


def _untied(*mutants):
    run = MutationRun(source="mutations.xml", tool="PIT", mutants=list(mutants), killers_complete=True)
    run.counts = {}
    for m in mutants:
        run.counts[m.status.value] = run.counts.get(m.status.value, 0) + 1
    return run


def _mutant(mid, *killers, status=MutantStatus.KILLED):
    return MutantRecord(mutant_id=mid, status=status, native_status=status.value, path="a/Calc.java", line=1, killed_by=killers)


def test_an_untied_report_never_passes_the_fault_sensitivity_check(tmp_path):
    candidate = StateEvidence("candidate", "copy")
    candidate.mutation = [_untied(_mutant("m1", "a.CalcTest.t"))]
    result = _mutation_stage(candidate)
    assert result.status is StageStatus.UNKNOWN and "cannot be tied" in result.summary  # 0.7.2: PASS


def test_an_untied_report_never_decides_a_retirement(tmp_path):
    baseline = StateEvidence("baseline", "copy")
    baseline.mutation = [_untied(_mutant("m1", "tests/test_old.py::test_a", "tests/test_new.py::test_a"))]
    from assertiva.candidate import CandidateChangeKind, CandidateTestChange

    change = CandidateTestChange(change_id="tests/test_old.py", path="tests/test_old.py", kind=CandidateChangeKind.RETIRE_CANDIDATE, reason="r")
    failures, unknown, passed = _retirement([change], baseline)
    assert not passed and any("cannot be tied" in u for u in unknown)  # 0.7.2: passed
