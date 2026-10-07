"""The auditing agent's assessment joins the engine's report for the same run without erasing engine evidence.

The engine stays the only renderer: `assertiva audit --assessment FILE` validates the agent's dispositions and findings
against the latest audit of the project and re-renders that run's canonical page. These tests pin the invariants:
the right run, an unchanged project, raw engine evidence preserved, no whole-finding verdict from a partial review,
grounded agent findings, and priorities that follow the disposition."""

import copy
import json
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.assessment import AssessmentError, apply_assessment
from assertiva.workspace import tree_fingerprint
from conftest import write


def _audit(project: Path, capsys) -> dict:
    assert cli.main(["audit", str(project), "--python", sys.executable, "--output", "json"]) == 0
    return json.loads(capsys.readouterr().out)


@pytest.fixture
def two_weak(calc_project):
    write(calc_project / "tests" / "test_more.py",
          "from calc import add\n\ndef test_add_is_callable():\n    assert add(0, 0) is not None\n")
    return calc_project


def _weak(report: dict) -> dict:
    return next(f for f in report["findings"] if f["code"] == "WEAK_ORACLE_SIGNAL")


def _assess(report: dict, **overrides) -> dict:
    base = {"run_id": report["run_id"], "summary": "Two tests check existence only.", "dispositions": [], "findings": []}
    base.update(overrides)
    return base


# --- the report model carries what an assessment needs -------------------------------------------

def test_every_audit_run_and_engine_finding_has_a_stable_reference(two_weak, capsys):
    report = _audit(two_weak, capsys)
    assert report["run_id"] and report["project"]["digest"]
    ids = [f["id"] for f in report["findings"]]
    assert len(ids) == len(set(ids)) and "WEAK_ORACLE_SIGNAL" in ids
    assert all(f["origin"] == "engine" and f["priority"] == f["severity"] for f in report["findings"])


# --- dispositions ---------------------------------------------------------------------------------

def test_contextual_disposition_keeps_the_engine_fact_and_restates_priority(two_weak, capsys):
    report = _audit(two_weak, capsys)
    raw = copy.deepcopy(_weak(report))
    out = apply_assessment(report, _assess(report, dispositions=[{
        "finding": "WEAK_ORACLE_SIGNAL", "disposition": "CONTEXTUAL", "priority": "low",
        "rationale": "Both are smoke checks of a trivial wrapper.", "evidence": ["tests/test_calc.py:3"],
        "scope": {"reviewed": 2, "of": 2}}]))
    weak = _weak(out)
    assert weak["severity"] == raw["severity"] and weak["evidence"] == raw["evidence"] and weak["summary"] == raw["summary"]
    assert weak["priority"] == "low" and weak["assessment"]["disposition"] == "CONTEXTUAL"
    assert _weak(report) == raw, "the input report is not mutated"


def test_false_positive_leaves_the_action_plan_but_not_the_report(two_weak, capsys):
    report = _audit(two_weak, capsys)
    out = apply_assessment(report, _assess(report, dispositions=[{
        "finding": "WEAK_ORACLE_SIGNAL", "disposition": "FALSE_POSITIVE",
        "rationale": "x", "evidence": ["tests/helpers.py:1"], "scope": {"reviewed": 2, "of": 2}}]))
    weak = _weak(out)
    assert weak["priority"] == "none" and weak["evidence"] == _weak(report)["evidence"]
    rec = next(r for r in out["recommendations"] if r["finding_id"] == "WEAK_ORACLE_SIGNAL")
    assert rec["status"] == "WITHDRAWN"


def test_a_whole_finding_verdict_needs_every_item_reviewed(two_weak, capsys):
    report = _audit(two_weak, capsys)
    for disposition in ("FALSE_POSITIVE", "CONFIRMED"):
        with pytest.raises(AssessmentError, match="every item"):
            apply_assessment(report, _assess(report, dispositions=[{
                "finding": "WEAK_ORACLE_SIGNAL", "disposition": disposition, "rationale": "x", "evidence": ["e"]}]))
        with pytest.raises(AssessmentError, match="reviewed 1 of 2"):
            apply_assessment(report, _assess(report, dispositions=[{
                "finding": "WEAK_ORACLE_SIGNAL", "disposition": disposition, "rationale": "x", "evidence": ["e"],
                "scope": {"reviewed": 1, "of": 2}}]))
    with pytest.raises(AssessmentError, match="has 2 items"):
        apply_assessment(report, _assess(report, dispositions=[{
            "finding": "WEAK_ORACLE_SIGNAL", "disposition": "UNRESOLVED", "rationale": "x", "evidence": ["e"],
            "scope": {"reviewed": 1, "of": 19}}]))
    out = apply_assessment(report, _assess(report, dispositions=[{
        "finding": "WEAK_ORACLE_SIGNAL", "disposition": "PARTIAL", "rationale": "x", "evidence": ["e"],
        "scope": {"reviewed": 1, "of": 2},
        "subjects": [{"subject": "tests/test_calc.py::test_add_runs", "disposition": "CONFIRMED", "note": "is not None"}]}]))
    assert _weak(out)["assessment"]["scope"] == {"reviewed": 1, "of": 2}


@pytest.mark.parametrize("bad, message", [
    ({"finding": "NOPE", "disposition": "CONFIRMED", "rationale": "x", "evidence": ["e"]}, "no finding"),
    ({"finding": "WEAK_ORACLE_SIGNAL", "disposition": "MAYBE", "rationale": "x", "evidence": ["e"]}, "disposition"),
    ({"finding": "WEAK_ORACLE_SIGNAL", "disposition": "UNRESOLVED", "rationale": "x", "evidence": []}, "evidence"),
    ({"finding": "WEAK_ORACLE_SIGNAL", "disposition": "UNRESOLVED", "rationale": "", "evidence": ["e"]}, "rationale"),
    ({"finding": "WEAK_ORACLE_SIGNAL", "disposition": "CONTEXTUAL", "rationale": "x", "evidence": ["e"]}, "priority"),
    ({"finding": "WEAK_ORACLE_SIGNAL", "disposition": "PARTIAL", "rationale": "x", "evidence": ["e"]}, "subjects"),
    ({"finding": "WEAK_ORACLE_SIGNAL", "disposition": "FALSE_POSITIVE", "priority": "low", "rationale": "x", "evidence": ["e"],
      "scope": {"reviewed": 2, "of": 2}}, "priority"),
    ({"finding": "WEAK_ORACLE_SIGNAL", "disposition": "UNRESOLVED", "priority": "urgent", "rationale": "x", "evidence": ["e"]}, "priority"),
])
def test_malformed_dispositions_are_refused_with_the_reason(two_weak, capsys, bad, message):
    report = _audit(two_weak, capsys)
    with pytest.raises(AssessmentError, match=message):
        apply_assessment(report, _assess(report, dispositions=[bad]))


def test_a_finding_is_dispositioned_once(two_weak, capsys):
    report = _audit(two_weak, capsys)
    one = {"finding": "WEAK_ORACLE_SIGNAL", "disposition": "UNRESOLVED", "rationale": "x", "evidence": ["e"]}
    with pytest.raises(AssessmentError, match="more than once"):
        apply_assessment(report, _assess(report, dispositions=[one, one]))


# --- the agent's own findings ---------------------------------------------------------------------

def test_agent_findings_are_first_class_grounded_and_labelled(two_weak, capsys):
    report = _audit(two_weak, capsys)
    finding = {"id": "boundary-mocked", "title": "The adapter is mocked in every test", "claim": "No test crosses the adapter.",
               "why": "A broken adapter stays green.", "priority": "high", "basis": "INFERRED",
               "evidence": ["tests/test_calc.py:1"], "recommendation": "Add one test through the real adapter."}
    out = apply_assessment(report, _assess(report, findings=[finding]))
    agent = next(f for f in out["findings"] if f["origin"] == "agent")
    assert agent["id"] == "agent:boundary-mocked" and agent["priority"] == "high" and agent["basis"] == "INFERRED"
    assert agent["evidence"]["refs"] == ["tests/test_calc.py:1"]
    assert {"finding_id": "agent:boundary-mocked", "status": "PROPOSED"}.items() <= next(
        r for r in out["recommendations"] if r.get("finding_id") == "agent:boundary-mocked").items()
    for missing in ("evidence", "claim", "priority", "basis", "title"):
        broken = {k: v for k, v in finding.items() if k != missing} | ({"evidence": []} if missing == "evidence" else {})
        with pytest.raises(AssessmentError):
            apply_assessment(report, _assess(report, findings=[broken]))
    with pytest.raises(AssessmentError, match="basis"):
        apply_assessment(report, _assess(report, findings=[finding | {"basis": "E4"}]))
    with pytest.raises(AssessmentError, match="more than once"):
        apply_assessment(report, _assess(report, findings=[finding, finding]))


def test_a_new_assessment_replaces_the_previous_one(two_weak, capsys):
    report = _audit(two_weak, capsys)
    first = apply_assessment(report, _assess(report, findings=[{
        "id": "a", "title": "t", "claim": "c", "priority": "high", "basis": "INFERRED", "evidence": ["e"]}],
        dispositions=[{"finding": "WEAK_ORACLE_SIGNAL", "disposition": "CONTEXTUAL", "priority": "info",
                       "rationale": "x", "evidence": ["e"], "scope": {"reviewed": 2, "of": 2}}]))
    second = apply_assessment(first, _assess(first, summary="Revised."))
    assert [f for f in second["findings"] if f["origin"] == "agent"] == []
    assert "assessment" not in _weak(second) and _weak(second)["priority"] == _weak(second)["severity"]
    assert second["findings"] == report["findings"] and second["recommendations"] == report["recommendations"]
    assert second["assessment"]["summary"] == "Revised."


def test_the_summary_is_required_and_the_run_must_match(two_weak, capsys):
    report = _audit(two_weak, capsys)
    with pytest.raises(AssessmentError, match="summary"):
        apply_assessment(report, _assess(report, summary=" "))
    with pytest.raises(AssessmentError, match="another run"):
        apply_assessment(report, _assess(report, run_id="0" * 16))


# --- the CLI: same run, same page, project untouched, stale refused -------------------------------

def _write_assessment(tmp_path: Path, data: dict) -> str:
    path = tmp_path / "assessment.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_cli_attaches_the_assessment_to_the_same_canonical_page(two_weak, tmp_path, capsys):
    report = _audit(two_weak, capsys)
    page = Path(report["report_path"])
    before = tree_fingerprint(two_weak)
    path = _write_assessment(tmp_path, _assess(report, dispositions=[{
        "finding": "WEAK_ORACLE_SIGNAL", "disposition": "CONFIRMED", "rationale": "Both assert only `is not None`.",
        "evidence": ["tests/test_calc.py:3", "tests/test_more.py:3"], "scope": {"reviewed": 2, "of": 2}}]))
    assert cli.main(["audit", str(two_weak), "--assessment", path, "--output", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["report_path"] == str(page) and sorted(p.name for p in page.parent.iterdir()) == ["audit.html", "audit.json"]
    stored = json.loads((page.parent / "audit.json").read_text(encoding="utf-8"))
    assert stored["run_id"] == report["run_id"] and _weak(stored)["assessment"]["disposition"] == "CONFIRMED"
    assert "Both assert only" in page.read_text(encoding="utf-8")
    assert tree_fingerprint(two_weak) == before


def test_cli_refuses_an_assessment_for_a_project_that_changed_since_the_run(two_weak, tmp_path, capsys):
    report = _audit(two_weak, capsys)
    write(two_weak / "calc.py", "def add(a, b):\n    return a - b\n")
    path = _write_assessment(tmp_path, _assess(report))
    assert cli.main(["audit", str(two_weak), "--assessment", path]) == 2
    assert "changed since" in capsys.readouterr().err


def test_cli_refuses_without_a_prior_audit_and_with_measurement_options(two_weak, tmp_path, capsys):
    path = _write_assessment(tmp_path, {"run_id": "x", "summary": "s"})
    assert cli.main(["audit", str(two_weak), "--assessment", path]) == 2
    assert "run `assertiva audit` first" in capsys.readouterr().err
    assert cli.main(["audit", str(two_weak), "--assessment", path, "--execute"]) == 2
    assert "--assessment" in capsys.readouterr().err


# --- the rendered page tells one story --------------------------------------------------------------

import html as html_lib  # noqa: E402
import re  # noqa: E402

from assertiva.report import render_html  # noqa: E402


def _rail(page: str) -> str:
    start = page.index('<aside class="rail"')
    return page[start:page.index("</aside>", start)]


def _card(page: str, finding_id: str) -> str:
    start = page.index(f'data-finding-id="{finding_id}"')
    start = page.rindex('<details class="finding', 0, start)
    end = page.find('<details class="finding', start + 10)
    return page[start:end if end > 0 else page.index("</section>", start)]


_BOUNDARY = {"id": "boundary-mocked", "title": "The adapter is mocked in every test", "claim": "No test crosses the adapter.",
             "why": "A broken adapter stays green.", "priority": "high", "basis": "INFERRED",
             "evidence": ["tests/test_calc.py:1"], "recommendation": "Add one test through the real adapter."}


def test_next_step_follows_the_assessment_not_the_engine_default(two_weak, capsys):
    report = _audit(two_weak, capsys)
    assert "WEAK_ORACLE_SIGNAL" in _rail(render_html(report)) or 'href="#finding-' in _rail(render_html(report))
    out = apply_assessment(report, _assess(report, findings=[_BOUNDARY], dispositions=[{
        "finding": "WEAK_ORACLE_SIGNAL", "disposition": "FALSE_POSITIVE", "rationale": "Both delegate to a strict helper.",
        "evidence": ["tests/helpers.py:3"], "scope": {"reviewed": 2, "of": 2}}]))
    page = render_html(out)
    rail = html_lib.unescape(_rail(page))
    assert "Add one test through the real adapter." in rail and "The adapter is mocked in every test" in rail
    improvements = page[page.index('id="improvements"'):page.index('<section id="evidence"')]
    assert "Add one test through the real adapter." in html_lib.unescape(improvements)
    assert 'id="rec-WEAK_ORACLE_SIGNAL"' not in improvements  # withdrawn: no longer an action


def test_a_dispositioned_card_shows_observation_assessment_and_raw_evidence(two_weak, capsys):
    report = _audit(two_weak, capsys)
    out = apply_assessment(report, _assess(report, dispositions=[{
        "finding": "WEAK_ORACLE_SIGNAL", "disposition": "CONTEXTUAL", "priority": "info",
        "rationale": "Smoke checks of a one-line wrapper; behavior is asserted elsewhere.",
        "evidence": ["tests/test_calc.py:6"], "scope": {"reviewed": 2, "of": 2}}]))
    card = _card(render_html(out), "WEAK_ORACLE_SIGNAL")
    text = html_lib.unescape(card)
    assert 'data-i18n="disp.CONTEXTUAL"' in card and 'data-i18n="severity.info"' in card
    assert 'data-i18n="assess.engine_said"' in card and 'data-i18n="severity.medium"' in card  # the engine default stays visible
    assert "Smoke checks of a one-line wrapper" in text and "tests/test_calc.py:6" in text
    assert "Reviewed 2 of 2 items" in text
    raw = re.search(r'<details class="tech">.*?<pre class="code">(.*?)</pre>', card, re.S).group(1)
    assert json.loads(html_lib.unescape(raw)) == _weak(report)["evidence"]


def test_agent_findings_render_as_findings_with_their_basis(two_weak, capsys):
    report = _audit(two_weak, capsys)
    page = render_html(apply_assessment(report, _assess(report, findings=[_BOUNDARY], lang="en")))
    card = _card(page, "agent:boundary-mocked")
    text = html_lib.unescape(card)
    assert "The adapter is mocked in every test" in text and "A broken adapter stays green." in text
    assert 'data-i18n="basis.INFERRED"' in card and 'data-i18n="assess.by_agent"' in card
    assert "tests/test_calc.py:1" in text and 'data-severity="high"' in card


def test_the_auditors_conclusion_leads_and_unknowns_are_listed(two_weak, capsys):
    report = _audit(two_weak, capsys)
    out = apply_assessment(report, _assess(report, summary="A suíte cobre o caminho feliz; nada prova a integração.",
                                           lang="pt-BR", unknowns=["Se o CI rodou nesta revisão."]))
    page = render_html(out)
    decision = page[page.index('class="decision'):page.index('id="green"')]
    assert 'lang="pt-BR"' in decision and "nada prova a integração" in html_lib.unescape(decision)
    assert "Se o CI rodou nesta revisão." in html_lib.unescape(page[page.index('class="fact d-unk"'):])
    assert render_html(out, lang="pt-BR")  # both languages render


def test_counts_and_verdict_use_effective_priority(two_weak, capsys):
    report = _audit(two_weak, capsys)
    out = apply_assessment(report, _assess(report, dispositions=[{
        "finding": "WEAK_ORACLE_SIGNAL", "disposition": "FALSE_POSITIVE", "rationale": "x", "evidence": ["e"],
        "scope": {"reviewed": 2, "of": 2}}]))
    page = render_html(out)
    attention = page[page.index('class="fact d-att"'):page.index('class="fact d-unk"')]
    assert "Weak behavioral oracles" not in html_lib.unescape(attention)
    assert "1 engine finding was reviewed and set aside" in html_lib.unescape(page)


def test_reports_written_before_assessments_still_render(calc_project):
    from assertiva.audit import run_audit

    old = run_audit(calc_project)
    old.pop("run_id")
    for f in old["findings"]:
        for key in ("id", "origin", "priority"):
            f.pop(key)
    for rec in old["recommendations"]:
        rec.pop("finding_id")
    assert 'href="#finding-' in _rail(render_html(old))
