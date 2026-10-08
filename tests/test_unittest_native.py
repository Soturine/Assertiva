"""Native unittest evidence: the project's own unittest run, read test by test, never inferred from an exit code.

Found by dogfooding: a project whose CI runs `python -m unittest discover -s tests` was executed only through
pytest, so equivalence with CI stayed UNKNOWN and the auditing agent ran unittest by hand (through `| tail`)."""

import json
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters import runner_adapters
from assertiva.adapters.unittest_native import UnittestAdapter, normalize
from assertiva.candidate import StageStatus
from assertiva.models import Outcome
from assertiva.workspace import tree_fingerprint
from conftest import write

pytestmark = pytest.mark.integration

ADAPTER = UnittestAdapter(python=sys.executable)

_SUITE = '''import asyncio
import unittest

from shop import price


class PriceContract(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(price(2), 4)


class PriceTests(PriceContract):
    def test_fails(self):
        self.assertEqual(price(1), 3)

    def test_errors(self):
        raise RuntimeError("boom")

    @unittest.skip("not today")
    def test_skipped(self):
        pass

    @unittest.skipIf(True, "condition")
    def test_skipped_if(self):
        pass

    @unittest.expectedFailure
    def test_known_bug(self):
        self.assertEqual(price(0), 1)

    def test_cases(self):
        for value, expected in [(1, 2), (2, 5)]:
            with self.subTest(value=value):
                self.assertEqual(price(value), expected)


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_awaited(self):
        await asyncio.sleep(0)
        self.assertEqual(price(3), 6)


class BrokenSetup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raise RuntimeError("no database")

    def test_never_runs(self):
        pass


def test_plain_function_unittest_never_runs():
    assert False
'''


def project(root: Path, ci: str | None = "python -m unittest discover -s tests") -> Path:
    write(root / "shop.py", "def price(n):\n    return n * 2\n")
    write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_shop.py", _SUITE)
    write(root / "tests" / "test_broken_import.py", "import missing_module_xyz\n")
    if ci:
        write(root / ".github" / "workflows" / "ci.yml",
              f"on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: {ci}\n")
    return root


def test_unittest_outcomes_are_read_per_test(tmp_path):
    root = project(tmp_path / "p")
    run = ADAPTER.run(root)
    assert run.metadata["arguments_from"] == "python -m unittest discover -s tests"
    outcomes = {inv.invocation_id.split("::", 1)[1]: inv.outcome for inv in run.invocations if not inv.custom}
    assert outcomes == {
        "PriceContract::test_positive": Outcome.PASSED,
        "PriceTests::test_positive": Outcome.PASSED,
        "PriceTests::test_fails": Outcome.FAILED,
        "PriceTests::test_errors": Outcome.ERROR,
        "PriceTests::test_skipped": Outcome.SKIPPED,
        "PriceTests::test_skipped_if": Outcome.SKIPPED,
        "PriceTests::test_known_bug": Outcome.XFAILED,
        "PriceTests::test_cases[(value=1)]": Outcome.PASSED,
        "PriceTests::test_cases[(value=2)]": Outcome.FAILED,
        "AsyncTests::test_awaited": Outcome.PASSED,
    }
    assert run.status is StageStatus.FAIL and run.exit_code == 1


def test_inheritance_subtests_fixtures_and_load_errors_keep_their_identity(tmp_path):
    run = ADAPTER.run(project(tmp_path / "p"))
    by_id = {inv.invocation_id: inv for inv in run.invocations}
    inherited = by_id["tests/test_shop.py::PriceTests::test_positive"]
    assert inherited.inherited and inherited.declaration_id == "tests/test_shop.py::PriceContract::test_positive"
    case = by_id["tests/test_shop.py::PriceTests::test_cases[(value=2)]"]
    assert case.parameters_id == "(value=2)" and case.materialization_id == "tests/test_shop.py::PriceTests::test_cases"
    [fixture] = [inv for inv in run.invocations if inv.custom]
    assert "setUpClass" in fixture.invocation_id and fixture.outcome is Outcome.ERROR and "no database" in fixture.message
    assert run.collection_errors == ["test_broken_import"]  # as unittest names it, relative to `-s tests`
    assert run.metadata["error_sources"] == {"test_broken_import": "tests/test_broken_import.py"}
    assert "missing_module_xyz" in run.metadata["load_errors"]["test_broken_import"]
    assert not any("plain_function" in inv.invocation_id for inv in run.invocations)  # unittest never runs it


def test_an_unexpected_success_fails_the_run(tmp_path):
    write(tmp_path / "test_x.py", "import unittest\n\nclass T(unittest.TestCase):\n    @unittest.expectedFailure\n"
                                  "    def test_fixed(self):\n        self.assertTrue(True)\n")
    run = ADAPTER.run(tmp_path)
    assert [inv.outcome for inv in run.invocations] == [Outcome.XPASSED]
    assert run.status is StageStatus.FAIL and any("unexpected success" in lim for lim in run.limitations)


def test_no_test_run_is_unknown_never_pass(tmp_path):
    write(tmp_path / "test_x.py", "X = 1\n")
    run = ADAPTER.run(tmp_path)
    assert run.status is StageStatus.UNKNOWN and not run.invocations


def test_a_runner_that_never_starts_is_blocked_not_simulated():
    run = normalize([], "unittest", 0)
    assert run.status is StageStatus.UNKNOWN and not run.invocations  # exit code 0 alone is never a pass


def test_ci_unittest_selects_the_unittest_adapter_not_pytest(tmp_path):
    root = project(tmp_path / "p")
    assert [a.adapter_id for a in runner_adapters(root, sys.executable)] == ["unittest"]
    no_ci = project(tmp_path / "q", ci=None)
    assert [a.adapter_id for a in runner_adapters(no_ci, sys.executable)] == ["pytest-native"]  # undeclared: pytest runs TestCases


def test_audit_executes_unittest_natively_and_reports_tests_unittest_never_runs(tmp_path, capsys):
    root = project(tmp_path / "p")
    before = tree_fingerprint(root)
    code = cli.main(["audit", str(root), "--execute", "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and tree_fingerprint(root) == before
    [run] = report["states"]["current"]["runs"]
    assert run["adapter"] == "unittest" and run["outcomes"]["FAILED"] == 2
    finding = next(f for f in report["findings"] if f["code"] == "CI_RUNS_PYTHON_UNITTEST")
    assert finding["evidence"]["not_collected_by_unittest"] == ["tests/test_shop.py::test_plain_function_unittest_never_runs"]
