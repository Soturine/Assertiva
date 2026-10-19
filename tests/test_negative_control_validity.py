"""A negative control is detected only by tests that were green before the behavior was broken.

Found by the 0.7.3 research (a public mutation workflow verifies the mutant against the unmutated code first): a test
that already failed, or failed for its environment, made every control that selected it look KILLED.
"""

from __future__ import annotations

from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.evidence import ControlOutcome, NegativeControl, run_negative_control
from assertiva.models import Outcome, RunEvidence
from assertiva.models import TestInvocation as Invocation

from conftest import write

CONTROL = NegativeControl("add-multiply", "calc.py", "return a + b", "return a * b", "add() returns the sum")


class FakeRunner:
    """Outcomes per test as a function of the code it sees: broken tests fail whatever the code is."""

    adapter_id = "fake"

    def __init__(self, always_failing=(), sensitive=()):
        self.always_failing, self.sensitive = set(always_failing), set(sensitive)

    def run(self, root: Path, args=None, coverage=False) -> RunEvidence:
        mutated = "a * b" in (Path(root) / "calc.py").read_text(encoding="utf-8")
        invocations = []
        for test in sorted(self.always_failing | self.sensitive):
            failed = test in self.always_failing or (mutated and test in self.sensitive)
            invocations.append(Invocation(test, test, test, outcome=Outcome.FAILED if failed else Outcome.PASSED))
        status = StageStatus.FAIL if any(i.outcome is Outcome.FAILED for i in invocations) else StageStatus.PASS
        return RunEvidence("fake", "execute", status, invocations=invocations)


def _project(tmp_path):
    write(tmp_path / "calc.py", "def add(a, b):\n    return a + b\n")
    return tmp_path


def test_a_test_that_fails_without_the_control_does_not_detect_it(tmp_path):
    result = run_negative_control(_project(tmp_path), CONTROL, [FakeRunner(always_failing=["t_broken"])])
    assert result.outcome is not ControlOutcome.KILLED  # 0.7.2: KILLED, "detected by t_broken"
    assert result.outcome is ControlOutcome.INVALID and "before the control" in result.detail


def test_a_test_green_before_and_red_after_detects_the_control(tmp_path):
    result = run_negative_control(_project(tmp_path), CONTROL, [FakeRunner(always_failing=["t_broken"], sensitive=["t_sum"])])
    assert result.outcome is ControlOutcome.KILLED and "t_sum" in result.detail and "t_broken" not in result.detail


def test_green_tests_that_stay_green_let_the_control_survive(tmp_path):
    result = run_negative_control(_project(tmp_path), NegativeControl("c", "calc.py", "return a + b", "return b + a", "n/a"),
                                  [FakeRunner(sensitive=["t_sum"])])
    assert result.outcome is ControlOutcome.SURVIVED
