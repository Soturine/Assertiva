"""AG-03: when most failures share one cause, the failing-tests finding's next step names it (every test stays listed)."""

from assertiva.audit import _native_findings
from assertiva.candidate import StageStatus
from assertiva.evidence import StateEvidence
from assertiva.models import Outcome, RunEvidence
from assertiva.models import TestInvocation as Invocation

ACL = ("C:/venv/Lib/site-packages/_pytest/pathlib.py:175: PermissionError\n"
       "E PermissionError: [WinError 5] Access is denied: 'C:/Users/u/AppData/Local/Temp/pytest-of-u'")


def state(messages):
    run = RunEvidence(adapter_id="pytest", mode="execute", status=StageStatus.FAIL)
    for index, message in enumerate(messages):
        run.invocations.append(Invocation(invocation_id=f"tests/test_x.py::test_{index}", declaration_id=f"d{index}", materialization_id=f"m{index}",
                                          outcome=Outcome.ERROR if message else Outcome.PASSED, message=message))
    current = StateEvidence(label="current", observed_in="copy")
    current.runs.append(run)
    return current


def failing(findings):
    return next(f for f in findings if f.code == "NATIVE_TESTS_FAILING")


def test_ten_failures_from_one_injected_environment_error_name_the_single_cause():
    found = failing(_native_findings(state([ACL] * 10 + [None] * 5), 15))
    assert found.recommendation.startswith("10 of 10 failing invocations share one cause: PermissionError")
    cause = found.evidence["dominant_cause"]
    assert cause["count"] == 10 and cause["origin"] == "INFRASTRUCTURE"
    assert found.evidence["count"] == 10 and len(found.evidence["tests"]) == 10  # no test is hidden behind the cluster


def test_unrelated_failures_keep_the_plain_summary():
    product = ["shop/a.py:{}: TypeError\nE TypeError: x".format(i) for i in range(4)]
    found = failing(_native_findings(state(product), 4))
    assert found.recommendation is None and "dominant_cause" not in found.evidence
