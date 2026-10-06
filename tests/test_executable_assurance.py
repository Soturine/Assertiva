import json
from pathlib import Path

import pytest

from assertiva.pytest_audit import (
    audit_pytest_project,
    discover_pytest_composition,
    discover_pytest_definitions,
)


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discovers_pytest_functions_and_class_methods(tmp_path):
    write(
        tmp_path / "tests" / "test_sample.py",
        "def test_function():\n    assert 2 + 2 == 4\n\n"
        "class TestGroup:\n    def test_method(self):\n        assert 'a'.upper() == 'A'\n",
    )
    assert [item.node_id for item in discover_pytest_definitions(tmp_path)] == [
        "tests/test_sample.py::test_function",
        "tests/test_sample.py::TestGroup::test_method",
    ]


def test_discovers_same_file_inherited_materializations(tmp_path):
    write(
        tmp_path / "tests" / "test_shared.py",
        "class CrudBehavior:\n"
        "    def test_create(self):\n"
        "        assert 2 + 2 == 4\n\n"
        "class TestCustomer(CrudBehavior):\n"
        "    pass\n\n"
        "class TestProduct(CrudBehavior):\n"
        "    pass\n",
    )
    assert discover_pytest_definitions(tmp_path) == []
    relations = discover_pytest_composition(tmp_path)
    assert {item.materialization_id for item in relations} == {
        "tests/test_shared.py::TestCustomer::test_create",
        "tests/test_shared.py::TestProduct::test_create",
    }


def test_override_prevents_inherited_materialization_of_same_method(tmp_path):
    write(
        tmp_path / "tests" / "test_override.py",
        "class SharedBehavior:\n"
        "    def test_rule(self):\n"
        "        assert 1 == 1\n\n"
        "class TestConcrete(SharedBehavior):\n"
        "    def test_rule(self):\n"
        "        assert 2 == 2\n",
    )
    assert discover_pytest_composition(tmp_path) == []


def _ids(tmp_path, source):
    write(tmp_path / "tests" / "test_m.py", source)
    return [t.node_id.split("::", 1)[1] for t in discover_pytest_definitions(tmp_path)]


def test_testcase_named_test_is_collected(tmp_path):
    assert _ids(tmp_path, "import unittest\n\nclass TestUser(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(1, 1)\n") == ["TestUser::test_x"]


def test_testcase_is_collected_whatever_its_name(tmp_path):
    """Found by dogfooding: only `Test*` classes were inventoried, so unittest suites named `*Tests` vanished."""
    assert _ids(tmp_path, "import unittest\n\nclass UserPermissionsTests(unittest.TestCase):\n"
                          "    def test_x(self):\n        self.assertEqual(1, 1)\n"
                          "    def testLegacyName(self):\n        self.assertTrue(True)\n") == [
        "UserPermissionsTests::test_x", "UserPermissionsTests::testLegacyName"]  # unittest's prefix is `test`


@pytest.mark.parametrize("imports, base", [
    ("from unittest import TestCase", "TestCase"),
    ("from unittest import TestCase as TC", "TC"),
    ("import unittest as ut", "ut.TestCase"),
    ("from unittest import IsolatedAsyncioTestCase", "IsolatedAsyncioTestCase"),
])
def test_testcase_aliases_are_resolved(tmp_path, imports, base):
    assert _ids(tmp_path, f"{imports}\n\nclass AssetCrudCase({base}):\n    def test_x(self):\n        pass\n") == ["AssetCrudCase::test_x"]


def test_local_subclass_of_a_testcase_is_collected(tmp_path):
    source = ("from unittest import TestCase\n\nclass MyBase(TestCase):\n    def helper(self):\n        return 1\n\n"
              "class ConcreteBehavior(MyBase):\n    def test_x(self):\n        self.assertEqual(self.helper(), 1)\n")
    assert _ids(tmp_path, source) == ["ConcreteBehavior::test_x"]


def test_plain_class_with_test_methods_is_not_a_testcase(tmp_path):
    source = ("import unittest\n\nclass Helpers:\n    def test_x(self):\n        assert 1\n\n"
              "class Widget(dict):\n    def test_y(self):\n        assert 1\n")
    assert _ids(tmp_path, source) == []
    assert not audit_pytest_project(tmp_path).has_finding("TEST_CLASS_COLLECTION_UNKNOWN")


def test_testcase_inheritance_materializes_without_the_test_prefix(tmp_path):
    write(tmp_path / "tests" / "test_crud.py",
          "import unittest\n\nclass CrudContract(unittest.TestCase):\n    def test_create(self):\n        self.assertTrue(True)\n\n"
          "class CustomerCrud(CrudContract):\n    pass\n\n"
          "class ProductCrud(CrudContract):\n    def test_create(self):\n        self.assertEqual(1, 1)\n")
    assert [t.node_id.split("::", 1)[1] for t in discover_pytest_definitions(tmp_path)] == [
        "CrudContract::test_create", "ProductCrud::test_create"]
    assert [r.materialization_id.split("::", 1)[1] for r in discover_pytest_composition(tmp_path)] == ["CustomerCrud::test_create"]


@pytest.mark.parametrize("source", [
    "from tests.base import BaseCase\n\nclass PermissionsCase(BaseCase):\n    def test_x(self):\n        pass\n",
    "from django.test import TestCase\n\nclass PermissionsCase(TestCase):\n    def test_x(self):\n        pass\n",
    "class PermissionsCase(make_base()):\n    def test_x(self):\n        pass\n",
    "class PermissionsCase(metaclass=Registry):\n    def test_x(self):\n        pass\n",
])
def test_unresolvable_bases_stay_unknown_not_guessed(tmp_path, source):
    assert _ids(tmp_path, source) == []
    [finding] = [f for f in audit_pytest_project(tmp_path).findings if f.code == "TEST_CLASS_COLLECTION_UNKNOWN"]
    assert finding.evidence["classes"] == ["tests/test_m.py::PermissionsCase"]


def test_expected_exception_is_assertion_evidence(tmp_path):
    write(
        tmp_path / "tests" / "test_errors.py",
        "import pytest\n\n"
        "def test_invalid():\n"
        "    with pytest.raises(ValueError):\n"
        "        int('not-a-number')\n",
    )
    test = discover_pytest_definitions(tmp_path)[0]
    assert test.assertion_kinds == ("EXPECTED_ERROR_CONTRACT",)
    assert not test.smoke_like


def test_broad_exception_expectation_is_flagged(tmp_path):
    write(
        tmp_path / "tests" / "test_errors.py",
        "import pytest\n\n"
        "def test_invalid():\n"
        "    with pytest.raises(Exception):\n"
        "        int('not-a-number')\n",
    )
    assert audit_pytest_project(tmp_path).has_finding("BROAD_ERROR_EXPECTATION_SIGNAL")


def test_error_status_only_is_not_deep_negative_path_proof(tmp_path):
    write(
        tmp_path / "tests" / "test_api.py",
        "class R:\n    status_code = 422\n"
        "r = R()\n"
        "def test_invalid():\n    assert r.status_code == 422\n",
    )
    report = audit_pytest_project(tmp_path)
    assert report.has_finding("ERROR_STATUS_ONLY_SIGNAL")


def test_detects_tests_present_but_outside_ci_scope(tmp_path):
    write(tmp_path / "tests" / "unit" / "test_unit.py", "def test_unit():\n    assert 1 == 1\n")
    write(tmp_path / "tests" / "integration" / "test_db.py", "def test_db():\n    assert 2 == 2\n")
    write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "jobs:\n  test:\n    steps:\n      - run: pytest tests/unit -q\n",
    )
    assert audit_pytest_project(tmp_path).has_finding("CI_TEST_EXECUTION_GAP")


def test_bare_pytest_represents_observed_full_scope(tmp_path):
    write(tmp_path / "tests" / "unit" / "test_unit.py", "def test_unit():\n    assert 1 == 1\n")
    write(tmp_path / "tests" / "integration" / "test_db.py", "def test_db():\n    assert 2 == 2\n")
    write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "jobs:\n  test:\n    steps:\n      - run: pytest -q\n",
    )
    assert not audit_pytest_project(tmp_path).has_finding("CI_TEST_EXECUTION_GAP")


_UNITTEST_CASE = "import unittest\n\nclass TestX(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(1 + 1, 2)\n"


def test_unittest_in_ci_is_the_suite_in_ci_with_native_support_kept_apart(tmp_path):
    """Found by dogfooding: a CI running `python -X utf8 -m unittest discover -s tests` got CI_PYTEST_NOT_OBSERVED."""
    write(tmp_path / "tests" / "test_x.py", _UNITTEST_CASE)
    write(tmp_path / ".github" / "workflows" / "ci.yml",
          "jobs:\n  test:\n    steps:\n      - run: python -X utf8 -m unittest discover -s tests\n")
    report = audit_pytest_project(tmp_path)
    assert not report.has_finding("CI_PYTEST_NOT_OBSERVED")
    assert not report.has_finding("CI_TEST_EXECUTION_GAP")
    [finding] = [f for f in report.findings if f.code == "CI_RUNS_PYTHON_UNITTEST"]
    assert finding.evidence["ci_runner"] == "DECLARED"
    assert finding.evidence["native_unittest_execution"] == "UNSUPPORTED"


def test_unittest_assertions_are_oracles_not_missing_assertions(tmp_path):
    """Found by the same smoke: every `self.assert*` test read as NO_ASSERTION and raised WEAK_ORACLE_SIGNAL."""
    write(tmp_path / "tests" / "test_x.py",
          "import unittest\n\nclass TestX(unittest.TestCase):\n"
          "    def test_value(self):\n        self.assertEqual(add(1, 1), 2)\n"
          "    def test_exists(self):\n        self.assertIsNotNone(make())\n"
          "    def test_status(self):\n        self.assertEqual(client.get('/').status_code, 200)\n")
    kinds = {t.name: t.assertion_kinds for t in discover_pytest_definitions(tmp_path)}
    assert kinds == {"test_value": ("BEHAVIORAL_ASSERTION",), "test_exists": ("EXISTENCE_ONLY",), "test_status": ("HTTP_STATUS_ONLY",)}


def test_tests_outside_the_unittest_start_directory_are_a_ci_gap(tmp_path):
    write(tmp_path / "tests" / "test_x.py", _UNITTEST_CASE)
    write(tmp_path / "other" / "test_y.py", _UNITTEST_CASE)
    write(tmp_path / ".github" / "workflows" / "ci.yml", "jobs:\n  test:\n    steps:\n      - run: python -m unittest discover -s tests\n")
    report = audit_pytest_project(tmp_path)
    [gap] = [f for f in report.findings if f.code == "CI_TEST_EXECUTION_GAP"]
    assert gap.evidence["unobserved_test_files"] == ["other/test_y.py"]


def test_detects_smoke_dominant_suite(tmp_path):
    write(
        tmp_path / "tests" / "test_smoke.py",
        "class R:\n    status_code=200\n"
        "r=R()\n"
        "def test_a(): assert r.status_code == 200\n"
        "def test_b(): assert r.status_code == 200\n"
        "def test_c(): assert object() is not None\n"
        "def test_d(): pass\n",
    )
    report = audit_pytest_project(tmp_path)
    assert report.has_finding("SUITE_SMOKE_DOMINANT")
    assert report.smoke_ratio == 1.0


def test_high_line_coverage_does_not_hide_weak_oracles(tmp_path):
    write(
        tmp_path / "tests" / "test_api.py",
        "class R:\n    status_code=200\n"
        "r=R()\n"
        "def test_a(): assert r.status_code == 200\n"
        "def test_b(): assert r.status_code == 200\n"
        "def test_c(): assert r.status_code == 200\n"
        "def test_d(): assert r.status_code == 200\n",
    )
    cov = tmp_path / "coverage.json"
    cov.write_text(
        json.dumps({"totals": {"percent_covered": 96.0, "covered_branches": 10, "num_branches": 40}}),
        encoding="utf-8",
    )
    report = audit_pytest_project(tmp_path, cov)
    assert report.has_finding("HIGH_COVERAGE_WEAK_ORACLE")
    assert report.has_finding("LINE_BRANCH_COVERAGE_DIVERGENCE")
