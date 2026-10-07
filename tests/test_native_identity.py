"""Which identities are compared, and what "passed" counts.

The static inventory counts runnable nodes: direct test definitions plus inherited/composed materializations. It never
expands `parametrize`. A native run reports invocations: one per runnable node per parameter case. Comparing the two
reports a divergence for every parameterized suite. The comparable native unit is the materialization (the node id
without its parameter suffix).

A run's invocations include skipped cases; "executed and passed" must count passed invocations, not all invocations.
"""

import sys

import pytest

from assertiva.audit import run_audit
from assertiva.report import render_html

from conftest import write


def _findings(report: dict) -> dict:
    return {f["code"]: f for f in report["findings"]}


@pytest.mark.integration
def test_parameterized_cases_are_not_a_static_native_divergence(tmp_path):
    root = tmp_path / "params"
    write(root / "conftest.py", "")
    write(root / "tests" / "test_math.py",
          "import pytest\n\n@pytest.mark.parametrize('n', [1, 2, 3, 4])\ndef test_double(n):\n    assert n * 2 == n + n\n\n"
          "def test_zero():\n    assert 0 + 0 == 0\n")
    report = run_audit(root, execute=True, python=sys.executable)
    assert report["states"]["current"]["metrics"]["test_invocations"]["value"] == 5  # 4 cases + 1
    assert "STATIC_INVENTORY_DIVERGES_FROM_NATIVE" not in _findings(report)  # 2 runnable nodes on both sides


@pytest.mark.integration
def test_tests_the_static_inventory_cannot_see_are_a_divergence(tmp_path):
    root = tmp_path / "dynamic"
    write(root / "conftest.py", "")
    write(root / "tests" / "test_dynamic.py",
          "def test_static():\n    assert 1 == 1\n\n"
          "for _i in range(3):\n    globals()[f'test_generated_{_i}'] = lambda: None\n")
    report = run_audit(root, execute=True, python=sys.executable)
    finding = _findings(report).get("STATIC_INVENTORY_DIVERGES_FROM_NATIVE")
    assert finding is not None
    assert finding["evidence"]["static_definitions_and_materializations"] == 1
    assert finding["evidence"]["native_materializations"] == 4


def _passing_report_with_skips(calc_project) -> dict:
    report = run_audit(calc_project)
    state = report["states"]["current"]
    state["runs"] = [{"adapter": "pytest-native", "mode": "execute", "status": "PASS", "command": ["pytest"], "exit_code": 0,
                      "invocations": 530, "outcomes": {"PASSED": 522, "SKIPPED": 8}, "collection_errors": [], "limitations": [],
                      "matrix": {}, "attachments": 0}]
    for name, value in (("test_invocations", 530), ("passed", 522), ("skipped", 8), ("failed", 0), ("errors", 0)):
        state["metrics"][name] = {"value": value, "direction": "CONTEXTUAL", "unit": None, "evidence_tier": "E1"}
    return report


def test_confirmed_counts_passed_cases_not_all_invocations(calc_project):
    page = render_html(_passing_report_with_skips(calc_project))
    decision = page[page.index('id="overview"'):page.index('id="findings"')]
    assert "530 test cases executed and passed" not in decision and "530 test cases · passed" not in decision
    assert "522 test cases passed" in decision and "8 skipped" in decision
