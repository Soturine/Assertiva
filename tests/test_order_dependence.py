"""A test that fails in the full run and passes when rerun alone is either intermittent or order dependent. The
stability reruns run the relevant tests alone, so they cannot tell; one bounded rerun of the full run can."""

from __future__ import annotations

import sys

import pytest

from assertiva.improve import discard_session, qualify_candidate, start_improve

from conftest import write

pytestmark = pytest.mark.integration


def _stability(project, candidate_tests: str, name: str = "test_state.py"):
    session = start_improve(project, python=sys.executable)
    try:
        write(session.workspace / "tests" / name, candidate_tests)
        result = qualify_candidate(session)
        records = {r.invocation_id.rsplit("::", 1)[-1]: r for r in result.stability.records}
        [check] = [c for s in result.qualification.stages for c in s.checks if c.check.value == "STABILITY_AND_COST"]
        return records, check
    finally:
        discard_session(session)


def test_a_failure_that_repeats_in_suite_order_and_not_alone_is_order_dependent(calc_project):
    # an unchanged test leaves shared state behind; the candidate's new test only passes when it runs first or alone
    write(calc_project / "registry.py", "ITEMS = []\n")
    write(calc_project / "tests" / "test_a_register.py",
          "import registry\n\ndef test_registers():\n    registry.ITEMS.append(1)\n    assert registry.ITEMS\n")
    records, check = _stability(calc_project, "import registry\n\ndef test_b_starts_empty():\n    assert registry.ITEMS == []\n",
                                name="test_b_empty.py")
    record = records["test_b_starts_empty"]
    assert record.verdict == "ORDER_DEPENDENT_SUSPECT", record
    assert "full run" in record.probe and check.status.value == "FAIL" and "ORDER_DEPENDENT_SUSPECT" in check.summary


def test_a_failure_that_does_not_repeat_in_suite_order_stays_intermittent(calc_project, tmp_path):
    counter = (tmp_path / "count").as_posix()
    records, _ = _stability(calc_project, (
        "from pathlib import Path\n\n"
        f"COUNT = Path({counter!r})\n\n"
        "def test_fails_once():\n"
        "    seen = int(COUNT.read_text()) if COUNT.exists() else 0\n"
        "    COUNT.write_text(str(seen + 1))\n"
        "    assert seen > 0\n"))
    record = records["test_fails_once"]
    assert record.verdict == "OBSERVED_UNSTABLE_CURRENT_RUN" and "passed when the full run was repeated" in record.probe
