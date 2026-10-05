import json
from pathlib import Path

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
