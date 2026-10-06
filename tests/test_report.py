"""Assurance Report: one model, honest states, accessible self-contained HTML."""

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

from assertiva.evidence import NegativeControl
from assertiva.improve import apply_approved, discard_session, qualify_candidate, start_improve
from assertiva.audit import run_audit as audit_report
from assertiva.report import improve_report, render_html
from assertiva.workspace import Approval

from conftest import write

SCHEMA = json.loads((Path(__file__).parents[1] / "schemas" / "assurance-report.schema.json").read_text(encoding="utf-8"))
STRONG_TEST = "from calc import add\n\ndef test_add_distinguishes_operands():\n    assert add(2, 3) == 5\n"


class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.attrs, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def parse(html):
    parser = Structure()
    parser.feed(html)
    return parser


@pytest.fixture
def improve_states(calc_project):
    session = start_improve(calc_project, python=sys.executable)
    write(session.workspace / "tests" / "test_strong.py", STRONG_TEST)
    control = NegativeControl("add-multiply", "calc.py", "return a + b", "return a * b", "add() returns the sum")
    result = qualify_candidate(session, negative_controls=[control])
    yield session, result
    discard_session(session)


def assert_schema_shape(report):
    for key in SCHEMA["required"]:
        assert key in report
    assert set(report["states"]) <= set(SCHEMA["properties"]["states"]["properties"])
    for key in SCHEMA["properties"]["claim_boundary"]["required"]:
        assert isinstance(report["claim_boundary"][key], list)


@pytest.mark.integration
def test_improve_report_shows_baseline_vs_candidate_never_applied(improve_states):
    session, result = improve_states
    report = improve_report(session, result)
    assert_schema_shape(report)
    assert report["states"]["applied"] is None
    assert report["states"]["candidate"]["observed_in"] == "isolated-candidate-copy"
    html = render_html(report)
    assert "Not applied" in html
    assert re.search(r'<th scope="col">Candidate\b', html)
    assert not re.search(r'<th scope="col">Applied\b', html)


@pytest.mark.integration
def test_applied_column_appears_only_after_approved_application(improve_states):
    session, result = improve_states
    applied = apply_approved(session, result, Approval(frozenset({"tests/test_strong.py"}), "reviewer"))
    report = improve_report(session, result, applied)
    assert report["states"]["applied"]["observed_in"] == "applied-project-copy"
    assert re.search(r'<th scope="col">Applied\b', render_html(report))


@pytest.mark.integration
def test_report_bounds_what_green_proves(improve_states):
    session, result = improve_states
    boundary = improve_report(session, result)["claim_boundary"]
    assert any("PREVIEW_DEPLOY" in item for item in boundary["not_evidenced"])
    assert any("ORIGINAL_REGRESSION" in item for item in boundary["observed"])
    assert any("not applied" in item.lower() for item in boundary["limitations"])


@pytest.mark.integration
def test_evidence_delta_buckets_use_metric_semantics(improve_states):
    session, result = improve_states
    delta = improve_report(session, result)["evidence_delta"]
    assert "negative_controls_survived" in {d["name"] for d in delta["improved"]}
    assert "test_invocations" in {d["name"] for d in delta["changed"]}
    assert not any(d["name"] == "test_invocations" for d in delta["improved"])


@pytest.mark.integration
def test_change_set_carries_reviewable_diff(improve_states):
    session, result = improve_states
    [change] = improve_report(session, result)["change_set"]["changes"]
    assert change["kind"] == "ADD"
    assert "+    assert add(2, 3) == 5" in change["diff"]


@pytest.mark.integration
def test_html_is_self_contained_semantic_and_accessible(improve_states):
    session, result = improve_states
    html = render_html(improve_report(session, result))
    doc = parse(html)
    assert re.search(r'<html lang="[a-z]{2}', html)
    for landmark in ("header", "nav", "main", "footer"):
        assert landmark in doc.tags
    assert doc.tags.count("h1") == 1
    assert not re.search(r'(src|href)="(https?:)?//', html), "report must work offline"
    for tag, attrs in doc.attrs:
        if tag == "th":
            assert attrs.get("scope") in {"col", "row"}
        if tag == "svg":
            assert attrs.get("role") == "img" and attrs.get("aria-labelledby")
        if tag in {"input", "select", "button"}:
            assert attrs.get("aria-label") or attrs.get("id")
    assert doc.tags.count("table") == html.count("<caption")
    assert "prefers-color-scheme: dark" in html
    assert "What does green prove?" in html
    assert "<details" in html


def test_charts_have_table_equivalents_and_no_invented_data(tmp_path):
    write(tmp_path / "README.md", "nothing executable\n")
    report = audit_report(tmp_path)
    html = render_html(report)
    assert "<svg" not in html  # no measured metric pairs -> no chart
    assert report["status"] == "UNKNOWN"


@pytest.mark.integration
def test_audit_report_has_current_findings_recommendations_unknowns(calc_project):
    report = audit_report(calc_project, execute=True, python=sys.executable)
    assert_schema_shape(report)
    assert report["workflow"] == "audit"
    assert set(k for k, v in report["states"].items() if v) == {"current"}
    assert any(f["code"] == "WEAK_ORACLE_SIGNAL" for f in report["findings"])
    assert report["recommendations"]
    assert any("NO_DELIVERY_PIPELINE_OBSERVED" == f["code"] for f in report["findings"])
    assert report["states"]["current"]["metrics"]["test_invocations"]["value"] == 2
