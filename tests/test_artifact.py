"""Built/installed artifact qualification: a green source tree is not a working package."""

import re
import sys
from pathlib import Path

from assertiva.adapters.python_package import PythonPackageAdapter
from assertiva.candidate import DeltaState, QualificationStage, StageStatus
from assertiva.improve import discard_session, qualify_candidate, start_improve

from conftest import write

ADAPTER = PythonPackageAdapter(python=sys.executable)
PYPROJECT = """[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "greet"
version = "0.1.0"
{extra_project}
[tool.setuptools]
packages = {packages}
{package_data}
[tool.pytest.ini_options]
testpaths = ["tests"]
"""
WITH_DATA = '[tool.setuptools.package-data]\ngreet = ["templates/*.txt"]\n'


def make_package(root, *, package_data=True, packages='["greet"]', extra_project="", subpackage=False):
    write(root / "pyproject.toml", PYPROJECT.format(packages=packages, package_data=WITH_DATA if package_data else "", extra_project=extra_project))
    init = "from importlib import resources\n"
    if subpackage:
        init += "from greet.text import shout\n"
        write(root / "greet" / "text" / "__init__.py", "def shout(s):\n    return s.upper()\n")
    init += "\ndef hello():\n    return resources.files('greet').joinpath('templates/hello.txt').read_text().strip()\n"
    write(root / "greet" / "__init__.py", init)
    write(root / "greet" / "templates" / "hello.txt", "hi\n")
    write(root / "tests" / "test_greet.py", "from greet import hello\n\ndef test_hello():\n    assert hello() == 'hi'\n")
    return root


def check(evidence, name):
    return next(c for c in evidence.checks if c.name == name)


def test_complete_package_is_qualified_from_the_installed_artifact(tmp_path):
    evidence = ADAPTER.qualify(make_package(tmp_path / "ok"))
    assert evidence.status is StageStatus.PASS, evidence
    assert evidence.artifact.endswith(".whl") and re.fullmatch(r"[0-9a-f]{64}", evidence.sha256)
    assert [c.name for c in evidence.checks] == ["build", "install", "import", "tests"]
    assert all(c.status is StageStatus.PASS for c in evidence.checks)
    assert "site-packages" in check(evidence, "import").detail
    assert any("sdist" in item for item in evidence.limitations)  # only the wheel was verified


def test_source_tree_green_but_wheel_missing_package_data_fails(tmp_path):
    from assertiva.adapters.pytest_native import PytestNativeAdapter

    root = make_package(tmp_path / "nodata", package_data=False)
    assert PytestNativeAdapter(python=sys.executable).run(root).status is StageStatus.PASS  # SOURCE_TREE_PASS
    evidence = ADAPTER.qualify(root)
    assert evidence.status is StageStatus.FAIL  # INSTALLED_ARTIFACT_FAIL
    assert check(evidence, "tests").status is StageStatus.FAIL
    assert "greet/templates/hello.txt" in evidence.omitted_files


def test_installed_import_failure_is_detected(tmp_path):
    evidence = ADAPTER.qualify(make_package(tmp_path / "sub", subpackage=True))  # greet.text not packaged
    assert evidence.status is StageStatus.FAIL
    assert check(evidence, "import").status is StageStatus.FAIL


def test_build_failure_is_fail(tmp_path):
    root = make_package(tmp_path / "badbuild")
    (root / "pyproject.toml").write_text("[build-system]\nrequires = ['setuptools']\nbuild-backend = 'setuptools.build_meta'\n[project]\nname = 'greet'\nversion = 'not a version'\n", encoding="utf-8")
    evidence = ADAPTER.qualify(root)
    assert evidence.status is StageStatus.FAIL
    assert [c.name for c in evidence.checks] == ["build"]


def test_install_failure_is_fail(tmp_path):
    evidence = ADAPTER.qualify(make_package(tmp_path / "noinstall", extra_project='requires-python = ">=99"\n'))
    assert evidence.status is StageStatus.FAIL
    assert check(evidence, "install").status is StageStatus.FAIL


def test_missing_interpreter_is_blocked(tmp_path):
    evidence = PythonPackageAdapter(python=str(tmp_path / "missing-python")).qualify(make_package(tmp_path / "x"))
    assert evidence.status is StageStatus.BLOCKED


def test_project_without_packaging_is_not_supported(tmp_path, calc_project):
    from assertiva.verification import SupportLevel

    assert ADAPTER.supports(calc_project) is SupportLevel.UNSUPPORTED


def test_unsupported_project_leaves_stage_not_run(calc_project):
    session = start_improve(calc_project, python=sys.executable)
    try:
        q = qualify_candidate(session).qualification
    finally:
        discard_session(session)
    stage = next(s for s in q.stages if s.stage is QualificationStage.BUILD_AND_ARTIFACT)
    assert stage.status is StageStatus.NOT_RUN


def test_candidate_fixing_the_artifact_is_an_improvement(tmp_path):
    root = make_package(tmp_path / "proj", package_data=False)
    session = start_improve(root, python=sys.executable)
    try:
        (session.workspace / "pyproject.toml").write_text(
            (session.workspace / "pyproject.toml").read_text(encoding="utf-8") + WITH_DATA, encoding="utf-8"
        )
        q = qualify_candidate(session).qualification
    finally:
        discard_session(session)
    stage = next(s for s in q.stages if s.stage is QualificationStage.BUILD_AND_ARTIFACT)
    assert stage.status is StageStatus.PASS
    assert "greet-0.1.0" in stage.summary and ".whl" in stage.summary
    assert next(d for d in q.metric_deltas if d.name == "artifact_qualified").state is DeltaState.IMPROVED


def test_candidate_breaking_the_artifact_fails_the_stage(tmp_path):
    root = make_package(tmp_path / "proj2")
    session = start_improve(root, python=sys.executable)
    try:
        text = (session.workspace / "pyproject.toml").read_text(encoding="utf-8").replace(WITH_DATA, "")
        (session.workspace / "pyproject.toml").write_text(text, encoding="utf-8")
        q = qualify_candidate(session).qualification
    finally:
        discard_session(session)
    stage = next(s for s in q.stages if s.stage is QualificationStage.BUILD_AND_ARTIFACT)
    assert stage.status is StageStatus.FAIL
    assert next(d for d in q.metric_deltas if d.name == "artifact_qualified").state is DeltaState.REGRESSED
    assert not q.ready_for_review


def test_audit_execute_reports_source_green_artifact_red(tmp_path, capsys):
    import json

    from assertiva import cli
    from assertiva.workspace import tree_fingerprint

    root = make_package(tmp_path / "audited", package_data=False)
    before = tree_fingerprint(root)
    cli.main(["audit", str(root), "--execute", "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert tree_fingerprint(root) == before
    assert report["states"]["current"]["runs"][0]["status"] == "PASS"  # source tree green
    codes = {f["code"] for f in report["findings"]}
    assert {"ARTIFACT_QUALIFICATION_FAILED", "ARTIFACT_OMITS_SOURCE_FILES"} <= codes
    assert any("greet-0.1.0" in item for item in report["claim_boundary"]["not_evidenced"])
    assert 'id="artifact-evidence"' in open(report["report_path"], encoding="utf-8").read()


def test_target_interpreter_with_inherited_site_dirs_keeps_its_dependencies(tmp_path):
    """Found by dogfooding: deps visible to the target only via an extra site dir were lost."""
    import subprocess

    import pytest
    import setuptools

    venv = tmp_path / "target-env"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    target = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    site = subprocess.run([str(target), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"], capture_output=True, text=True).stdout.strip()
    # pytest/setuptools reach this interpreter only through extra site directories
    # (wherever they are installed for the interpreter running this test).
    inherited = dict.fromkeys(str(Path(m.__file__).resolve().parents[1]) for m in (pytest, setuptools))
    (Path(site) / "inherited.pth").write_text("\n".join(inherited) + "\n")
    evidence = PythonPackageAdapter(python=str(target)).qualify(make_package(tmp_path / "pkg"))
    assert check(evidence, "tests").status is StageStatus.PASS, evidence
