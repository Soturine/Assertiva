"""First JS/TS slice: Jest evidence through the same core as every other runner."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from assertiva.adapters.jest import JestAdapter, parse_jest_results
from assertiva.candidate import QualificationCheck, StageStatus
from assertiva.models import Outcome

from conftest import write

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT = FIXTURES / "js-jest"


def recorded(name):
    return json.loads((FIXTURES / "jest-json" / name).read_text(encoding="utf-8"))


def by_title(run):
    return {inv.invocation_id.split(" › ", 1)[1]: inv for inv in run.invocations}


# --- normalization of real Jest --json output (recorded from Jest 30.5.2) ------------

def test_outcomes_skips_and_todos_are_normalized():
    run = parse_jest_results(recorded("passing.json"), "<ROOT>")
    tests = by_title(run)
    assert run.status is StageStatus.PASS
    assert tests["discount rejects a negative total"].outcome is Outcome.PASSED
    assert tests["discount waits for a currency rule"].outcome is Outcome.SKIPPED
    todo = tests["discount handles rounding of fractional cents"]
    assert todo.outcome is Outcome.SKIPPED and "todo" in todo.message
    assert all(inv.source_paths == ("__tests__/price.test.js",) for inv in run.invocations)


def test_table_cases_keep_their_shared_declaration():
    run = parse_jest_results(recorded("passing.json"), "<ROOT>")
    tests = by_title(run)
    first, second = tests["discount discount(100, VIP) is 90"], tests["discount discount(150, REGULAR) is 150"]
    assert first.declaration_id == second.declaration_id == "__tests__/price.test.js:7:5"
    assert first.parameters_id == "discount(100, VIP) is 90" and first.invocation_id != second.invocation_id
    assert tests["discount rejects a negative total"].declaration_id != first.declaration_id
    assert tests["discount rejects a negative total"].parameters_id is None


def test_failures_collection_errors_and_retries():
    run = parse_jest_results(recorded("variants.json"), "<ROOT>")
    assert run.status is StageStatus.FAIL
    assert run.collection_errors == ["__tests__/broken.test.js"]
    assert run.metadata["error_sources"] == {"__tests__/broken.test.js": "__tests__/broken.test.js"}
    tests = by_title(run)
    failed = tests["vip boundary"]
    assert failed.outcome is Outcome.FAILED and "toBe" in failed.message
    retried = tests["passes on the second attempt"]
    assert retried.outcome is Outcome.PASSED and "2 invocations" in retried.message  # earlier failure not erased
    assert any("retried" in item for item in run.limitations)


def test_format_limits_are_declared():
    run = parse_jest_results(recorded("passing.json"), "<ROOT>")
    text = " ".join(run.limitations)
    assert "source location" in text and "first attempt" in text


@pytest.mark.parametrize("content", ["{", json.dumps({"testResults": "nope"})])
def test_malformed_results_are_blocked(content, tmp_path):
    run = parse_jest_results(content, "<ROOT>")
    assert run.status is StageStatus.BLOCKED and run.invocations == []


def test_missing_node_is_blocked(tmp_path, monkeypatch):
    write(tmp_path / "package.json", json.dumps({"devDependencies": {"jest": "30.5.2"}}))
    write(tmp_path / "node_modules" / "jest" / "bin" / "jest.js", "")
    monkeypatch.setenv("ASSERTIVA_NODE", str(tmp_path / "no-node-here"))
    run = JestAdapter().run(tmp_path)
    assert run.status is StageStatus.BLOCKED and "Node" in run.limitations[0]


def test_package_scripts_join_the_verification_surface(tmp_path):
    from assertiva.verification import VerificationKind, VerificationOrigin, discover_surface

    write(tmp_path / "package.json", json.dumps({"scripts": {"test": "jest --ci", "lint": "eslint .", "deploy": "./ship.sh"}}))
    checks = {c.check_id: c for c in discover_surface(tmp_path).checks}
    assert checks["package-script:test"].kind is VerificationKind.TEST and checks["package-script:test"].origin is VerificationOrigin.LOCAL
    assert checks["package-script:lint"].kind is VerificationKind.LINT
    assert checks["package-script:deploy"].kind is VerificationKind.UNKNOWN


def _commit_all(root):
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)


def test_installed_dependencies_are_linked_into_copies_never_copied(tmp_path):
    from assertiva.evidence import runnable_copy
    from assertiva.workspace import PathBoundaryError, is_link, link_installed, remove_tree

    origin = tmp_path / "project"
    write(origin / "package.json", '{"devDependencies": {"jest": "30.5.2"}}')
    write(origin / "node_modules" / "jest" / "bin" / "jest.js", "")
    write(origin / ".gitignore", "node_modules/\n")
    _commit_all(origin)  # installed dependencies are ignored, so the copy never contains them
    copy = runnable_copy(origin, [JestAdapter()], origin)
    try:
        assert is_link(copy / "node_modules") and (copy / "node_modules" / "jest" / "bin" / "jest.js").is_file()
    finally:
        remove_tree(copy)
    assert (origin / "node_modules" / "jest" / "bin" / "jest.js").is_file()  # removing the copy never follows the link
    for name in ("../outside", "/abs", ""):
        with pytest.raises(PathBoundaryError):
            link_installed(tmp_path / "copy", origin, [name])


# --- real Jest runs (Node + the fixture's node_modules installed once) ----------------

@pytest.fixture
def jest_project(tmp_path):
    node = os.environ.get("ASSERTIVA_NODE") or shutil.which("node")
    modules = PROJECT / "node_modules"
    if not node or not (modules / "jest").is_dir():
        reason = "requires Node and `npm ci --ignore-scripts` in tests/fixtures/js-jest"
        if os.environ.get("ASSERTIVA_REQUIRE_JS"):
            pytest.fail(reason)
        pytest.skip(reason)
    root = tmp_path / "js-project"
    root.mkdir()
    for entry in ("package.json", "package-lock.json", "src", "__tests__"):
        source = PROJECT / entry
        (shutil.copytree if source.is_dir() else shutil.copy2)(source, root / entry)
    try:
        os.symlink(modules, root / "node_modules", target_is_directory=True)
    except OSError:
        import _winapi

        _winapi.CreateJunction(str(modules), str(root / "node_modules"))
    # The realistic shape: installed dependencies are ignored by Git, so they are never copied.
    write(root / ".gitignore", "node_modules/\n")
    _commit_all(root)
    return root


@pytest.mark.integration
def test_real_jest_run_through_audit(jest_project):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    report = run_audit(jest_project, execute=True)
    [run] = report["states"]["current"]["runs"]
    assert (run["adapter"], run["status"], run["invocations"]) == ("jest", "PASS", 5)
    metrics = report["states"]["current"]["metrics"]
    assert metrics["line_coverage"]["value"] == 100 and metrics["skipped"]["value"] == 2
    assert any(c["check_id"] == "package-script:test" for c in report["verification_surface"])
    html = render_html(report)
    assert "jest" in html and "package-script:test" in html


@pytest.mark.integration
def test_real_jest_candidate_qualification(jest_project):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    session = start_improve(jest_project)
    try:
        write(session.workspace / "__tests__" / "boundary.test.js",
              'const { discount } = require("../src/price");\ntest("vip boundary", () => { expect(discount(99, "VIP")).toBe(99); });\n')
        q = qualify_candidate(session, stability_reruns=0).qualification
        stages = {c.check: c.status for c in q.checks}
        assert stages[QualificationCheck.CANDIDATE_TESTS] is StageStatus.PASS
        assert stages[QualificationCheck.ORIGINAL_REGRESSION] is StageStatus.PASS
        (session.workspace / "src" / "price.js").write_text(
            (session.workspace / "src" / "price.js").read_text(encoding="utf-8").replace("total * 90", "total * 80"), encoding="utf-8")
        broken = {c.check: c.status for c in qualify_candidate(session, stability_reruns=0).qualification.checks}
        assert broken[QualificationCheck.ORIGINAL_REGRESSION] is StageStatus.FAIL
    finally:
        discard_session(session)
