"""Automated accessibility results. The fixtures are real axe-core 4.10.3 runs in headless Chromium on the two pages
beside them (tests/fixtures/accessibility/run-axe.js): a checkout form with violations and a contrast item axe could
not decide, and a receipt page with none."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters.accessibility import findings, load_accessibility

FIXTURES = Path(__file__).parent / "fixtures" / "accessibility"


def test_violations_and_undecided_items_are_kept_apart():
    [page] = load_accessibility(FIXTURES / "axe-checkout.json")["pages"]
    assert page["engine"] == "axe-core" and page["engine_version"] == "4.10.3" and page["browser"].startswith("HeadlessChrome/")
    assert {v["rule"]: v["impact"] for v in page["violations"]} == {
        "button-name": "critical", "color-contrast": "serious", "image-alt": "critical", "label": "critical"}
    assert [v["rule"] for v in page["needs_review"]] == ["color-contrast"]  # over a gradient: undecided, not passed
    codes = [(f.code, f.severity) for f in findings({"pages": [page]})]
    assert ("ACCESSIBILITY_VIOLATION", "high") in codes and ("ACCESSIBILITY_NEEDS_REVIEW", "low") in codes


def test_a_page_without_violations_is_not_called_accessible():
    report = load_accessibility(FIXTURES / "axe-receipt.json")
    [page] = report["pages"]
    assert page["violations"] == [] and page["passed_rules"] > 0 and findings(report) == []
    assert "not proof of accessibility" in report["claim"]


def test_cli_lists_and_unreadable_files_are_handled(tmp_path):
    many = [json.loads((FIXTURES / name).read_text(encoding="utf-8")) for name in ("axe-checkout.json", "axe-receipt.json")]
    (tmp_path / "cli.json").write_text(json.dumps(many), encoding="utf-8")  # @axe-core/cli writes a list of results
    assert len(load_accessibility(tmp_path / "cli.json")["pages"]) == 2
    (tmp_path / "other.json").write_text('{"tests": []}', encoding="utf-8")
    assert "not axe-core results" in load_accessibility(tmp_path / "other.json")["error"]


@pytest.mark.integration
def test_audit_reports_accessibility_with_its_claim_boundary(calc_project, tmp_path, capsys):
    capsys.readouterr()
    cli.main(["audit", str(calc_project), "--report-dir", str(tmp_path / "r"), "--python", sys.executable, "--output", "json",
              "--accessibility-report", str(FIXTURES / "axe-checkout.json"), "--accessibility-report", str(FIXTURES / "axe-receipt.json")])
    report = json.loads(capsys.readouterr().out)
    assert [len(r["pages"]) for r in report["accessibility"]] == [1, 1]
    assert sum(f["code"] == "ACCESSIBILITY_VIOLATION" for f in report["findings"]) == 4
    page = (tmp_path / "r" / "audit.html").read_text(encoding="utf-8")
    assert 'id="accessibility"' in page and "No violation is not proof of accessibility" in page
