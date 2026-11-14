"""Collection errors that only say the unprepared environment lacks third-party modules are attributed to it.

Found in the SotuHire dogfood (2026-11-14): with the Python environment not prepared (no provision consent), 47 test
files failed to import `fastapi`, `streamlit` or `docx`, all declared by the project. The audit reported
ENVIRONMENT_NOT_PREPARED (info) next to NATIVE_COLLECTION_ERRORS (high) without connecting them, so the
collection errors read as a test or product failure.
"""

from types import SimpleNamespace

from assertiva.audit import environment_collection_cause
from assertiva.report_narrative import NARRATIVE


def _run(causes: dict[str, str]):
    details = {node: {"cause": cause, "kind": "IMPORT_FAILURE" if "Module" in cause or "Import" in cause else "SYNTAX_ERROR"}
               for node, cause in causes.items()}
    return SimpleNamespace(collection_errors=list(causes), metadata={"collection_error_details": details})


BLOCKED_ENV = [SimpleNamespace(step_id="python-env", status="BLOCKED")]
MISSING = {
    "tests/test_api.py": "ModuleNotFoundError: No module named 'fastapi'",
    "tests/test_ui.py": "ModuleNotFoundError: No module named 'streamlit'",
    "tests/test_export.py": "ModuleNotFoundError: No module named 'docx'",
    "tests/test_api_two.py": "ModuleNotFoundError: No module named 'fastapi.testclient'",
}


def test_missing_third_party_modules_with_an_unprepared_environment_are_the_environment(tmp_path):
    cause = environment_collection_cause([_run(MISSING)], BLOCKED_ENV, tmp_path)
    assert cause is not None
    assert cause["origin"] == "ENVIRONMENT"
    assert cause["count"] == 4 and cause["of"] == 4
    assert cause["missing_modules"] == {"fastapi": 2, "docx": 1, "streamlit": 1}
    assert cause["unprepared_steps"] == ["python-env"]


def test_a_prepared_environment_leaves_the_errors_undecided(tmp_path):
    assert environment_collection_cause([_run(MISSING)], [], tmp_path) is None


def test_a_missing_module_that_is_the_projects_own_package_is_not_the_environment(tmp_path):
    (tmp_path / "fastapi").mkdir()  # the project ships a package with that name: a path or product problem
    assert environment_collection_cause([_run(MISSING)], BLOCKED_ENV, tmp_path) is None
    (tmp_path / "fastapi").rmdir()
    (tmp_path / "src" / "docx").mkdir(parents=True)
    assert environment_collection_cause([_run(MISSING)], BLOCKED_ENV, tmp_path) is None


def test_another_kind_of_collection_error_keeps_the_errors_undecided(tmp_path):
    mixed = {**MISSING, "tests/test_broken.py": "SyntaxError: invalid syntax"}
    assert environment_collection_cause([_run(mixed)], BLOCKED_ENV, tmp_path) is None


def test_the_recommendation_has_a_localized_template():
    english = {en for en, _ in NARRATIVE}
    assert any(text.startswith("all {n} collection errors are third-party modules missing") for text in english)


def test_the_audit_attributes_them_end_to_end(tmp_path, capsys):
    # Through the CLI, as the SotuHire run did: Finding is frozen, so the wiring must replace it (the first version
    # of this fix assigned to it and crashed the whole audit; only the helper above was tested then).
    import json
    import sys

    import pytest

    from assertiva import cli

    root = tmp_path / "p"
    (root / "tests").mkdir(parents=True)
    (root / "requirements.txt").write_text("assertiva-missing-thirdparty-xyz==1.0\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    (root / "tests" / "test_uses_dependency.py").write_text(
        "import assertiva_missing_thirdparty_xyz\n\n\ndef test_dependency():\n    assert assertiva_missing_thirdparty_xyz\n",
        encoding="utf-8")
    code = cli.main(["audit", str(root), "--execute", "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    codes = {f["code"]: f for f in report["findings"]}
    if "NATIVE_COLLECTION_ERRORS" not in codes:
        pytest.skip("the pytest runner did not run in this environment; nothing to attribute")
    assert code == 0 and "ENVIRONMENT_NOT_PREPARED" in codes
    collection = codes["NATIVE_COLLECTION_ERRORS"]
    assert collection["evidence"]["dominant_cause"]["origin"] == "ENVIRONMENT"
    assert collection["evidence"]["dominant_cause"]["missing_modules"] == {"assertiva_missing_thirdparty_xyz": 1}
    assert collection["recommendation"].startswith("all 1 collection errors are third-party modules missing")
