import json
from pathlib import Path

from assertiva.pytest_audit import audit_pytest_project, discover_pytest_definitions


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discovers_pytest_functions_and_class_methods(tmp_path):
    write(tmp_path/"tests"/"test_sample.py", "def test_function():\n    assert 2 + 2 == 4\n\nclass TestGroup:\n    def test_method(self):\n        assert 'a'.upper() == 'A'\n")
    assert [x.node_id for x in discover_pytest_definitions(tmp_path)] == ["tests/test_sample.py::test_function","tests/test_sample.py::TestGroup::test_method"]


def test_detects_tests_present_but_outside_ci_scope(tmp_path):
    write(tmp_path/"tests"/"unit"/"test_unit.py", "def test_unit():\n    assert 1 == 1\n")
    write(tmp_path/"tests"/"integration"/"test_db.py", "def test_db():\n    assert 2 == 2\n")
    write(tmp_path/".github"/"workflows"/"ci.yml", "jobs:\n  test:\n    steps:\n      - run: pytest tests/unit -q\n")
    report = audit_pytest_project(tmp_path)
    assert report.has_finding("CI_TEST_EXECUTION_GAP")


def test_bare_pytest_represents_observed_full_scope(tmp_path):
    write(tmp_path/"tests"/"unit"/"test_unit.py", "def test_unit():\n    assert 1 == 1\n")
    write(tmp_path/"tests"/"integration"/"test_db.py", "def test_db():\n    assert 2 == 2\n")
    write(tmp_path/".github"/"workflows"/"ci.yml", "jobs:\n  test:\n    steps:\n      - run: pytest -q\n")
    assert not audit_pytest_project(tmp_path).has_finding("CI_TEST_EXECUTION_GAP")


def test_detects_smoke_dominant_suite(tmp_path):
    write(tmp_path/"tests"/"test_smoke.py", "class R:\n    status_code=200\nr=R()\ndef test_a(): assert r.status_code == 200\ndef test_b(): assert r.status_code == 200\ndef test_c(): assert object() is not None\ndef test_d(): pass\n")
    report = audit_pytest_project(tmp_path)
    assert report.has_finding("SUITE_SMOKE_DOMINANT")
    assert report.smoke_ratio == 1.0


def test_high_line_coverage_does_not_hide_weak_oracles(tmp_path):
    write(tmp_path/"tests"/"test_api.py", "class R:\n    status_code=200\nr=R()\ndef test_a(): assert r.status_code == 200\ndef test_b(): assert r.status_code == 200\ndef test_c(): assert r.status_code == 200\ndef test_d(): assert r.status_code == 200\n")
    cov = tmp_path/"coverage.json"
    cov.write_text(json.dumps({"totals":{"percent_covered":96.0,"covered_branches":10,"num_branches":40}}), encoding="utf-8")
    report = audit_pytest_project(tmp_path, cov)
    assert report.has_finding("HIGH_COVERAGE_WEAK_ORACLE")
    assert report.has_finding("LINE_BRANCH_COVERAGE_DIVERGENCE")


def test_missing_ci_is_unknown_evidence_not_execution_gap(tmp_path):
    write(tmp_path/"tests"/"test_core.py", "def test_core():\n    assert 9 == 9\n")
    report = audit_pytest_project(tmp_path)
    assert report.has_finding("CI_PYTEST_NOT_OBSERVED")
    assert not report.has_finding("CI_TEST_EXECUTION_GAP")
