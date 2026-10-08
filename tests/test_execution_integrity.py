"""Execution is evidence only with its own exit status, identity and limits; a disposable copy is not a sandbox.

Found by dogfooding (0.6.0): an auditing agent ran `python -m unittest discover -s tests 2>&1 | tail -5`, whose
status is tail's, not the runner's; `--run-check` kept only a status and a one-line summary; every project
execution inherited the caller's full environment (tokens, cloud keys, credentialed URLs); a timeout ended only
the direct child; and naming any discovered check in an audit authorized it, whatever it could change."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

from assertiva import cli, process
from assertiva.adapters.commands import classify_command
from assertiva.verification import VerificationKind
from assertiva.workspace import tree_fingerprint
from conftest import write

_PRINT_ENV = "import json, os; print(json.dumps(sorted(os.environ)))"


def _names(result) -> list[str]:
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_credentials_are_withheld_from_child_processes_and_named_not_valued(tmp_path):
    env = {**os.environ, "GITHUB_TOKEN": "ghp_x", "AWS_SECRET_ACCESS_KEY": "k", "DATABASE_URL": "postgres://u:hunter2@db/x",
           "MY_API_KEY": "k", "HARMLESS_SETTING": "1"}
    with process.run_scope():
        result = process.run_command([sys.executable, "-c", _PRINT_ENV], tmp_path, env=env, timeout_s=60)
        withheld = process.withheld_variables()
    names = _names(result)
    assert result.ok and "HARMLESS_SETTING" in names and "PATH" in names
    assert not {"GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "MY_API_KEY"} & set(names)
    assert {"GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "DATABASE_URL", "MY_API_KEY"} <= set(withheld)
    assert "hunter2" not in json.dumps(withheld)


def test_the_project_owner_can_pass_a_needed_variable_through(tmp_path):
    env = {**os.environ, "DATABASE_URL": "postgres://u:p@localhost/test"}
    with process.passthrough(["DATABASE_URL"]):
        result = process.run_command([sys.executable, "-c", _PRINT_ENV], tmp_path, env=env, timeout_s=60)
    assert "DATABASE_URL" in _names(result)


def test_success_is_the_commands_own_exit_status_not_its_output(tmp_path):
    result = process.run_command([sys.executable, "-c", "print('OK: 12 passed'); raise SystemExit(1)"], tmp_path, timeout_s=60)
    assert not result.ok and result.returncode == 1 and "12 passed" in result.stdout
    assert len(result.output_sha256) == 64


@pytest.mark.skipif(os.name == "nt", reason="POSIX signals")
def test_a_process_ended_by_a_signal_is_not_a_pass(tmp_path):
    result = process.run_command([sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"], tmp_path, timeout_s=60)
    assert not result.ok and result.signal == "SIGTERM" and "SIGTERM" in result.summary()


@pytest.mark.integration
def test_a_timeout_ends_the_whole_process_tree(tmp_path):
    marker = tmp_path / "grandchild-survived"
    child = f"import time; time.sleep(4); open({str(marker)!r}, 'w').write('x')"
    parent = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {child!r}]); time.sleep(60)"
    result = process.run_command([sys.executable, "-c", parent], tmp_path, timeout_s=1.5)
    assert result.timed_out and not result.ok
    time.sleep(5)
    assert not marker.exists()


@pytest.mark.parametrize("command", ["mvn -B deploy", "./gradlew publish", "mvn release:perform"])
def test_build_tool_publishing_goals_are_deploys(command):
    assert classify_command(command).kind is VerificationKind.DEPLOY


# --- audit --run-check ----------------------------------------------------------------

def _project(root: Path, steps: str) -> Path:
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_calc.py", "from calc import add\n\n\ndef test_add():\n    assert add(2, 2) == 4\n\n\n"
                                          "def test_add_negative():\n    assert add(-1, 1) == 0\n")
    write(root / "manage.py", "import pathlib, sys\npathlib.Path('migrated.marker').write_text('x')\nsys.exit(0)\n")
    write(root / ".github" / "workflows" / "ci.yml",
          "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n" + steps)
    return root


def _audit(root: Path, capsys, *args: str) -> dict:
    code = cli.main(["audit", str(root), "--python", sys.executable, "--output", "json", *args])
    out, err = capsys.readouterr()
    assert code == 0, err
    return json.loads(out)


def test_a_reproduced_test_check_carries_its_execution_record_and_parity(tmp_path, capsys):
    root = _project(tmp_path / "p", "      - run: python -m pytest -q tests\n")
    before = tree_fingerprint(root)
    report = _audit(root, capsys, "--run-check", "gha:.github/workflows/ci.yml:test:1")
    assert tree_fingerprint(root) == before
    [check] = report["declared_checks"]
    assert check["status"] == "PASS" and check["scope"].startswith("per-test outcomes")
    assert check["execution"]["via"] == "pytest-native" and check["execution"]["exit_code"] == 0
    parity = {p["dimension"]: p["status"] for p in check["parity"]}
    assert parity["revision"] == "LOCAL" and parity["result"] == "LOCAL" and parity["selection"] == "SAME"
    assert parity["environment"] in {"SAME", "DIFFERENT"}  # ubuntu-latest vs this machine
    # per-test outcomes of the reproduced CI command are the run's evidence (nothing else ran)
    [run] = report["states"]["current"]["runs"]
    assert run["invocations"] == 2 and run["outcomes"] == {"PASSED": 2}


def test_a_whole_command_reproduction_records_exit_status_and_output_digest(tmp_path, capsys):
    root = _project(tmp_path / "p", "      - run: python -m compileall -q calc.py\n")
    report = _audit(root, capsys, "--run-check", "gha:.github/workflows/ci.yml:test:1")
    [check] = report["declared_checks"]
    execution = check["execution"]
    assert check["status"] == "PASS" and execution["via"] == "command" and execution["exit_code"] == 0
    assert execution["signal"] is None and not execution["timed_out"] and len(execution["output_sha256"]) == 64
    assert check["environment"]["platform"] and check["scope"].startswith("whole command")


def test_a_pipeline_into_tail_is_never_reproduced_as_the_runner(tmp_path, capsys):
    root = _project(tmp_path / "p", "      - run: python -m unittest discover -s tests 2>&1 | tail -5\n")
    report = _audit(root, capsys, "--run-check", "gha:.github/workflows/ci.yml:test:1")
    [check] = report["declared_checks"]
    assert check["status"] == "NOT_RUN" and "compound shell step" in check["detail"]


def test_a_check_with_effects_outside_the_copy_needs_the_owners_authorization(tmp_path, capsys):
    root = _project(tmp_path / "p", "      - run: python manage.py migrate\n")
    check_id = "gha:.github/workflows/ci.yml:test:1"
    report = _audit(root, capsys, "--run-check", check_id)
    [check] = report["declared_checks"]
    assert check["kind"] == "MIGRATION" and check["status"] == "NOT_RUN" and check["authorization"] == "REQUIRED"
    assert ".assertiva.toml" in check["detail"]
    write(root / ".assertiva.toml", f'[execution]\nauthorize = ["{check_id}"]\n')
    before = tree_fingerprint(root)
    report = _audit(root, capsys, "--run-check", check_id)
    [check] = report["declared_checks"]
    assert check["status"] == "PASS" and check["authorization"] == "AUTHORIZED"
    assert tree_fingerprint(root) == before and not (root / "migrated.marker").exists()  # it ran in the copy


def test_withheld_credentials_are_a_reported_limitation(tmp_path, capsys, monkeypatch):
    root = _project(tmp_path / "p", "      - run: python -m pytest -q tests\n")
    monkeypatch.setenv("DEPLOY_TOKEN", "secret-value")
    report = _audit(root, capsys, "--execute")
    text = json.dumps(report)
    assert "DEPLOY_TOKEN" in " ".join(report["claim_boundary"]["limitations"]) and "secret-value" not in text


def test_the_report_shows_what_ran_and_its_equivalence_in_both_languages(tmp_path, capsys):
    from assertiva.report import render_html

    root = _project(tmp_path / "p", "      - run: python -m compileall -q calc.py\n")
    report = _audit(root, capsys, "--run-check", "gha:.github/workflows/ci.yml:test:1")
    english, portuguese = render_html(report), render_html(report, lang="pt-BR")
    assert "Reproduced in a disposable copy" in english and "Equivalence with the declared step" in english
    assert "Reproduzida em uma cópia descartável" in portuguese and "Equivalência com o passo declarado" in portuguese
    assert "which revision CI ran is UNKNOWN" in english


def test_one_failing_ci_check_is_one_finding_naming_its_failing_tests(tmp_path, capsys):
    """Found in CP4 review: the reproduced check's own run also raised NATIVE_TESTS_FAILING for the same failure."""
    root = _project(tmp_path / "p", "      - run: python -m pytest -q tests\n")
    write(root / "tests" / "test_calc.py", "from calc import add\n\n\ndef test_add():\n    assert add(2, 2) == 5\n")
    report = _audit(root, capsys, "--run-check", "gha:.github/workflows/ci.yml:test:1")
    codes = [f["code"] for f in report["findings"]]
    assert codes.count("DECLARED_CHECK_FAILED") == 1 and "NATIVE_TESTS_FAILING" not in codes
    finding = next(f for f in report["findings"] if f["code"] == "DECLARED_CHECK_FAILED")
    assert finding["evidence"]["failing_tests"] == ["tests/test_calc.py::test_add"]
