"""Browser evidence: Playwright Test results, project/browser matrix and locator evidence through the shared core."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from assertiva.adapters.playwright import PlaywrightAdapter, classify_locator, parse_playwright_results
from assertiva.candidate import MetricDirection, QualificationCheck, StageStatus
from assertiva.models import Outcome

from conftest import write

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT = FIXTURES / "js-playwright"


def recorded(name):
    return parse_playwright_results((FIXTURES / "playwright-json" / name).read_text(encoding="utf-8"), "<ROOT>")


def by_title(run, project="chromium"):
    return {inv.invocation_id.split(" › ")[-1].removesuffix(f" [{project}]"): inv
            for inv in run.invocations if inv.invocation_id.endswith(f"[{project}]")}


# --- normalization of real Playwright JSON reports (recorded from Playwright 1.63.0) ------

def test_chromium_run_outcomes_retries_and_attachments():
    run = recorded("chromium.json")
    tests = by_title(run)
    assert run.status is StageStatus.PASS
    assert {t: i.outcome for t, i in tests.items()} == {
        "semantic locators": Outcome.PASSED, "structural locators": Outcome.PASSED,
        "passes only on retry": Outcome.PASSED, "not ready yet": Outcome.SKIPPED,
    }
    retried = tests["passes only on retry"]
    assert "2 attempts" in retried.message and any("passes only on retry" in lim for lim in run.limitations)
    assert retried.source_paths == ("tests/form.spec.js",) and retried.declaration_id == "tests/form.spec.js:28:3"
    assert retried.invocation_id == "tests/form.spec.js › signup form › passes only on retry [chromium]"
    kinds = {(a["name"], a["attempt"]) for a in run.metadata["attachments"][retried.invocation_id]}
    assert {("screenshot", 0), ("trace", 1)} <= kinds
    assert all(not os.path.isabs(a["path"]) for a in run.metadata["attachments"][retried.invocation_id] if a["path"])
    # what ran, and the evidence a failure or a retried pass left (a trace replays it)
    assert run.metadata["context"]["playwright_version"] == "1.63.0" and run.metadata["context"]["retries"]["chromium"] == 1
    assert run.metadata["failure_evidence"] == {retried.invocation_id: ["error-context", "screenshot", "trace"]}
    assert not any("left no trace" in lim for lim in run.limitations)


def test_declared_selected_executed_matrix():
    chromium_only = recorded("chromium.json")
    assert chromium_only.metadata["matrix"] == {
        "project chromium": "EXECUTED", "project firefox": "DECLARED",
        "engine chromium": "EXECUTED", "engine firefox": "DECLARED", "engine webkit": "NOT_CONFIGURED",
    }
    assert any("firefox" in lim and "not selected" in lim for lim in chromium_only.limitations)
    listed = recorded("list.json")
    assert listed.status is StageStatus.UNKNOWN and {i.outcome for i in listed.invocations} == {Outcome.NOT_RUN}
    assert listed.metadata["matrix"]["project chromium"] == "SELECTED"


def test_missing_browser_is_not_executed_not_a_test_failure():
    run = recorded("all-projects.json")
    firefox = by_title(run, "firefox")
    assert {i.outcome for t, i in firefox.items() if t != "not ready yet"} == {Outcome.NOT_RUN}
    assert "not installed" in firefox["semantic locators"].message
    assert run.status is StageStatus.PASS  # chromium passed; firefox never ran: a limitation, not a failure
    assert run.metadata["matrix"]["project firefox"] == "SELECTED" and run.metadata["matrix"]["engine webkit"] == "NOT_CONFIGURED"
    assert any("firefox" in lim and "browser is not installed" in lim for lim in run.limitations)


def test_failures_expected_failures_fixme_and_generated_cases():
    run = recorded("variants.json")
    tests = by_title(run)
    assert run.status is StageStatus.FAIL
    assert tests["fails"].outcome is Outcome.FAILED and "Total: 11" in tests["fails"].message
    assert tests["known bug"].outcome is Outcome.XFAILED
    assert tests["broken upstream"].outcome is Outcome.SKIPPED and "fixme" in tests["broken upstream"].markers
    small, large = tests["renders small"], tests["renders large"]
    assert small.declaration_id == large.declaration_id == "tests/variants.spec.js:15:5"
    assert (small.parameters_id, large.parameters_id) == ("renders small", "renders large")
    assert "\x1b" not in tests["fails"].message


def test_a_file_that_cannot_load_aborts_the_run():
    run = recorded("load-error.json")
    assert run.status is StageStatus.FAIL and not run.invocations
    assert run.collection_errors == ["tests/broken.spec.js"]
    assert run.metadata["error_sources"] == {"tests/broken.spec.js": "tests/broken.spec.js"}


@pytest.mark.parametrize("payload", ["not json", "{}", '{"suites": 3}'])
def test_unreadable_results_are_blocked(payload):
    run = parse_playwright_results(payload, "<ROOT>")
    assert run.status is StageStatus.BLOCKED and run.limitations


# --- locator evidence: coupling/semantics, never a score ---------------------------------

@pytest.mark.parametrize(("call", "kind"), [
    ('getByRole("button", { name: "Send" })', "ROLE"), ('getByLabel("Email")', "LABEL"),
    ('getByPlaceholder("you@x")', "PLACEHOLDER"), ('getByText("Hi")', "TEXT"), ('getByTestId("submit")', "TEST_ID"),
    ('locator("p.hint")', "CSS"), ('locator("css=#a")', "CSS"), ("locator('xpath=//b')", "XPATH"), ('locator("//div")', "XPATH"),
    ('locator("text=Hi")', "TEXT"), ('locator("role=button")', "ROLE"), ('locator("data-testid=x")', "TEST_ID"),
    ('$(".x")', "CSS"), ('getByAltText("logo")', "OTHER"), ('getByTitle("t")', "OTHER"), ("locator(selector)", "UNKNOWN"),
])
def test_locator_kinds(call, kind):
    assert classify_locator(call) == kind


def test_fixture_locator_evidence_is_informational():
    from assertiva.evidence import StateEvidence, state_metrics

    signals = PlaywrightAdapter().static_signals(PROJECT)
    assert {k: v for k, v in signals.items() if v} == {
        "locator_role": 1, "locator_label": 1, "locator_placeholder": 1, "locator_text": 1,
        "locator_test_id": 1, "locator_css": 1, "locator_xpath": 1,
    }
    state = StateEvidence("s", "test")
    state.static.update(signals)
    assert {state_metrics(state)[k].direction for k in signals} == {MetricDirection.INFORMATIONAL}


# --- discovery and safety ------------------------------------------------------------------

def test_remote_base_url_is_never_targeted(tmp_path):
    write(tmp_path / "package.json", '{"devDependencies": {"@playwright/test": "1.63.0"}}')
    write(tmp_path / "playwright.config.js", 'module.exports = { use: { baseURL: "https://shop.example.com" } };\n')
    write(tmp_path / "node_modules" / "playwright" / "cli.js", "")
    run = PlaywrightAdapter().run(tmp_path)
    assert run.status is StageStatus.BLOCKED and not run.command
    assert any("shop.example.com" in lim and "remote" in lim for lim in run.limitations)


# --- real Playwright runs (Node, the fixture's node_modules and a Chromium build) ----------

def _browser_available() -> bool:
    """A Chromium build of the revision the fixture's Playwright expects (an older revision in the cache cannot run
    it: the run would report every project as not executed)."""
    if os.environ.get("ASSERTIVA_PW_CHANNEL"):
        return True
    cache = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or (
        Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" if os.name == "nt" else Path.home() / ".cache" / "ms-playwright")
    try:
        browsers = json.loads((PROJECT / "node_modules" / "playwright-core" / "browsers.json").read_text(encoding="utf-8"))["browsers"]
    except (OSError, ValueError, KeyError):
        return False
    wanted = {f"{b['name'].replace('-', '_')}-{b['revision']}" for b in browsers if b["name"] in ("chromium", "chromium-headless-shell")}
    return any((Path(cache) / name / "INSTALLATION_COMPLETE").is_file() for name in wanted)


@pytest.fixture
def playwright_project(tmp_path):
    node = os.environ.get("ASSERTIVA_NODE") or shutil.which("node")
    modules = PROJECT / "node_modules"
    if not node or not (modules / "playwright").is_dir() or not _browser_available():
        reason = ("requires Node, `npm ci --ignore-scripts` in tests/fixtures/js-playwright and a Chromium build of the revision "
                  "its Playwright expects (playwright-core/browsers.json)")
        if os.environ.get("ASSERTIVA_REQUIRE_PLAYWRIGHT"):
            pytest.fail(reason)
        pytest.skip(reason)
    root = tmp_path / "pw-project"
    root.mkdir()
    for entry in ("package.json", "package-lock.json", "playwright.config.js", "tests"):
        source = PROJECT / entry
        (shutil.copytree if source.is_dir() else shutil.copy2)(source, root / entry)
    try:
        os.symlink(modules, root / "node_modules", target_is_directory=True)
    except OSError:
        import _winapi

        _winapi.CreateJunction(str(modules), str(root / "node_modules"))
    write(root / ".gitignore", "node_modules/\ntest-results/\n")
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)
    return root


@pytest.mark.integration
@pytest.mark.browser
def test_real_playwright_run_through_audit(playwright_project):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    report = run_audit(playwright_project, execute=True)
    [run] = [r for r in report["states"]["current"]["runs"] if r["adapter"] == "playwright"]
    assert run["status"] == "PASS" and run["invocations"] == 8
    assert run["matrix"]["engine chromium"] == "EXECUTED" and run["matrix"]["engine webkit"] == "NOT_CONFIGURED"
    assert run["matrix"]["project firefox"] in ("SELECTED", "EXECUTED")
    assert run["attachments"] >= 2
    assert report["states"]["current"]["metrics"]["locator_role"]["value"] == 1
    assert any("webkit" in item for item in report["claim_boundary"]["not_evidenced"])
    html = render_html(report)
    assert "NOT_CONFIGURED" in html and "playwright" in html


@pytest.mark.integration
@pytest.mark.browser
def test_real_playwright_candidate_qualification(playwright_project):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    session = start_improve(playwright_project)
    try:
        write(session.workspace / "tests" / "title.spec.js",
              'const { test, expect } = require("@playwright/test");\n'
              'test("heading", async ({ page }) => {\n  await page.setContent("<h1>Shop</h1>");\n'
              '  await expect(page.getByRole("heading", { name: "Shop" })).toBeVisible();\n});\n')
        q = qualify_candidate(session, stability_reruns=0).qualification
    finally:
        discard_session(session)
    stages = {c.check: c.status for c in q.checks}
    assert stages[QualificationCheck.CANDIDATE_TESTS] is StageStatus.PASS
    assert stages[QualificationCheck.ORIGINAL_REGRESSION] is StageStatus.PASS
    assert json.dumps([d.name for d in q.metric_deltas]).count("locator_role") == 1


# --- outcomes Playwright folds into "skipped" and "flaky" (computeTestCaseOutcome, teleReceiver.ts at 41e6a18) ------

def _one(title, expected, status, *results):
    return json.dumps({"config": {"projects": [{"id": "chromium", "name": "chromium", "testDir": "<ROOT>/tests"}]},
                       "suites": [{"title": "a.spec.js", "file": "a.spec.js", "specs": [{"title": title, "file": "a.spec.js", "line": 1, "column": 1,
                                   "tests": [{"projectId": "chromium", "projectName": "chromium", "expectedStatus": expected, "status": status,
                                              "annotations": [], "results": [{"status": s, "retry": i, "errors": []} for i, s in enumerate(results)]}]}]}]})


@pytest.mark.parametrize(("expected", "status", "results", "outcome"), [
    ("skipped", "skipped", ["skipped"], Outcome.SKIPPED),  # test.skip / fixme: the author skipped it
    ("passed", "skipped", ["skipped"], Outcome.NOT_RUN),  # expected to run: the run stopped before it or a serial predecessor failed
    ("passed", "skipped", ["interrupted"], Outcome.NOT_RUN),  # only interrupted results
    ("passed", "flaky", ["failed", "passed"], Outcome.PASSED),  # a pass after a failed attempt
    ("failed", "flaky", ["failed", "passed"], Outcome.XFAILED),  # test.fail: failed as expected once, passed once
    ("skipped", "flaky", ["failed", "skipped"], Outcome.SKIPPED),  # failed, then skipped on retry: never a pass
])
def test_skipped_and_flaky_keep_what_playwright_folds_into_them(expected, status, results, outcome):
    [inv] = parse_playwright_results(_one("t", expected, status, *results), "<ROOT>").invocations
    assert inv.outcome is outcome
    if status == "flaky" and outcome is not Outcome.PASSED:
        assert "passed after" not in (inv.message or "")


def test_a_failure_without_a_trace_is_named_as_not_replayable():
    data = json.loads((FIXTURES / "playwright-json" / "chromium.json").read_text(encoding="utf-8"))

    def strip(suite):
        for spec in suite.get("specs") or []:
            for test in spec.get("tests") or []:
                for result in test.get("results") or []:
                    result["attachments"] = [a for a in result.get("attachments") or [] if a.get("name") != "trace"]
        for child in suite.get("suites") or []:
            strip(child)

    for suite in data["suites"]:
        strip(suite)
    run = parse_playwright_results(data, "<ROOT>")
    assert any("left no trace to replay" in lim for lim in run.limitations)
