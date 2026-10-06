"""Native pytest evidence: the runner, not the AST, is authoritative for what runs."""

import pytest
import os
import sys

from assertiva.adapters.pytest_native import PytestNativeAdapter
from assertiva.candidate import StageStatus
from assertiva.models import Outcome
from assertiva.workspace import tree_fingerprint

from conftest import write

pytestmark = pytest.mark.integration

ADAPTER = PytestNativeAdapter(python=sys.executable)


def by_id(evidence):
    return {inv.invocation_id: inv for inv in evidence.invocations}


def test_native_collection_preserves_parameterized_invocation_ids(tmp_path):
    write(
        tmp_path / "tests" / "test_params.py",
        "import pytest\n\n"
        "@pytest.mark.parametrize('value', [0, 1, -1], ids=['zero', 'one', 'negative'])\n"
        "def test_abs(value):\n    assert abs(value) >= 0\n",
    )
    evidence = ADAPTER.collect(tmp_path)
    assert evidence.status is StageStatus.PASS
    invocations = by_id(evidence)
    assert set(invocations) == {
        "tests/test_params.py::test_abs[zero]",
        "tests/test_params.py::test_abs[one]",
        "tests/test_params.py::test_abs[negative]",
    }
    assert {inv.declaration_id for inv in invocations.values()} == {"tests/test_params.py::test_abs"}
    assert invocations["tests/test_params.py::test_abs[one]"].parameters_id == "one"


def test_inherited_test_materialization_from_native_collection(tmp_path):
    write(
        tmp_path / "tests" / "base_behaviors.py",
        "class CrudBehavior:\n"
        "    def test_create(self):\n"
        "        assert self.kind in {'customer', 'product'}\n",
    )
    write(
        tmp_path / "tests" / "test_entities.py",
        "from base_behaviors import CrudBehavior\n\n"
        "class TestCustomer(CrudBehavior):\n    kind = 'customer'\n\n"
        "class TestProduct(CrudBehavior):\n    kind = 'product'\n",
    )
    invocations = by_id(ADAPTER.collect(tmp_path))
    customer = invocations["tests/test_entities.py::TestCustomer::test_create"]
    product = invocations["tests/test_entities.py::TestProduct::test_create"]
    # Cross-module inheritance that the bounded static slice cannot see.
    assert customer.declaration_id == product.declaration_id == "tests/base_behaviors.py::CrudBehavior::test_create"
    assert customer.inherited and product.inherited


def test_collection_errors_are_failures_not_zero_tests(tmp_path):
    write(tmp_path / "tests" / "test_ok.py", "def test_ok():\n    assert 1 == 1\n")
    write(tmp_path / "tests" / "test_broken.py", "import does_not_exist_anywhere\n\ndef test_x():\n    assert True\n")
    evidence = ADAPTER.collect(tmp_path)
    assert evidence.status is StageStatus.FAIL
    assert [error.split("::")[0] for error in evidence.collection_errors] == ["tests/test_broken.py"]


def test_no_tests_collected_is_unknown_not_pass(tmp_path):
    write(tmp_path / "tests" / "test_empty.py", "X = 1\n")
    evidence = ADAPTER.collect(tmp_path)
    assert evidence.status is StageStatus.UNKNOWN
    assert evidence.invocations == []


def test_execution_distinguishes_skip_xfail_xpass_fail_and_error(tmp_path):
    write(
        tmp_path / "tests" / "test_outcomes.py",
        "import pytest\n\n"
        "def test_pass():\n    assert 1 == 1\n\n"
        "def test_fail():\n    assert 1 == 2\n\n"
        "@pytest.fixture\ndef broken():\n    raise RuntimeError('setup')\n\n"
        "def test_error(broken):\n    assert True\n\n"
        "@pytest.mark.skip(reason='not here')\ndef test_skip():\n    assert True\n\n"
        "@pytest.mark.xfail(reason='known')\ndef test_xfail():\n    assert 1 == 2\n\n"
        "@pytest.mark.xfail(reason='stale')\ndef test_xpass():\n    assert 1 == 1\n",
    )
    evidence = ADAPTER.run(tmp_path)
    outcomes = {inv.invocation_id.split("::")[-1]: inv.outcome for inv in evidence.invocations}
    assert outcomes == {
        "test_pass": Outcome.PASSED,
        "test_fail": Outcome.FAILED,
        "test_error": Outcome.ERROR,
        "test_skip": Outcome.SKIPPED,
        "test_xfail": Outcome.XFAILED,
        "test_xpass": Outcome.XPASSED,
    }
    assert evidence.status is StageStatus.FAIL


def test_green_run_is_pass_with_markers_preserved(tmp_path):
    write(
        tmp_path / "tests" / "test_marked.py",
        "import pytest\n\n"
        "@pytest.mark.slow\ndef test_slow():\n    assert 2 * 2 == 4\n\n"
        "def test_fast():\n    assert 2 + 2 == 4\n",
    )
    write(tmp_path / "pytest.ini", "[pytest]\nmarkers =\n    slow: slow tests\n")
    evidence = ADAPTER.run(tmp_path)
    assert evidence.status is StageStatus.PASS
    assert by_id(evidence)["tests/test_marked.py::test_slow"].markers == ("slow",)


def test_marker_filter_selection_is_recorded_as_deselected(tmp_path):
    write(
        tmp_path / "tests" / "test_marked.py",
        "import pytest\n\n"
        "@pytest.mark.slow\ndef test_slow():\n    assert True\n\n"
        "def test_fast():\n    assert True\n",
    )
    write(tmp_path / "pytest.ini", "[pytest]\nmarkers =\n    slow: slow tests\n")
    evidence = ADAPTER.collect(tmp_path, args=["-m", "not slow"])
    assert set(by_id(evidence)) == {"tests/test_marked.py::test_fast"}
    assert evidence.deselected == ["tests/test_marked.py::test_slow"]


def test_custom_collected_items_are_kept_with_declared_limitation(tmp_path):
    write(
        tmp_path / "conftest.py",
        "import pytest\n\n"
        "class CheckItem(pytest.Item):\n"
        "    def runtest(self):\n        pass\n\n"
        "class CheckFile(pytest.File):\n"
        "    def collect(self):\n        yield CheckItem.from_parent(self, name='rule')\n\n"
        "def pytest_collect_file(parent, file_path):\n"
        "    if file_path.suffix == '.check':\n"
        "        return CheckFile.from_parent(parent, path=file_path)\n",
    )
    write(tmp_path / "rules" / "pricing.check", "anything\n")
    evidence = ADAPTER.collect(tmp_path)
    item = by_id(evidence)["rules/pricing.check::rule"]
    assert item.custom
    assert any("custom" in limitation for limitation in evidence.limitations)


def test_adapter_never_writes_caches_into_the_directory_it_runs(tmp_path):
    write(tmp_path / "tests" / "test_ok.py", "def test_ok():\n    assert 1 == 1\n")
    before = tree_fingerprint(tmp_path)
    ADAPTER.run(tmp_path)
    assert tree_fingerprint(tmp_path) == before


def test_stale_bytecode_in_a_copied_tree_does_not_corrupt_provenance(tmp_path):
    """Found by dogfooding: copied __pycache__ made every test look inherited from elsewhere."""
    import subprocess

    from assertiva.workspace import snapshot

    original = tmp_path / "original"
    write(original / "tests" / "test_a.py", "def test_a():\n    assert 1 + 1 == 2\n")
    # A plain pytest run leaves pytest's assertion-rewrite bytecode cache in the tree.
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPYCACHEPREFIX", "PYTHONDONTWRITEBYTECODE"}}
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=original, capture_output=True, env=env)
    assert list(original.rglob("*-pytest-*.pyc"))
    copy = snapshot(original, tmp_path / "copy")
    [invocation] = ADAPTER.collect(copy).invocations
    assert invocation.declaration_id == "tests/test_a.py::test_a"
    assert not invocation.inherited
