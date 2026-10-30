"""TCC-A01: a CI step that runs the tests from a subfolder covers that subfolder's tests.

`defaults.run.working-directory` (workflow or job) and a step's `working-directory` move where the runner starts; the
scopes the command names are relative to it. Ignoring that raised a false high CI_TEST_EXECUTION_GAP."""

import pytest

from assertiva.pytest_audit import audit_pytest_project

from conftest import write

TEST = "import unittest\n\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(1 + 1, 2)\n"


def project(root, workflow):
    write(root / "tools" / "research" / "tests" / "test_model.py", TEST)
    write(root / "tools" / "research" / "model.py", "X = 1\n")
    write(root / ".github" / "workflows" / "ci.yml", workflow)
    return root


def gap(root):
    report = audit_pytest_project(root)
    return next((f for f in report.findings if f.code == "CI_TEST_EXECUTION_GAP"), None)


@pytest.mark.parametrize("workflow", [
    # workflow-level defaults
    "on: push\ndefaults:\n  run:\n    working-directory: tools/research\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - run: python -m unittest discover -s tests\n",
    # job-level defaults
    "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n        working-directory: ./tools/research\n"
    "    steps:\n      - run: python -m unittest discover -s tests\n",
    # step-level
    "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m unittest discover -s tests\n"
    "        working-directory: tools/research\n",
    # step-level, the whole subfolder by default discovery
    "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m pytest -q\n"
    "        working-directory: tools/research\n",
])
def test_tests_run_from_a_working_directory_are_observed(tmp_path, workflow):
    assert gap(project(tmp_path, workflow)) is None


def test_a_step_level_directory_overrides_the_defaults(tmp_path):
    workflow = ("on: push\ndefaults:\n  run:\n    working-directory: tools/research\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - run: python -m unittest discover -s tests\n        working-directory: docs\n")
    found = gap(project(tmp_path, workflow))
    assert found is not None and found.evidence["unobserved_test_files"] == ["tools/research/tests/test_model.py"]


def test_tests_outside_the_working_directory_stay_unobserved(tmp_path):
    # negative control: the CI really runs another folder's tests only
    root = project(tmp_path, "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    defaults:\n      run:\n"
                             "        working-directory: services/api\n    steps:\n      - run: python -m pytest -q\n")
    write(root / "services" / "api" / "tests" / "test_api.py", "def test_api():\n    assert 1 == 1\n")
    found = gap(root)
    assert found is not None and found.evidence["unobserved_test_files"] == ["tools/research/tests/test_model.py"]


def test_an_expression_valued_directory_is_not_claimed_as_a_gap(tmp_path):
    workflow = ("on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    strategy:\n      matrix:\n        dir: [tools/research]\n"
                "    steps:\n      - run: python -m pytest -q\n        working-directory: ${{ matrix.dir }}\n")
    assert gap(project(tmp_path, workflow)) is None
