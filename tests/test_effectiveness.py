"""Test effectiveness: one model over normalized facts, the same rules in every language.

The matrix fixture writes the same defects in Python, JavaScript and Kotlin; each rule is accepted only when it
fires in every ecosystem, and the strong control test is never nominated anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from assertiva.adapters.mutation import load_mutation_report
from assertiva.adapters.test_facts import collect
from assertiva.audit import run_audit
from assertiva.candidate import CandidateChangeKind, CandidateTestChange, StageStatus
from assertiva.effectiveness import TestFacts as Facts, candidates, metrics, mutation_contribution, summarize
from assertiva.evidence import StateEvidence
from assertiva.improve import _mutation_stage, _owned_by, _retirement
from assertiva.models import MutantRecord, MutantStatus, MutationRun
from assertiva.report_html import render_html

from test_report import assert_schema_shape

MATRIX = Path(__file__).parent / "fixtures" / "effectiveness-matrix"

# defect -> the test that carries it, per language (the control test carries none)
EXPECTED = {
    "python": {"control": "test_total_applies_discount", "SWALLOWED_EXCEPTION": "test_total_swallowed",
               "CONDITIONAL_ASSERTION": "test_total_conditional", "TAUTOLOGY": "test_total_tautology",
               "STATUS_ONLY": "test_status_only", "BROAD_ERROR": "test_any_error", "FIDELITY": "test_publishes_total",
               "REDUNDANCY": ("test_sum_copy_one", "test_sum_copy_two"), "DUPLICATE_CASES": "test_rows", "WAIT": "test_waits"},
    "javascript": {"control": "applies discount", "SWALLOWED_EXCEPTION": "swallowed", "CONDITIONAL_ASSERTION": "conditional",
                   "TAUTOLOGY": "tautology", "STATUS_ONLY": "status only", "BROAD_ERROR": "any error", "FIDELITY": "publishes total",
                   "REDUNDANCY": ("sum copy one", "sum copy two"), "DUPLICATE_CASES": "each@", "WAIT": "waits"},
    "jvm": {"control": "appliesDiscount", "SWALLOWED_EXCEPTION": "swallowed", "CONDITIONAL_ASSERTION": "conditional",
            "TAUTOLOGY": "tautology", "STATUS_ONLY": "statusOnly", "BROAD_ERROR": "anyError", "FIDELITY": "publishesTotal",
            "REDUNDANCY": ("sumCopyOne", "sumCopyTwo"), "DUPLICATE_CASES": "rows", "WAIT": "waits"},
}


def _name(test_id: str) -> str:
    return test_id.replace(" › ", "::").rsplit("::", 1)[-1]


@pytest.fixture(scope="module")
def matrix():
    facts, limits = collect(MATRIX)
    return facts, summarize(facts, limits)


@pytest.mark.parametrize("language", sorted(EXPECTED))
def test_the_same_defects_are_found_in_every_language(matrix, language):
    facts, summary = matrix
    expected = EXPECTED[language]
    found = [c for c in summary["candidates"] if c["language"] == language]
    names = lambda kind, key=None, value=None: {_name(t) for c in found if c["kind"] == kind  # noqa: E731
                                                and (key is None or c["detail"].get(key) == value) for t in c["tests"]}
    for smell in ("SWALLOWED_EXCEPTION", "CONDITIONAL_ASSERTION", "TAUTOLOGY"):
        assert names("FALSE_GREEN", "pattern", smell) == {expected[smell]}, smell
    assert names("WEAK_ORACLE") == {expected["STATUS_ONLY"], expected["BROAD_ERROR"]}
    assert names("FIDELITY_MISMATCH") == {expected["FIDELITY"]}
    assert names("REDUNDANCY") == set(expected["REDUNDANCY"])
    duplicates = names("DUPLICATE_CASES")
    assert len(duplicates) == 1 and next(iter(duplicates)).startswith(expected["DUPLICATE_CASES"])
    assert {_name(t) for c in found if c["kind"] == "SMELL" for t in c["tests"]} == {expected["WAIT"]}
    nominated = {_name(t) for c in found for t in c["tests"]}
    assert expected["control"] in {_name(f.test_id) for f in facts if f.language == language}
    assert expected["control"] not in nominated  # a strong, direct test is never a candidate
    assert summary["languages"][language]["limitations"]  # each extractor states what it cannot see


def test_every_candidate_states_its_basis_and_what_would_settle_it(matrix):
    _, summary = matrix
    for c in summary["candidates"]:
        assert c["shows"] and c["why"] and c["resolve_with"] and c["recommendation"]
        assert c["basis"] in ("INFERRED", "CONFIRMED", "UNKNOWN")
    assert "score" not in json.dumps(summary).lower().replace("no score", "")


def _facts(test_id, **kw):
    base = dict(path="t", language="x", oracles=("VALUE",), body_signature="same", component=".")
    return Facts(test_id=test_id, **{**base, **kw})


def test_same_assertions_after_different_setup_are_not_redundant():
    found = candidates([_facts("a", oracle_signature="r == 7", body_signature="r = total([3, 4])"),
                        _facts("b", oracle_signature="r == 7", body_signature="r = total([7])")])
    assert not [c for c in found if c.kind == "REDUNDANCY"]


def test_identical_tests_of_different_components_are_not_redundant():
    found = candidates([_facts("a", component="web"), _facts("b", component="mobile")])
    assert not [c for c in found if c.kind == "REDUNDANCY"]
    assert [c for c in candidates([_facts("a"), _facts("b")]) if c.kind == "REDUNDANCY"]


def test_integration_with_one_real_boundary_is_not_a_fidelity_mismatch():
    honest = _facts("a", declared_level="INTEGRATION", boundaries=("DATABASE", "HTTP"), simulated=("HTTP",))
    fake = _facts("b", declared_level="INTEGRATION", boundaries=("HTTP",), simulated=("HTTP",), body_signature="other")
    found = [c for c in candidates([honest, fake]) if c.kind == "FIDELITY_MISMATCH"]
    assert [c.tests for c in found] == [["b"]]


def test_exception_ignored_in_cleanup_is_not_a_false_green(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_cleanup.py").write_text(
        "def test_reads(tmp_path):\n"
        "    handle = open(tmp_path / 'f', 'w')\n"
        "    try:\n"
        "        assert handle.writable()\n"
        "    finally:\n"
        "        try:\n"
        "            handle.close()\n"
        "        except OSError:\n"
        "            pass\n", encoding="utf-8")
    facts, _ = collect(tmp_path)
    assert facts and "SWALLOWED_EXCEPTION" not in facts[0].smells


def _run(*mutants, locations=None):
    run = MutationRun(source="m.json", mutants=list(mutants), test_locations=dict(locations or {}))
    run.counts = {MutantStatus.KILLED.value: len(mutants)}
    return run


def _mutant(mid, *killers, status=MutantStatus.KILLED):
    return MutantRecord(mutant_id=mid, status=status, native_status=status.value, path="src/pricing.py", line=int(mid[1:]),
                        operator="op", killed_by=killers)


def test_mutation_contribution_separates_exclusive_from_shared_detection():
    view = mutation_contribution([_run(_mutant("m1", "a"), _mutant("m2", "a", "b"), _mutant("m3", "b"))])
    assert view["available"]
    assert view["tests"] == {"a": {"kills": 2, "exclusive": 1}, "b": {"kills": 2, "exclusive": 1}}
    assert view["exclusive_protection"] == {"a": ["m1"], "b": ["m3"]}
    assert not mutation_contribution([_run(_mutant("m1"))])["available"]  # no killing tests named: no claim


def _retire(path):
    return CandidateTestChange("c1", path, CandidateChangeKind.RETIRE_CANDIDATE, "removed in candidate")


def _state(*runs):
    return StateEvidence(label="baseline", observed_in="copy", mutation=list(runs))


def test_retiring_the_only_detector_of_a_mutant_fails_fault_sensitivity():
    baseline = _state(_run(_mutant("m1", "tests/test_old.py::test_edge"), _mutant("m2", "tests/test_old.py::test_a", "tests/test_new.py::test_a")))
    failures, unknown, passed = _retirement([_retire("tests/test_old.py")], baseline)
    assert failures and "RETIRED_TEST_EXCLUSIVE_DETECTION" in failures[0] and "src/pricing.py:1" in failures[0]
    result = _mutation_stage(StateEvidence(label="candidate", observed_in="copy"), [_retire("tests/test_old.py")], baseline)
    assert result.status is StageStatus.FAIL


def test_retiring_tests_whose_detections_are_shared_passes_that_check():
    baseline = _state(_run(_mutant("m1", "tests/test_old.py::test_a", "tests/test_new.py::test_a")))
    assert _retirement([_retire("tests/test_old.py")], baseline)[0] == []
    result = _mutation_stage(StateEvidence(label="candidate", observed_in="copy"), [_retire("tests/test_old.py")], baseline)
    assert result.status is StageStatus.PASS


def test_retirement_without_per_test_detection_is_not_proven():
    _, unknown, _ = _retirement([_retire("tests/test_old.py")], _state())
    assert unknown and "not proven" in unknown[0]
    result = _mutation_stage(StateEvidence(label="candidate", observed_in="copy"), [_retire("tests/test_old.py")], _state())
    assert result.status is StageStatus.NOT_RUN  # never a pass without evidence


def test_killing_tests_are_matched_to_retired_files_in_each_report_style():
    assert _owned_by("tests/test_old.py::test_a", None, "tests/test_old.py")
    assert _owned_by("17", "src/old.test.js", "src/old.test.js")
    assert _owned_by("demo.OldTest.edge(demo.OldTest)", "demo/OldTest", "src/test/kotlin/demo/OldTest.kt")
    assert not _owned_by("demo.NewTest.edge(demo.NewTest)", "demo/NewTest", "src/test/kotlin/demo/OldTest.kt")
    assert not _owned_by("tests/test_old_extra.py::test_a", None, "tests/test_old.py")


def test_mutation_reports_name_the_file_or_class_of_each_killing_test(tmp_path):
    report = tmp_path / "mutation.json"
    report.write_text(json.dumps({
        "schemaVersion": "2", "thresholds": {"high": 80, "low": 60},
        "files": {"src/pricing.js": {"language": "javascript", "source": "", "mutants": [
            {"id": "1", "mutatorName": "ArithmeticOperator", "status": "Killed", "killedBy": ["0"], "location": {"start": {"line": 2, "column": 1}}}]}},
        "testFiles": {"src/pricing.test.js": {"tests": [{"id": "0", "name": "applies discount"}]}},
    }), encoding="utf-8")
    assert load_mutation_report(report).test_locations == {"0": "src/pricing.test.js"}
    pit = tmp_path / "mutations.xml"
    pit.write_text(
        "<mutations><mutation detected='true' status='KILLED'><sourceFile>Pricing.kt</sourceFile><mutatedClass>demo.Pricing</mutatedClass>"
        "<mutatedMethod>total</mutatedMethod><lineNumber>3</lineNumber><mutator>MATH</mutator>"
        "<killingTest>demo.PricingTest.[engine:junit-jupiter]/[class:demo.PricingTest]/[method:appliesDiscount()]</killingTest>"
        "<description>replaced</description></mutation></mutations>", encoding="utf-8")
    run = load_mutation_report(pit)
    assert set(run.test_locations.values()) == {"demo/PricingTest"}


def test_effectiveness_metrics_compare_states_without_a_score(matrix):
    _, summary = matrix
    values = metrics(summary)
    assert values["false_green_candidates"] == 9 and values["fidelity_mismatches"] == 3 and values["redundancy_candidates"] == 3
    assert set(values) == {"false_green_candidates", "fidelity_mismatches", "redundancy_candidates", "distinct_oracle_signatures"}


def test_audit_reports_effectiveness_with_findings_panel_and_schema():
    report = run_audit(MATRIX)
    assert_schema_shape(report)
    assert set(report["test_effectiveness"]["languages"]) == {"python", "javascript", "jvm"}
    codes = {f["code"] for f in report["findings"]}
    assert {"FALSE_GREEN_CANDIDATE", "TEST_FIDELITY_MISMATCH", "REDUNDANCY_CANDIDATE", "WEAK_ORACLE_SIGNAL"} <= codes
    html = render_html(report)
    assert 'id="effectiveness"' in html and "RETIRED" not in html
    assert "Efetividade dos testes" in render_html(report, lang="pt-BR")


# --- calibration: negatives that must not be nominated, from the dogfood and from each ecosystem's idioms ----------

CALIBRATION = {
    "py/tests/test_cases.py": '''
import time
import unittest

import pytest


def assert_total(value, expected):
    assert value == expected


def test_session_expires_after_ttl(cache):
    cache.put("k", 1, ttl=0.01)
    time.sleep(0.02)
    assert cache.get("k") is None


def test_branch_checks_both_paths(flag):
    if flag:
        assert compute() == 1
    else:
        assert compute() == 2


def test_uses_helper():
    assert_total(compute(), 3)


class Base(unittest.TestCase):
    def check(self, value):
        self.assertEqual(value, 3)


class TestInherited(Base):
    def test_inherited_helper(self):
        self.check(compute())


@pytest.mark.asyncio
async def test_async_value(service):
    assert await service.total() == 3
''',
    "js/package.json": '{"name": "calibration"}',
    "js/src/cases.test.ts": '''
import { expect, test } from '@playwright/test'

test('fills the form', async ({ page }) => {
  await page.fill('#qty', '2')
  await expect(page.locator('#total')).toHaveText('6')
})

test('debounce waits before saving', async () => {
  await new Promise((r) => setTimeout(r, 300))
  expect(save).toHaveBeenCalledTimes(1)
})

test('both branches check', () => {
  if (mode === 'a') {
    expect(run()).toBe(1)
  } else {
    expect(run()).toBe(2)
  }
})

test('every item is priced', () => {
  items.forEach((item) => expect(item.price).toBe(3))
})

test('rejects awaited', async () => {
  await expect(load()).rejects.toThrow('not found')
})
''',
    "jvm/build.gradle.kts": "",
    "jvm/src/test/kotlin/demo/CasesTest.kt": '''
package demo

class CasesTest {
    @Test
    fun accepts() = assertTrue(isValid("abc"))

    @Test
    fun requestTimesOut() {
        Thread.sleep(50)
        assertThrows<TimeoutException> { client.await() }
    }

    @Test
    fun bothBranches() {
        if (flag) {
            assertEquals(1, run())
        } else {
            fail("unexpected mode")
        }
    }
}
''',
}


@pytest.fixture(scope="module")
def calibration(tmp_path_factory):
    root = tmp_path_factory.mktemp("calibration")
    for rel, text in CALIBRATION.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    facts, limits = collect(root)
    return {_name(f.test_id): f for f in facts}, summarize(facts, limits)


def test_calibration_negatives_are_not_nominated(calibration):
    facts, summary = calibration
    expected = {"test_session_expires_after_ttl", "test_branch_checks_both_paths", "test_uses_helper", "test_inherited_helper",
                "test_async_value", "fills the form", "debounce waits before saving", "both branches check",
                "every item is priced", "rejects awaited", "accepts", "requestTimesOut", "bothBranches"}
    assert expected <= set(facts), expected - set(facts)
    nominated = {_name(t) for c in summary["candidates"] for t in c["tests"]}
    assert not nominated & expected, nominated & expected


def test_calibration_reads_each_idiom(calibration):
    facts, _ = calibration
    assert facts["fills the form"].oracles == ("VALUE",)  # the `({ page })` parameter is not mistaken for the body
    assert facts["accepts"].oracles == ("VALUE",)  # Kotlin expression body; a predicate checked exactly pins a value
    assert facts["requestTimesOut"].oracles == ("SPECIFIC_ERROR",) and "SLEEP" not in facts["requestTimesOut"].smells
    assert "HELPER" in facts["test_uses_helper"].oracles
    assert facts["rejects awaited"].oracles == ("SPECIFIC_ERROR",) and "UNAWAITED_ASYNC" not in facts["rejects awaited"].smells


def test_an_unawaited_rejection_and_a_sleep_without_timing_subject_stay_leads(tmp_path):
    (tmp_path / "a.test.js").write_text(
        "test('loads', () => {\n  expect(load()).rejects.toThrow('x')\n})\n"
        "test('saves', async () => {\n  await new Promise((r) => setTimeout(r, 300))\n  expect(saved()).toBe(true)\n})\n", encoding="utf-8")
    facts = {_name(f.test_id): f for f in collect(tmp_path)[0]}
    assert "UNAWAITED_ASYNC" in facts["loads"].smells and "FIXED_WAIT" in facts["saves"].smells
    found = summarize(list(facts.values()), {})["candidates"]
    assert all(c["basis"] == "INFERRED" for c in found if c["kind"] in ("FALSE_GREEN", "SMELL"))  # leads, never confirmed


def test_the_agent_decides_each_candidate_and_the_engine_fact_stays():
    """Agent-led: a candidate is the engine's lead; the agent's assessment confirms or rejects it per test, with
    evidence, and the engine's finding is kept unchanged beside that decision."""
    from assertiva.assessment import apply_assessment

    report = run_audit(MATRIX)
    green = [f for f in report["findings"] if f["code"] == "FALSE_GREEN_CANDIDATE"]
    assert len({f["id"] for f in green}) == len(green) == 9  # one reviewable finding per language and pattern
    target = next(f for f in green if f["evidence"]["language"] == "python" and f["evidence"]["detail"]["pattern"] == "CONDITIONAL_ASSERTION")
    assert target["evidence"]["basis"] == "INFERRED" and target["evidence"]["count"] == 1
    out = apply_assessment(report, {"run_id": report["run_id"], "summary": "Reviewed the conditional test.", "findings": [],
                                    "dispositions": [{"finding": target["id"], "disposition": "FALSE_POSITIVE",
                                                      "rationale": "The flag is a fixture that is always set in this suite.",
                                                      "evidence": ["py/tests/test_pricing.py:18"], "scope": {"reviewed": 1, "of": 1}}]})
    kept = next(f for f in out["findings"] if f["id"] == target["id"])
    assert kept["evidence"] == target["evidence"] and kept["summary"] == target["summary"]
    assert kept["assessment"]["disposition"] == "FALSE_POSITIVE" and kept["priority"] == "none"


def test_an_expected_exception_in_the_else_branch_is_a_check(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_branch.py").write_text(
        "import pytest\n\n"
        "@pytest.mark.parametrize('bad', [False, True])\n"
        "def test_verify(bad):\n"
        "    if not bad:\n"
        "        assert verify() == 1\n"
        "    else:\n"
        "        with pytest.raises(ValueError):\n"
        "            verify()\n", encoding="utf-8")
    [fact] = collect(tmp_path)[0]
    assert "CONDITIONAL_ASSERTION" not in fact.smells  # found by running the model on Assertiva's own suite


def test_fixture_projects_inside_test_directories_are_inputs_not_tests(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.test.js").write_text("test('own', () => {\n  expect(f()).toBe(1)\n})\n", encoding="utf-8")
    fixture = tmp_path / "tests" / "fixtures" / "bad-project" / "src"
    fixture.mkdir(parents=True)
    (fixture / "b.test.js").write_text("test('seeded defect', () => {\n  expect(true).toBe(true)\n})\n", encoding="utf-8")
    facts, limits = collect(tmp_path)
    assert [_name(f.test_id) for f in facts] == ["own"]  # found by the self-audit: seeded defects were counted
    assert any("fixture projects" in limit for limit in limits["javascript"])
    assert collect(MATRIX)[0]  # a fixture audited as its own project is still read
