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


# --- AXF-VN-03: the identity of the code a unittest run imported, observed inside the test process ------------------

_CALC_TEST = "import unittest\nfrom calc import add\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n"


def _calc(root: Path, test: str = _CALC_TEST) -> Path:
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_calc.py", test)
    write(root / ".github" / "workflows" / "ci.yml",
          "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m unittest discover -s tests -t .\n")
    return root


def test_a_clean_unittest_run_records_where_the_code_came_from(tmp_path):
    root = _calc(tmp_path / "with space")  # a path with a space
    run = ADAPTER.run(root)
    assert run.status is StageStatus.PASS
    identity = run.metadata["source_identity"]
    assert identity["status"] == "SOURCE_TREE" and identity["loaded"] >= 1 and identity["unexpected"] == 0
    assert identity["basis"].startswith("OBSERVED")
    assert Path(run.metadata["interpreter"]["python"]).name.lower().startswith("python")
    assert run.metadata["temp_root"]["writable"] is True


def test_a_shadowing_copy_of_the_project_is_a_mismatch(tmp_path):
    """Contaminated on purpose: the test puts another tree first on sys.path, as an installed copy would."""
    shadow = tmp_path / "elsewhere"
    write(shadow / "calc.py", "def add(a, b):\n    return a + b\n")
    contaminated = ("import sys\nsys.path.insert(0, " + repr(str(shadow)) + ")\nsys.modules.pop('calc', None)\n" + _CALC_TEST)
    run = ADAPTER.run(_calc(tmp_path / "p", contaminated))
    identity = run.metadata["source_identity"]
    assert identity["status"] == "MISMATCH" and identity["from_outside_the_copy"] == ["calc"]
    assert any("from outside the tested copy" in lim for lim in run.limitations)


def test_a_process_that_dies_before_its_end_has_no_verified_identity(tmp_path):
    dies = _CALC_TEST + "\n    def test_zz_exit(self):\n        import os\n        os._exit(0)\n"
    run = ADAPTER.run(_calc(tmp_path / "p", dies))
    assert run.metadata["source_identity"]["status"] == "UNKNOWN"
    assert run.metadata["source_identity"]["basis"].startswith("UNKNOWN")


def test_a_namespace_package_is_not_claimed_as_verified(tmp_path):
    """No __init__.py: the observer cannot tell the project's namespace from any other, so nothing is verified."""
    root = tmp_path / "p"
    write(root / "ns" / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_calc.py", _CALC_TEST.replace("from calc import", "from ns.calc import"))
    run = ADAPTER.run(root, args=["discover", "-s", "tests", "-t", "."])
    assert run.status is StageStatus.PASS
    assert run.metadata["source_identity"]["status"] == "UNKNOWN"  # loaded 0 project modules it could recognize


def test_the_json_report_carries_the_unittest_identity(tmp_path, capsys):
    root = _calc(tmp_path / "p")
    cli.main(["audit", str(root), "--execute", "--python", sys.executable, "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    runs = payload["states"]["current"]["runs"]
    unittest_run = next(r for r in runs if r["adapter"] == "unittest")
    assert unittest_run["source_identity"]["status"] == "SOURCE_TREE"
    assert unittest_run["interpreter"]["python"] and unittest_run["temp_root"]["path"]


# --- AXF-VN-05: a stdlib-only TestCase project without CI or configuration -------------------------------------------

def _stdlib_project(root: Path, *, tests_package: bool = False) -> Path:
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    if tests_package:
        write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_calc.py", "import unittest as ut\nfrom calc import add\n\nclass Base(ut.TestCase):\n"
                                            "    pass\n\nclass T(Base):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")
    return root


def test_a_stdlib_testcase_project_without_declarations_runs_under_unittest(tmp_path):
    from assertiva.adapters.python_discovery import python_runners

    for package in (False, True):
        root = _stdlib_project(tmp_path / f"p{package}", tests_package=package)
        assert python_runners(root) == {"unittest"}
        assert [a.adapter_id for a in runner_adapters(root, sys.executable)] == ["unittest"]
        run = UnittestAdapter(python=sys.executable).run(root)
        assert run.status is StageStatus.PASS and len(run.invocations) == 1, run.limitations
        assert run.metadata["arguments_from"].startswith("INFERRED (no declared runner)")


def test_controls_anything_that_points_to_pytest_keeps_pytest(tmp_path):
    from assertiva.adapters.python_discovery import python_runners

    cases = {
        "imports_pytest": lambda r: write(r / "tests" / "test_more.py", "import pytest\n\ndef test_x():\n    assert True\n"),
        "plain_function": lambda r: write(r / "tests" / "test_more.py", "def test_x():\n    assert True\n"),
        "conftest": lambda r: write(r / "tests" / "sub" / "conftest.py", ""),
        "declared_dependency": lambda r: write(r / "pyproject.toml", '[project]\nname = "x"\nversion = "0"\n'
                                                                    '[project.optional-dependencies]\ntest = ["pytest>=8"]\n'),
        "requirements": lambda r: write(r / "requirements-dev.txt", "pytest==9.0\n"),
        "no_testcase": lambda r: write(r / "tests" / "test_calc.py", "from calc import add\nX = add(1, 2)\n"),
    }
    for name, change in cases.items():
        root = _stdlib_project(tmp_path / name)
        change(root)
        assert python_runners(root) == {"pytest"}, name
    django = _stdlib_project(tmp_path / "django")
    write(django / "manage.py", "import django\n")
    assert python_runners(django) == {"django"}
