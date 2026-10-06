"""Declared lifecycle checks: discovered is not authorized; authorized is not executed blindly."""

import os
import sys

import pytest

from assertiva.candidate import QualificationCheck, StageStatus
from assertiva.improve import discard_session, qualify_candidate, start_improve
from assertiva.verification import discover_surface

from conftest import write

pytestmark = pytest.mark.integration


def workflow(root, steps):
    body = ""
    for step in steps:
        if isinstance(step, str):
            step = {"run": step}
        body += f"      - run: {step['run']}\n"
        if step.get("continue-on-error"):
            body += "        continue-on-error: true\n"
    matrix = "    strategy:\n      matrix:\n        os: [ubuntu-latest, windows-latest]\n" if any(isinstance(s, dict) and s.get("matrix") for s in steps) else ""
    write(root / ".github" / "workflows" / "ci.yml", f"on: [push]\njobs:\n  check:\n{matrix}    steps:\n{body}")


def check_id(root, command):
    return next(c.check_id for c in discover_surface(root).checks if c.command == command)


def pipeline(session, **kwargs):
    q = qualify_candidate(session, **kwargs).qualification
    return next(s for s in q.checks if s.check is QualificationCheck.PIPELINE_EQUIVALENT), q


@pytest.fixture
def project(calc_project, tmp_path):
    marker = tmp_path / "side-effect-marker"
    # A custom script with an effect *outside* the project: it must never run unless authorized.
    write(calc_project / "scripts" / "reset_env.py", f"from pathlib import Path\nPath(r'{marker}').write_text('ran')\n")
    write(calc_project / "manage.py", "import sys\nprint('migrating')\nsys.exit(1)\n")
    return calc_project, marker


def start(root):
    return start_improve(root, python=sys.executable)


def test_recognized_safe_check_is_reproduced(calc_project):
    workflow(calc_project, ["pytest -q", "python -m compileall -q ."])
    session = start(calc_project)
    try:
        result, _ = pipeline(session)
    finally:
        discard_session(session)
    assert result.status is StageStatus.PASS
    assert "reproduced 2/2" in result.summary


def test_failing_safe_check_fails_the_stage(calc_project):
    workflow(calc_project, ["pytest -q", "python -m compileall -q ."])
    session = start(calc_project)
    try:
        write(session.workspace / "broken_syntax.py", "def nope(:\n")
        result, q = pipeline(session)
    finally:
        discard_session(session)
    assert result.status is StageStatus.FAIL
    assert not q.ready_for_review


def test_unknown_command_is_preserved_but_never_executed(project):
    root, marker = project
    workflow(root, ["pytest -q", "python scripts/reset_env.py"])
    session = start(root)
    try:
        result, _ = pipeline(session)
    finally:
        discard_session(session)
    assert not marker.exists()
    assert result.status is StageStatus.UNKNOWN
    assert any("python scripts/reset_env.py" in item and "not authorized" in item for item in result.limitations)


def test_explicitly_authorized_custom_check_is_executed(project):
    root, marker = project
    workflow(root, ["pytest -q", "python scripts/reset_env.py"])
    session = start(root)
    try:
        result, _ = pipeline(session, authorized_checks={check_id(root, "python scripts/reset_env.py")})
    finally:
        discard_session(session)
    assert marker.read_text() == "ran"
    assert result.status is StageStatus.PASS


def test_failing_authorized_migration_blocks_the_claim(project):
    root, _ = project
    workflow(root, ["pytest -q", "python manage.py migrate"])
    session = start(root)
    try:
        unauthorized, _ = pipeline(session)
        authorized, q = pipeline(session, authorized_checks={check_id(root, "python manage.py migrate")})
    finally:
        discard_session(session)
    assert unauthorized.status is StageStatus.UNKNOWN
    assert any("MIGRATION" in item and "not authorized" in item for item in unauthorized.limitations)
    assert authorized.status is StageStatus.FAIL
    assert not q.ready_for_review


def test_allowed_failure_stays_allowed(calc_project):
    workflow(calc_project, ["pytest -q", {"run": "python -m compileall -q .", "continue-on-error": True}])
    session = start(calc_project)
    try:
        write(session.workspace / "broken_syntax.py", "def nope(:\n")
        result, _ = pipeline(session)
    finally:
        discard_session(session)
    assert result.status is StageStatus.PASS  # CI would be green too
    assert any("allowed to fail" in item for item in result.limitations)


def test_matrix_reproduced_in_one_environment_is_partial(calc_project):
    workflow(calc_project, [{"run": "pytest -q", "matrix": True}])
    session = start(calc_project)
    try:
        result, _ = pipeline(session)
    finally:
        discard_session(session)
    assert result.status is StageStatus.UNKNOWN
    assert any("matrix" in item for item in result.limitations)


def test_deploy_is_never_executed_even_when_authorized(calc_project, tmp_path, monkeypatch):
    from assertiva.verification import VerificationKind

    # A fake `twine` on PATH: if Assertiva ever executed the publish step, the marker appears.
    marker, bin_dir = tmp_path / "published-marker", tmp_path / "fake-bin"
    write(bin_dir / "twine_impl.py", f"from pathlib import Path\nPath(r'{marker}').write_text('published')\n")
    write(bin_dir / "twine.cmd", f'@"{sys.executable}" "%~dp0twine_impl.py" %*\n')
    write(bin_dir / "twine", f'#!/bin/sh\nexec "{sys.executable}" "$(dirname "$0")/twine_impl.py" "$@"\n')
    (bin_dir / "twine").chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    workflow(calc_project, ["pytest -q", "twine upload dist/x.whl"])
    publish = next(c for c in discover_surface(calc_project).checks if c.command == "twine upload dist/x.whl")
    assert publish.kind is VerificationKind.DEPLOY
    session = start(calc_project)
    try:
        result, _ = pipeline(session, authorized_checks={publish.check_id})
    finally:
        discard_session(session)
    assert not marker.exists()
    assert result.status is StageStatus.UNKNOWN
    assert any("never executed" in item for item in result.limitations)


def test_compound_shell_step_is_not_reproduced(calc_project):
    workflow(calc_project, ["pytest -q", "python -m compileall -q . && echo done"])
    session = start(calc_project)
    try:
        result, _ = pipeline(session)
    finally:
        discard_session(session)
    assert result.status is StageStatus.UNKNOWN
    assert any("compound" in item for item in result.limitations)


def test_cli_run_check_authorizes_a_single_discovered_check(project, capsys):
    import json

    from assertiva import cli

    root, marker = project
    workflow(root, ["pytest -q", "python scripts/reset_env.py"])
    target = check_id(root, "python scripts/reset_env.py")
    cli.main(["improve", str(root), "--python", sys.executable, "--output", "json"])
    capsys.readouterr()
    cli.main(["improve", str(root), "--python", sys.executable, "--run-check", target, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    cli.main(["improve", str(root), "--discard"])
    stage = next(c for s in report["candidate_qualification"]["stages"] for c in s["checks"] if c["check"] == "PIPELINE_EQUIVALENT")
    assert marker.exists() and stage["status"] == "PASS"
