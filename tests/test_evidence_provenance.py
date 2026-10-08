"""Imported evidence keeps its provenance and its uncertainty; time and identity are what the format gives.

Found by auditing a real project: a JUnit report of a parallel run showed 815 cases, so the audit counted 815
declarations, and summed case times (≈376 s) were shown as the run's wall clock (≈112 s real). Synthetic reports."""

import json

from assertiva.adapters.ci_runs import identity, load_ci_run
from assertiva.adapters.coverage_reports import is_test_path, load_coverage_report
from assertiva.adapters.junit import load_junit
from assertiva.evidence import StateEvidence, state_metrics
from conftest import write

PARALLEL = """<testsuites time="12.0">
  <testsuite name="workers-1" time="11.5">
    <testcase classname="tests.test_upload" name="test_rejects_large_file" time="5.0"/>
    <testcase classname="tests.test_upload" name="test_size_limit[10]" time="3.0"/>
    <testcase classname="tests.test_upload" name="test_size_limit[20]" time="3.0"><failure message="boom"/></testcase>
  </testsuite>
  <testsuite name="workers-2" time="11.8">
    <testcase classname="tests.test_auth" name="test_expired_token" time="6.0"><skipped/></testcase>
    <testcase classname="tests.test_auth" name="test_valid_token" time="5.5"/>
  </testsuite>
</testsuites>"""


def test_a_parallel_report_is_not_given_a_wall_clock_from_summed_cases(tmp_path):
    run = load_junit(write(tmp_path / "r.xml", PARALLEL))
    assert run.wall_clock_s is None  # the real duration is not in the format
    assert run.metadata["cases_duration_sum_s"] == 22.5 and run.metadata["reported_root_time_s"] == 12.0
    assert [s["reported_time_s"] for s in run.metadata["suites"]] == [11.5, 11.8]
    metrics = state_metrics(StateEvidence("current", "report", runs=[run]))
    assert metrics["wall_clock_s"].value is None and metrics["test_time_accumulated_s"].value == 22.5


def test_cases_are_not_declarations_but_parameter_suffixes_group_them(tmp_path):
    run = load_junit(write(tmp_path / "r.xml", PARALLEL))
    assert run.metadata["declaration_identity"] == "UNKNOWN" and run.metadata["provenance"] == "EXTERNAL_UNVERIFIED"
    params = [inv for inv in run.invocations if inv.parameters_id]
    assert {inv.parameters_id for inv in params} == {"10", "20"} and len({inv.declaration_id for inv in params}) == 1
    metrics = state_metrics(StateEvidence("current", "report", runs=[run]))
    assert "test_declarations" not in metrics and metrics["test_invocations"].value == 5  # cases, never declarations


def test_an_incomplete_or_invalid_report_is_not_evidence(tmp_path):
    truncated = load_junit(write(tmp_path / "t.xml", PARALLEL[:300]))
    assert truncated.status.value == "BLOCKED" and not truncated.invocations
    empty = load_junit(write(tmp_path / "e.xml", "<testsuites/>"))
    assert empty.status.value == "UNKNOWN"


def test_the_audit_report_says_who_produced_each_result_and_what_was_only_read(tmp_path):
    from assertiva.audit import run_audit

    write(tmp_path / "p" / "app.py", "X = 1\n")
    report_file = write(tmp_path / "r.xml", PARALLEL)
    report = run_audit(tmp_path / "p", junit_reports=[report_file])
    [run] = report["states"]["current"]["runs"]
    assert run["provenance"] == "EXTERNAL_UNVERIFIED" and run["cases_duration_sum_s"] == 22.5
    manifest = report["execution_manifest"]
    assert manifest["read"][0]["kind"] == "test_results" and len(manifest["read"][0]["sha256"]) == 64
    assert manifest["code"]["vcs_revision"] is None and manifest["code"]["tree_digest"] == report["project"]["digest"]
    assert "no version control" in manifest["code"]["note"]  # a ZIP-like tree is identified by content, never by an invented SHA


COVERAGE_PY = {
    "totals": {"covered_lines": 90, "num_statements": 100, "covered_branches": 8, "num_branches": 10},
    "files": {
        "app/orders.py": {"summary": {"covered_lines": 50, "num_statements": 70, "covered_branches": 6, "num_branches": 8}},
        "tests/test_orders.py": {"summary": {"covered_lines": 40, "num_statements": 30, "covered_branches": 2, "num_branches": 2}},
    },
}


def test_coverage_of_product_code_is_kept_apart_from_test_code(tmp_path):
    summary = load_coverage_report(write(tmp_path / "coverage.json", json.dumps(COVERAGE_PY)))
    assert summary.counts["line"] == {"covered": 90, "total": 100}  # the whole tree, as reported
    assert summary.product_counts["line"] == {"covered": 50, "total": 70} and summary.test_files == 1 and summary.files == 2


def test_test_paths_follow_conventions_across_languages():
    for path in ("tests/test_x.py", "pkg/x_test.py", "src/a.test.ts", "web/b.spec.jsx", "src/test/kotlin/ATest.kt",
                 "app/src/androidTest/java/UiTest.java", "conftest.py"):
        assert is_test_path(path), path
    for path in ("src/main/kotlin/Order.kt", "app/orders.py", "contest/main.py", "src/testing_utils.py"):
        assert not is_test_path(path), path


def test_ingested_coverage_is_never_presented_as_measured(tmp_path):
    from assertiva.audit import run_audit

    write(tmp_path / "p" / "app.py", "X = 1\n")
    report = run_audit(tmp_path / "p", coverage_reports=[write(tmp_path / "coverage.json", json.dumps(COVERAGE_PY))])
    [coverage] = report["states"]["current"]["coverage"]
    assert coverage["origin"] == "INGESTED"
    assert any("read by Assertiva, not measured" in line for line in report["claim_boundary"]["observed"])


GH_RUN = {"databaseId": 7, "headSha": "a" * 40, "conclusion": "failure", "status": "completed", "url": "https://example.invalid/run/7",
          "workflowName": "CI", "jobs": [{"name": "tests", "conclusion": "failure"}, {"name": "lint", "conclusion": "success"}]}


def test_a_provider_run_proves_a_revision_only_with_the_same_sha_and_a_clean_tree(tmp_path):
    run = load_ci_run(write(tmp_path / "run.json", json.dumps(GH_RUN)))
    assert run["provider"] == "github-actions" and run["head_sha"] == "a" * 40
    assert identity(run, "a" * 40, False) == "SAME_REVISION"
    assert identity(run, "a" * 40, True) == "LOCAL_CHANGES"
    assert identity(run, "b" * 40, False) == "OTHER_REVISION"
    assert identity(run, None, None) == "UNKNOWN"  # no version control: no correspondence is claimed
    gitlab = load_ci_run(write(tmp_path / "p.json", json.dumps({"id": 3, "sha": "c" * 40, "status": "success", "web_url": "u"})))
    assert gitlab["provider"] == "gitlab-ci" and gitlab["conclusion"] == "success"
    assert "error" in load_ci_run(write(tmp_path / "x.json", '[{"headSha": "a"}, {"headSha": "b"}]'))


def test_the_audit_ties_a_ci_run_to_the_audited_revision(tmp_path):
    from assertiva.audit import run_audit
    from conftest import git

    root = tmp_path / "p"
    write(root / "app.py", "X = 1\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "x")
    head = git(root, "rev-parse", "HEAD").strip()
    same = write(tmp_path / "same.json", json.dumps({**GH_RUN, "headSha": head}))
    other = write(tmp_path / "other.json", json.dumps(GH_RUN))
    report = run_audit(root, ci_runs=[same, other])
    assert [r["identity"] for r in report["ci_runs"]] == ["SAME_REVISION", "OTHER_REVISION"]
    assert report["ci_runs"][0]["provenance"] == "EXTERNAL_VERIFIED"
    codes = {f["code"]: f for f in report["findings"]}
    assert codes["CI_RUN_NOT_GREEN"]["evidence"]["failed_jobs"] == ["tests"]
    assert "CI_RUN_FOR_ANOTHER_REVISION" in codes


def test_the_page_never_shows_ingested_coverage_as_measured_and_shows_observed_ci(tmp_path):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    write(tmp_path / "p" / "app.py", "X = 1\n")
    report = run_audit(tmp_path / "p", coverage_reports=[write(tmp_path / "coverage.json", json.dumps(COVERAGE_PY))],
                       ci_runs=[write(tmp_path / "run.json", json.dumps(GH_RUN))])
    page = render_html(report)
    assert "Ingested" in page and "71.4% of product lines (test code excluded)" in page
    assert "CI runs observed at the provider" in page and "Revision correspondence unknown" in page  # no Git here
    assert "Execuções de CI observadas no provedor" in render_html(report, lang="pt-BR")
