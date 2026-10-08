"""Vitest evidence through the same core as every other runner (Vitest 3+, its JSON reporter in Jest's format).

The real fixture (tests/fixtures/js-vitest) is TypeScript with two projects, table cases, a skip, a todo and an
async test; `variants.json` was recorded from Vitest 5.0.3 with a failure, a pass after a retry and a file that
fails to load."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from assertiva.adapters.vitest import VitestAdapter
from assertiva.adapters.jest import parse_jest_format
from assertiva.adapters.vitest import FORMAT_LIMITS
from assertiva.candidate import QualificationCheck, StageStatus
from assertiva.models import Outcome
from assertiva.workspace import tree_fingerprint
from conftest import write

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT = FIXTURES / "js-vitest"


def parsed():
    return parse_jest_format((FIXTURES / "vitest-json" / "variants.json").read_text(encoding="utf-8"), "<ROOT>", "vitest", FORMAT_LIMITS)


def by_title(run):
    return {inv.invocation_id.split(" › ", 1)[1]: inv for inv in run.invocations}


def test_failures_retries_and_load_errors_from_real_vitest_output():
    run = parsed()
    assert run.adapter_id == "vitest" and run.status is StageStatus.FAIL
    assert run.collection_errors == ["src/broken.test.ts"]
    tests = by_title(run)
    assert tests["fails"].outcome is Outcome.FAILED and "expected 1 to be 2" in tests["fails"].message
    retried = tests["retried"]
    assert retried.outcome is Outcome.PASSED and "earlier failed attempts" in retried.message and retried.attempts is None
    assert any("retried" in lim for lim in run.limitations)


def test_table_cases_share_a_declaration_and_skips_are_never_passes():
    tests = by_title(parsed())
    first, second = tests["discount discount(100, VIP) is 90"], tests["discount discount(150, REGULAR) is 150"]
    assert first.declaration_id == second.declaration_id == "src/price.test.ts:8:14"
    assert tests["discount waits for a currency rule"].outcome is Outcome.SKIPPED
    assert tests["discount handles rounding of fractional cents"].outcome is Outcome.SKIPPED


def test_vitest_is_recognized_from_dependencies_or_configuration(tmp_path):
    from assertiva.verification import SupportLevel

    assert VitestAdapter().supports(PROJECT) is SupportLevel.SUPPORTED
    write(tmp_path / "vitest.config.mts", "export default {}\n")
    assert VitestAdapter().supports(tmp_path) is SupportLevel.SUPPORTED
    assert VitestAdapter().supports(tmp_path / "missing") is SupportLevel.UNSUPPORTED


def test_an_old_vitest_is_blocked_instead_of_writing_into_the_project(tmp_path):
    write(tmp_path / "package.json", json.dumps({"devDependencies": {"vitest": "1.6.0"}}))
    write(tmp_path / "node_modules" / "vitest" / "vitest.mjs", "")
    write(tmp_path / "node_modules" / "vitest" / "package.json", json.dumps({"version": "1.6.0"}))
    run = VitestAdapter().run(tmp_path)
    assert run.status is StageStatus.BLOCKED and "Vitest 3+" in run.limitations[0]


def _commit_all(root):
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def vitest_project(tmp_path):
    node = os.environ.get("ASSERTIVA_NODE") or shutil.which("node")
    modules = PROJECT / "node_modules"
    if not node or not (modules / "vitest").is_dir():
        reason = "requires Node and `npm ci --ignore-scripts` in tests/fixtures/js-vitest"
        if os.environ.get("ASSERTIVA_REQUIRE_JS"):
            pytest.fail(reason)
        pytest.skip(reason)
    root = tmp_path / "vitest-project"
    root.mkdir()
    for entry in ("package.json", "package-lock.json", "vitest.config.ts", "src", "api"):
        source = PROJECT / entry
        (shutil.copytree if source.is_dir() else shutil.copy2)(source, root / entry)
    try:
        os.symlink(modules, root / "node_modules", target_is_directory=True)
    except OSError:
        import _winapi

        _winapi.CreateJunction(str(modules), str(root / "node_modules"))
    write(root / ".gitignore", "node_modules/\n")
    _commit_all(root)
    return root


@pytest.mark.integration
def test_real_vitest_audit_measures_typescript_projects_and_writes_nothing(vitest_project):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    modules = (vitest_project / "node_modules").resolve()
    before, before_modules = tree_fingerprint(vitest_project), sorted(p.name for p in modules.iterdir())
    report = run_audit(vitest_project, execute=True)
    assert tree_fingerprint(vitest_project) == before and sorted(p.name for p in modules.iterdir()) == before_modules
    [run] = report["states"]["current"]["runs"]
    assert (run["adapter"], run["status"], run["invocations"]) == ("vitest", "PASS", 6)
    assert run["outcomes"] == {"PASSED": 4, "SKIPPED": 2}
    metrics = report["states"]["current"]["metrics"]
    assert metrics["line_coverage"]["value"] == 100 and metrics["branch_covered"]["value"] == 4
    assert "vitest" in render_html(report)


@pytest.mark.integration
def test_real_vitest_candidate_qualification_detects_a_regression(vitest_project):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    session = start_improve(vitest_project)
    try:
        write(session.workspace / "src" / "boundary.test.ts",
              'import { expect, test } from "vitest";\nimport { discount } from "./price";\n\n'
              'test("vip boundary", () => { expect(discount(10, "VIP")).toBe(9); });\n')
        checks = {c.check: c.status for c in qualify_candidate(session, stability_reruns=0).qualification.checks}
        assert checks[QualificationCheck.CANDIDATE_TESTS] is StageStatus.PASS
        assert checks[QualificationCheck.ORIGINAL_REGRESSION] is StageStatus.PASS
        price = session.workspace / "src" / "price.ts"
        price.write_text(price.read_text(encoding="utf-8").replace("total * 90", "total * 80"), encoding="utf-8")
        broken = {c.check: c.status for c in qualify_candidate(session, stability_reruns=0).qualification.checks}
        assert broken[QualificationCheck.ORIGINAL_REGRESSION] is StageStatus.FAIL
    finally:
        discard_session(session)


@pytest.mark.integration
def test_the_ci_vitest_check_is_reproduced_with_per_test_outcomes(vitest_project, capsys):
    import sys

    from assertiva import cli

    write(vitest_project / ".github" / "workflows" / "ci.yml",
          "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npx vitest run --project unit\n")
    subprocess.run(["git", "-c", "user.name=f", "-c", "user.email=f@example.invalid", "commit", "-qam", "ci"], cwd=vitest_project, check=False)
    subprocess.run(["git", "add", "-A"], cwd=vitest_project, check=True)
    code = cli.main(["audit", str(vitest_project), "--python", sys.executable, "--run-check", "gha:.github/workflows/ci.yml:test:1",
                     "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0
    [check] = report["declared_checks"]
    assert check["status"] == "PASS" and check["execution"]["via"] == "vitest"
    [run] = report["states"]["current"]["runs"]
    assert run["invocations"] == 5  # only the `unit` project the CI step selects
