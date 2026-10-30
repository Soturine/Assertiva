"""AX-E02 / AG-08 / AG-09: a green run says which copy of the code it exercised, where its temp root was, and which
site directories it borrowed.

The stale copy stands in for an old non-editable install: a directory on the interpreter's path that provides the
project's package with outdated behavior. With a src/ layout and no import path configured, pytest imports that copy,
so a mutant in src/ survives while the suite is green."""

import json
import sys

import pytest

from assertiva import cli

from conftest import write

pytestmark = pytest.mark.integration


def run(capsys, *args):
    code = cli.main([*args, "--python", sys.executable, "--output", "json"])
    return code, json.loads(capsys.readouterr().out)


def src_project(root, configured: bool):
    write(root / "src" / "shop" / "__init__.py", "def fee(amount):\n    return amount * 3  # mutant: the real rate is 2\n")
    write(root / "tests" / "test_fee.py", "from shop import fee\n\ndef test_fee():\n    assert fee(10) == 20\n")
    write(root / "pytest.ini", "[pytest]\n" + ("pythonpath = src\n" if configured else ""))
    return root


@pytest.fixture
def stale_install(tmp_path, monkeypatch):
    stale = tmp_path / "stale-site"
    write(stale / "shop" / "__init__.py", "def fee(amount):\n    return amount * 2\n")
    monkeypatch.setenv("PYTHONPATH", str(stale))
    return stale


def native(report):
    return next(r for r in report["states"]["current"]["runs"] if r["adapter"] == "pytest-native")


def test_a_green_run_against_a_stale_installed_copy_is_flagged(tmp_path, capsys, assertiva_home, stale_install):
    code, report = run(capsys, "audit", str(src_project(tmp_path / "p", configured=False)), "--execute")
    run_ = native(report)
    assert run_["status"] == "PASS"  # the mutant survives: the tests never ran src/
    identity = run_["source_identity"]
    assert identity["status"] == "MISMATCH" and identity["from_outside_the_copy"] == ["shop"]
    found = next(f for f in report["findings"] if f["code"] == "SOURCE_IDENTITY_MISMATCH")
    assert found["severity"] == "high" and found["evidence"]["modules"] == ["shop"]


def test_the_same_tests_on_the_source_tree_kill_the_mutant_and_say_so(tmp_path, capsys, assertiva_home, stale_install):
    code, report = run(capsys, "audit", str(src_project(tmp_path / "p", configured=True)), "--execute")
    run_ = native(report)
    assert run_["status"] == "FAIL"  # src/ is exercised: the mutant is caught
    assert run_["source_identity"]["status"] == "SOURCE_TREE"
    assert not any(f["code"] == "SOURCE_IDENTITY_MISMATCH" for f in report["findings"])


def test_the_temp_root_and_interpreter_are_recorded(tmp_path, capsys, assertiva_home):
    code, report = run(capsys, "audit", str(src_project(tmp_path / "p", configured=True)), "--execute")
    meta = native(report)
    assert meta["temp_root"]["writable"] is True and meta["temp_root"]["path"]
    assert meta["interpreter"]["python"] and "borrowed_site_dirs" in meta["interpreter"]


def test_an_unwritable_temp_root_is_named_as_the_environment():
    # AG-08: interpreting what the plugin observed. An end-to-end run cannot force it safely: tempfile falls back to
    # another writable folder when TEMP is unusable, and changing a real folder's ACL is out of bounds for a test.
    from assertiva.adapters.pytest_native import PytestNativeAdapter
    from assertiva.candidate import StageStatus
    from assertiva.models import RunEvidence

    run_ = RunEvidence(adapter_id="pytest-native", mode="execute", status=StageStatus.UNKNOWN)
    PytestNativeAdapter()._session_facts(run_, {"imported": {}, "tempdir": "C:/Users/u/AppData/Local/Temp",
                                               "tempdir_writable": False, "borrowed_site_dirs": ["D:/other-venv/Lib/site-packages"]})
    assert run_.metadata["temp_root"] == {"path": "C:/Users/u/AppData/Local/Temp", "writable": False}
    assert any("temporary directory" in limitation and "not for the product" in limitation for limitation in run_.limitations)
    assert any("D:/other-venv/Lib/site-packages" in limitation for limitation in run_.limitations)  # AG-09
    assert run_.metadata["source_identity"]["status"] == "UNKNOWN"
