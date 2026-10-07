"""Contract of the HTML Assurance Report as a product surface: two layers (decision, auditability), honesty,
accessibility, i18n, offline. These tests parse the rendered page; they do not test pixels or styling."""

import ast
import copy
import html as html_lib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

import assertiva
from assertiva.audit import run_audit
from assertiva.report import _RECOMMENDATION, render_html
from assertiva.report_html import narrate
from assertiva.report_i18n import ACTIONS, FINDINGS, METRICS, UI
from assertiva.report_narrative import NARRATIVE

from conftest import write

# The package these tests exercise: the one actually imported (a source checkout or an installed wheel), never a
# path derived from the repository layout. Under wheel qualification the source package does not exist beside the tests.
PACKAGE = Path(assertiva.__file__).resolve().parent
LONG_COMMAND = "pytest " + " ".join(f"--option-{i}=/a/very/long/path/segment/{i}" for i in range(60))
VOID = {"br", "img", "input", "meta", "col", "use", "path", "rect", "circle", "link"}


class Page(HTMLParser):
    """Light element tree: tags with attributes, text per id, heading levels, and text by layer."""

    def __init__(self):
        super().__init__()
        self.elements, self.headings, self.stack = [], [], []
        self.texts: dict[str, list[str]] = {}
        self.decision_text: list[str] = []
        self.decision_english: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag not in VOID:
            self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        if tag not in VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        for _, attrs in self.stack:
            if attrs.get("id"):
                self.texts.setdefault(attrs["id"], []).append(data)
        in_decision = any(a.get("data-layer") == "decision" for _, a in self.stack)
        technical = any(t in ("code", "pre") or {"original", "tech", "raw-json", "tier-code"} & set((a.get("class") or "").split()) for t, a in self.stack)
        if in_decision and not technical and data.strip():
            self.decision_text.append(data)
            if any(a.get("lang") == "en" for _, a in self.stack):
                self.decision_english.append(data.strip())

    def text(self, element_id):
        return " ".join("".join(self.texts.get(element_id, [])).split())

    def all(self, tag=None, **attrs):
        return [a for t, a in self.elements if (tag is None or t == tag) and all(a.get(k) == v for k, v in attrs.items())]

    def with_class(self, cls):
        return [a for _, a in self.elements if cls in (a.get("class") or "").split()]


def parse(page_html):
    page = Page()
    page.feed(page_html)
    return page


def dictionary(page_html):
    raw = re.search(r'<script type="application/json" id="i18n">(.*?)</script>', page_html, re.S).group(1)
    return json.loads(raw.replace("<\\/", "</"))["pt-BR"]


def section(page_html, marker, end="</section>"):
    start = page_html.index(marker)
    return page_html[start:page_html.index(end, start)]


@pytest.fixture
def report(calc_project):
    write(calc_project / ".github" / "workflows" / "ci.yml", f"on: push\njobs:\n  test:\n    steps:\n      - run: {LONG_COMMAND}\n      - run: ruff check .\n")
    data = run_audit(calc_project)
    data["findings"].append({
        "code": "CI_TEST_EXECUTION_GAP", "severity": "high",
        "summary": "Some discovered test files are outside the test scopes observed in CI configuration.",
        "evidence": {"unobserved_test_files": [f"tests/deep/module_{i}/test_{i}.py" for i in range(300)]}, "recommendation": None,
    })
    data["recommendations"].append({"finding": "CI_TEST_EXECUTION_GAP", "recommendation": _RECOMMENDATION["CI_TEST_EXECUTION_GAP"], "status": "PROPOSED"})
    return data


def _metric(value, direction="CONTEXTUAL", unit=None, tier="E1"):
    return {"value": value, "direction": direction, "unit": unit, "evidence_tier": tier}


def _state(label, invocations, line):
    return {
        "label": label, "observed_in": f"isolated-{label}-copy",
        "metrics": {"test_invocations": _metric(invocations), "passed": _metric(invocations),
                    "line_coverage": _metric(line, "HIGHER_IS_BETTER", "%"), "weak_oracle_tests": _metric(1, "LOWER_IS_BETTER", tier="E3")},
        "runs": [{"adapter": "fake-runner", "mode": "native", "status": "PASS", "command": ["run"], "exit_code": 0, "invocations": invocations,
                  "collection_errors": [], "limitations": [], "matrix": {}, "attachments": 0}],
        "negative_controls": [], "mutation": [], "artifacts": [], "negative_paths": {}, "coverage": [], "limitations": [],
    }


def improve_model(pipeline="FAIL", regressed=False, unchanged=19):
    checks = [
        {"check": "ORIGINAL_REGRESSION", "status": "PASS", "summary": "all 5 originally passing invocations still pass", "limitations": []},
        {"check": "NEGATIVE_PATHS", "status": "UNKNOWN", "summary": "the candidate does not add or modify negative-path tests", "limitations": []},
        {"check": "PIPELINE_EQUIVALENT", "status": pipeline,
         "summary": "reproduced 4/5 delivery checks locally; a reproduced gating check failed" if pipeline == "FAIL" else "reproduced 5/5 delivery checks locally; all gating checks passed",
         "limitations": ["an adapter-specific note with no template"]},
    ]
    delta = {
        "improved": [{"name": "line_covered", "baseline": 55, "candidate": 60, "state": "IMPROVED", "unit": None, "note": None}],
        "unchanged": [{"name": f"metric_{i}", "baseline": 1, "candidate": 1, "state": "UNCHANGED", "unit": None, "note": None} for i in range(unchanged)],
        "regressed": [{"name": "line_coverage", "baseline": 90.0, "candidate": 80.0, "state": "REGRESSED", "unit": "%", "note": None}] if regressed else [],
        "changed": [{"name": "test_invocations", "baseline": 5, "candidate": 7, "state": "CHANGED", "unit": None, "note": None}],
        "unknown": [],
    }
    ready = pipeline not in ("FAIL", "BLOCKED")
    return {
        "report_version": "1", "workflow": "improve", "status": "READY_FOR_REVIEW" if ready else "NEEDS_ATTENTION",
        "project": {"name": "shop", "root": "/tmp/shop", "revision": "e5cc0b9abbecb9593de02c44e5121c11901fcea6", "dirty": False, "baseline_digest": "abc"},
        "generated_at": "2026-10-07T12:00:00+00:00",
        "states": {"current": None, "baseline": _state("baseline", 5, 88.7), "candidate": _state("candidate", 7, 89.5), "applied": None},
        "findings": [], "recommendations": [], "verification_surface": [], "evidence_delta": delta, "applied_delta": None,
        "change_set": {"changes": [{"change_id": "tests/test_new.py", "path": "tests/test_new.py", "kind": "ADD", "reason": "added in candidate",
                                    "original_fingerprint": None, "candidate_fingerprint": "f" * 64, "diff": "+def test_x():\n+    assert 1\n"}],
                       "approval_required": True, "applied": []},
        "candidate_qualification": {"ready_for_review": ready, "stages": [
            {"stage": "BEHAVIORAL_ASSURANCE", "status": "UNKNOWN", "checks": checks[:2]},
            {"stage": "DELIVERY_FIDELITY", "status": pipeline, "checks": checks[2:]},
        ], "baseline_negative_controls": [], "stability": {"records": []}, "timings": []},
        "claim_boundary": {"observed": [f"{c['check']}: {c['summary']}" for c in checks if c["status"] == "PASS"],
                           "not_evidenced": [f"{c['check']} ({c['status']}): {c['summary']}" for c in checks if c["status"] != "PASS"]
                           + ["preview/deployment behavior: no authorized non-production preview adapter; production is never used to qualify tests"],
                           "limitations": ["Candidate evidence was observed in an isolated copy; the candidate is not applied to the project."]},
        "remaining_unknowns": [], "provenance": {"assertiva_version": "0.5.5", "interpreter": "python", "read_only_until_approval": True},
    }


# --- structure and accessibility ---------------------------------------------------------

@pytest.mark.parametrize("lang", ["en", "pt-BR"])
def test_landmarks_one_h1_no_skipped_heading_levels(report, lang):
    page = parse(render_html(report, lang=lang))
    tags = [t for t, _ in page.elements]
    for landmark in ("header", "nav", "main", "footer"):
        assert landmark in tags
    assert page.all("a", **{"class": "skip", "href": "#main"})
    assert page.headings.count(1) == 1 and page.headings[0] == 1
    assert all(b - a <= 1 for a, b in zip(page.headings, page.headings[1:])), page.headings


@pytest.mark.parametrize("make", ["audit", "improve"])
def test_two_layers_decision_first_then_audit_detail(report, make):
    data = report if make == "audit" else improve_model()
    page = parse(render_html(data))
    areas = [a["id"] for a in page.with_class("area")]
    expected = ["findings", "improvements"] if make == "audit" else ["candidate", "delta"]
    assert areas == ["overview", *expected, "evidence", "details"]
    nav = [a["data-area"] for a in page.all("li") if a.get("data-area")]
    assert nav == areas  # five top-level entries, one per area
    [overview] = [a for a in page.with_class("area") if a["id"] == "overview"]
    assert overview.get("data-layer") == "decision"
    assert page.with_class("decision") and page.all("aside", **{"class": "rail"})
    assert [c["class"].split()[1] for c in page.with_class("fact")] == ["d-conf", "d-att", "d-unk"]
    assert page.all(id="green") and page.with_class("ledger")
    assert not [a for a in page.with_class("area") if a["id"] == "details" and a.get("data-layer")]  # technical layer is not decision


def test_overall_status_is_explained_never_shown_as_raw_enum_or_success(report):
    page_html = render_html(report)
    verdict = section(page_html, 'class="d-main"', "</div>")
    assert report["status"] not in re.sub(r"<[^>]+>", "", verdict)  # the enum is a technical detail
    assert "tone-pass" not in verdict
    assert '<span class="chip sev-high"><b>1</b>' in verdict  # the reason: how many findings of which priority
    compact = section(page_html, '<dl class="prov">', "</dl>")
    assert report["status"] not in re.sub(r"<[^>]+>", "", compact)  # compact pairs stay human
    assert f"<code>{report['status']}</code>" in page_html  # the raw status is kept in the full provenance


def test_improve_answers_readiness_and_blockers_first():
    not_ready = render_html(improve_model(pipeline="FAIL"), lang="pt-BR")
    verdict = html_lib.unescape(section(not_ready, 'class="d-main"', '<div class="life">'))
    assert "Candidato ainda não está pronto" in verdict and "verificações equivalentes ao pipeline (falhou)" in verdict
    nxt = section(not_ready, '<aside class="rail"', "</aside>")
    assert 'href="#check-PIPELINE_EQUIVALENT"' in nxt and 'data-i18n="next.unblock"' in nxt
    assert 'data-i18n="story.not_applied"' in not_ready  # candidate is never presented as applied
    ready = render_html(improve_model(pipeline="PASS"))
    assert "Candidate ready for review" in section(ready, 'class="d-main"', '<div class="life">')
    assert "--approve" in section(ready, '<aside class="rail"', "</aside>")  # review, never automatic apply


def test_audit_scope_separates_executed_measured_inspected_declared_not_proven(report):
    page = parse(render_html(report))
    rows = {a["id"]: a["class"] for a in page.with_class("lrow")}
    level = lambda area: re.search(r"lvl-(\w+)", rows[f"scope-{area}"]).group(1)
    assert level("tests") == "inspected"  # static audit: inventory only, nothing executed
    assert level("ci") == "declared"  # configuration is never run evidence
    assert level("deploy") == "not_evidenced" and level("fault") == "not_evidenced"
    assert all(level(a) != "executed" for a in ("tests", "ci", "coverage"))


@pytest.mark.integration
def test_audit_scope_shows_execution_only_when_tests_ran(calc_project):
    import sys

    page = parse(render_html(run_audit(calc_project, execute=True, python=sys.executable)))
    rows = {a["id"]: a["class"] for a in page.with_class("lrow")}
    assert "lvl-executed" in rows["scope-tests"] and "lvl-measured" in rows["scope-coverage"]


def test_heuristic_signals_are_never_counted_as_confirmed(calc_project):
    data = run_audit(calc_project)
    data["states"]["current"]["metrics"]["negative_paths_with_state_after_rejection"] = _metric(12, "HIGHER_IS_BETTER", tier="E3")
    page_html = render_html(data)
    confirmed = section(page_html, 'class="fact d-conf"')
    assert 'data-i18n="conf.none"' in confirmed  # nothing executed: nothing confirmed
    assert 'class="signal"' in confirmed and "E3" in confirmed  # the E3 signal is shown apart, labelled as heuristic


def test_absence_of_findings_is_not_presented_as_success(calc_project):
    data = run_audit(calc_project)
    data["findings"], data["recommendations"], data["status"] = [], [], "NO_FINDINGS_IN_SCOPE"
    page_html = render_html(data)
    assert "That is not proof of absence" in html_lib.unescape(section(page_html, 'class="d-main"', "</div>"))
    assert 'data-i18n="findings.none"' in page_html and 'data-i18n="next.none"' in page_html


# --- next step and recommendations ---------------------------------------------------------

def test_next_step_is_ranked_by_evidence_or_reported_as_a_tie(report):
    one = section(render_html(report), '<aside class="rail"', "</aside>")
    assert ACTIONS["CI_TEST_EXECUTION_GAP"][0] in one and 'href="#finding-' in one

    tied = copy.deepcopy(report)
    tied["findings"].append({"code": "LOCAL_CHECK_NOT_OBSERVED_IN_CI", "severity": "high", "evidence": {},
                             "summary": "Local/hook checks were not observed in CI; a green pipeline does not cover them."})
    tied["recommendations"].append({"finding": "LOCAL_CHECK_NOT_OBSERVED_IN_CI", "recommendation": _RECOMMENDATION["LOCAL_CHECK_NOT_OBSERVED_IN_CI"], "status": "PROPOSED"})
    tie = section(render_html(tied), '<aside class="rail"', "</aside>")
    assert "2 actions share high priority" in tie  # a tie is explained, never broken by guessing
    assert ACTIONS["CI_TEST_EXECUTION_GAP"][0] in tie and ACTIONS["LOCAL_CHECK_NOT_OBSERVED_IN_CI"][0] in tie

    first = copy.deepcopy(tied)
    first["findings"].append({"code": "NATIVE_TESTS_FAILING", "severity": "high", "summary": "Some tests fail or error in the current state.",
                              "evidence": {"count": 1, "tests": ["t"]}})
    first["recommendations"].append({"finding": "NATIVE_TESTS_FAILING", "recommendation": _RECOMMENDATION["NATIVE_TESTS_FAILING"], "status": "PROPOSED"})
    assert ACTIONS["NATIVE_TESTS_FAILING"][0] in section(render_html(first), '<aside class="rail"', "</aside>")


def test_recommendations_are_grouped_by_priority_and_always_marked_proposed(report):
    page_html = render_html(report)
    improvements = section(page_html, 'id="improvements"', '<section id="evidence"')
    groups = re.findall(r'class="rec-group g-(\w+)"', improvements)
    assert groups[0] == "first"  # the ranked next step is "do first"
    assert groups == [g for g in ("first", "high", "medium", "info") if g in groups]
    recs = re.findall(r'<li class="rec" id="rec-([A-Z_]+)"', improvements)
    assert sorted(recs) == sorted(r["finding"] for r in report["recommendations"])
    assert improvements.count('data-i18n="proposed.short"') == len(recs)


# --- findings --------------------------------------------------------------------------------

def test_findings_lead_with_title_and_consequence_and_keep_raw_evidence(report):
    page_html = render_html(report)
    for index, finding in enumerate(report["findings"]):
        start = page_html.index(f'id="finding-{index}"')
        nxt = page_html.find('<details class="finding', start)
        card = page_html[start:nxt if nxt > 0 else page_html.index('</section>', start)]
        row = card[:card.index("</summary>")]
        assert f'data-i18n="severity.{finding["severity"]}"' in row  # priority in words, not only colour
        assert finding["code"] not in re.sub(r"<[^>]+>", "", row)  # the identifier is a technical detail
        assert FINDINGS[finding["code"]]["title"][0] in html_lib.unescape(row)
        assert f'id="finding-{index}-evidence"' in card  # evidence and fix are deep-linkable inside the card
        if finding["code"] in {rec["finding"] for rec in report["recommendations"]}:
            assert f'id="finding-{index}-fix"' in card
        raw = re.search(r'<details class="tech">.*?<pre class="code">(.*?)</pre>', card, re.S).group(1)
        assert json.loads(html_lib.unescape(raw)) == finding["evidence"]
        assert f"<code>{finding['code']}</code>" in card
    big = page_html[page_html.index("tests/deep/module_299/test_299.py") - 4000:]
    assert '<details class="more">' in big  # long lists are disclosed progressively, never dropped


# --- evidence, delta and metrics ---------------------------------------------------------------

def test_delta_leads_with_movement_and_collapses_unchanged_metrics():
    page_html = render_html(improve_model(regressed=True))
    delta = section(page_html, '<section id="delta"', '<section id="evidence"')
    order = re.findall(r'class="dgroup dg-(\w+)"', delta)
    assert order == ["regressed", "improved", "changed", "unchanged"]  # regressions first, unchanged last
    assert re.search(r'<details class="dgroup dg-unchanged" id="delta-unchanged">', delta)  # collapsed by default
    assert "role=\"img\"" not in page_html  # no chart of identical bars
    counts = dict(re.findall(r'<li class="dc dc-(\w+)[^"]*"><a href="#delta-\w+"><span class="dc-n">(\d+)</span>', delta))
    assert counts == {"improved": "1", "regressed": "1", "changed": "1", "unchanged": "19", "unknown": "0"}


def test_metrics_summary_comes_before_the_complete_table(report):
    page_html = render_html(report)
    evidence = section(page_html, '<section id="evidence"', '<section id="details"')
    assert evidence.index('id="domains"') < evidence.index('id="metrics"')
    assert '<details class="panel-d" id="metrics">' in evidence  # the full table is disclosure, not the main view
    for name in report["states"]["current"]["metrics"]:
        assert f'<code class="m-id">{name}</code>' in evidence  # every metric id stays traceable
    assert 'data-i18n="metrics.delta"' not in evidence  # one state: no empty delta column


def test_verification_surface_keeps_full_commands_behind_disclosure(report):
    page_html = render_html(report)
    page = parse(page_html)
    assert len(page.with_class("origin")) == len({c["origin"] for c in report["verification_surface"]})
    assert LONG_COMMAND in html_lib.unescape(page_html)  # never truncated
    assert all(b.get("aria-label") for b in page.with_class("copy"))


def test_provenance_is_compact_and_raw_json_is_complete(report):
    page_html = render_html(report)
    prov = section(page_html, 'id="provenance"')
    assert prov.index('<dl class="prov">') < prov.index('<details class="more">')  # compact pairs first, full fields disclosed
    raw = re.search(r'<pre class="code raw-json">(.*?)</pre>', page_html, re.S).group(1)
    assert json.loads(html_lib.unescape(raw)) == json.loads(json.dumps(report, default=str))
    text = html_lib.unescape(page_html)
    for item in report["claim_boundary"]["observed"] + report["claim_boundary"]["not_evidenced"]:
        assert item in text or narrate(item)  # every claim-boundary entry is shown, as written or localized


def test_themes_offline_and_accessible_graphics(report):
    page_html = render_html(report)
    page = parse(page_html)
    assert "@media (prefers-color-scheme: dark)" in page_html and ':root[data-theme="dark"]' in page_html
    assert "prefers-reduced-motion" in page_html
    [toggle] = page.all("button", id="theme")
    assert toggle["aria-pressed"] in {"true", "false"} and toggle["aria-label"]
    assert not re.search(r'(src|href)="(https?:)?//|url\(\s*["\']?https?:|@import', page_html)
    assert not page.all("link") and not [a for a in page.all("script") if a.get("src")]
    for tag, attrs in page.elements:
        if tag == "svg":
            assert attrs.get("aria-hidden") == "true" or (attrs.get("role") == "img" and attrs.get("aria-labelledby"))
        if tag in {"input", "select", "button"}:
            assert attrs.get("aria-label") or attrs.get("id")


# --- i18n ----------------------------------------------------------------------------------------

_KNOWN_ENGLISH = sorted({
    *(en for en, pt in UI.values() if en != pt and len(en.split()) >= 3 and "{" not in en),
    *(meta[f][0] for meta in FINDINGS.values() for f in ("title", "why", "close", "rec") if f in meta),
    *(en for en, pt in NARRATIVE if "{" not in en and len(en.split()) >= 3),
    *(en for en, pt in ACTIONS.values()),
}, key=len, reverse=True)


@pytest.mark.parametrize("make", ["audit", "improve"])
def test_portuguese_decision_layer_has_no_known_english_presentation_text(report, make):
    data = report if make == "audit" else improve_model()
    page_html = render_html(data, lang="pt-BR")
    assert re.search(r'<html lang="pt-BR"', page_html)
    page = parse(page_html)
    assert not page.decision_english, page.decision_english  # raw engine text never sits in the decision layer
    text = " ".join(" ".join(page.decision_text).split())
    leaked = [phrase for phrase in _KNOWN_ENGLISH if phrase in text]
    assert not leaked, leaked
    for tag, attrs in page.elements:  # accessible names are localized too
        for name in ("aria-label", "placeholder", "data-label"):
            if attrs.get(f"data-i18n-{name}"):
                assert attrs[name] == UI.get(attrs[f"data-i18n-{name}"], (None, attrs[name]))[1] or attrs[name] != attrs.get(f"data-en{name.replace('-', '')}")


@pytest.mark.parametrize("make", ["audit", "improve"])
def test_language_switch_dictionary_reproduces_the_portuguese_page(report, make):
    """Applying the embedded dictionary to the English page (what the page script does) gives the pt-BR render."""
    data = report if make == "audit" else improve_model()
    english, portuguese = render_html(data), render_html(data, lang="pt-BR")
    table = dictionary(english)
    swapped = re.sub(r'(<(\w+)[^>]*\sdata-i18n="([^"]+)"[^>]*>)([^<]*)(</\2>)',
                     lambda m: m.group(1) + html_lib.escape(table.get(m.group(3), html_lib.unescape(m.group(4))), quote=False) + m.group(5), english)
    strip = lambda h: " ".join(re.sub(r"<[^>]+>", " ", h[h.index("<main"):h.index("</main>")]).split())
    assert html_lib.unescape(strip(swapped)) == html_lib.unescape(strip(portuguese))
    keys = set(re.findall(r'data-i18n(?:-[\w-]+)?="([^"]+)"', english))
    assert keys <= set(table)  # every translatable node and attribute has its pt-BR text embedded
    assert set(table) <= keys  # and nothing else is embedded


def test_engine_text_without_a_template_stays_original_and_only_in_technical_detail(report):
    data = copy.deepcopy(report)
    data["findings"][0]["summary"] = "An adapter-specific sentence with a dynamic value 42."
    page_html = render_html(data, lang="pt-BR")
    assert '<p class="original" lang="en">An adapter-specific sentence with a dynamic value 42.</p>' in page_html
    assert not parse(page_html).decision_english


def test_template_values_are_kept_and_kinds_localized():
    pair = narrate("native pytest-native run in an isolated copy: PASS (5 invocations)")
    assert pair == ("native pytest-native run in an isolated copy: passed (5 invocations)",
                    "execução nativa pytest-native em cópia isolada: aprovado (5 invocações)")
    assert narrate("PIPELINE_EQUIVALENT (FAIL): reproduced 4/5 delivery checks locally; a reproduced gating check failed")[1].startswith(
        "Verificações equivalentes ao pipeline (falhou): 4 de 5")
    assert narrate("pytest-native: static inventory is bounded source analysis, not native collection")[1].startswith("pytest-native: o inventário")
    assert narrate("an adapter-specific note with no template") is None
    assert narrate("reproduced many/5 delivery checks locally") is None  # placeholder shapes are enforced


# --- catalog completeness --------------------------------------------------------------------------

def _engine_findings():
    assert any(PACKAGE.rglob("*.py")), PACKAGE  # the scan must see the imported package, never an empty or missing tree
    found = {}
    for path in PACKAGE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding" and node.args:
                first = node.args[0]
                codes = [first.value] if isinstance(first, ast.Constant) else [first.body.value, first.orelse.value]
                summary = node.args[1] if len(node.args) > 1 else None
                try:
                    text = ast.literal_eval(summary)
                except (ValueError, TypeError):
                    text = None
                for code in codes:
                    found[code] = text
    return found


def test_catalog_covers_every_engine_finding_and_its_templates_match_the_engine_text():
    engine = _engine_findings()
    assert engine and set(engine) <= set(FINDINGS), set(engine) - set(FINDINGS)
    for code, text in engine.items():
        meta = FINDINGS[code]
        assert meta.get("title") and meta.get("why"), code
        if meta.get("summary"):
            assert text == meta["summary"][0], code  # otherwise the translation would silently never apply
        if meta.get("rec") and code in _RECOMMENDATION:
            assert meta["rec"][0] == _RECOMMENDATION[code], code
    assert set(ACTIONS) <= {code for code, meta in FINDINGS.items() if meta.get("rec")}


def _shape(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _shape(node.left), _shape(node.right)
        return (left if left is not None else "{}") + (right if right is not None else "{}")
    return None


def _engine_sentences():
    """Every literal sentence the engine writes into a limitation, a claim-boundary entry or a qualification summary."""
    assert any(PACKAGE.rglob("*.py")), PACKAGE
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name.startswith("report"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            args, f = [], node.func
            if isinstance(f, ast.Attribute) and f.attr == "append":
                target = f.value.attr if isinstance(f.value, ast.Attribute) else getattr(f.value, "id", "")
                args = node.args[:1] if target in ("limitations", "observed", "not_evidenced") else []
            elif isinstance(f, ast.Name) and f.id == "_stage":
                args = node.args[2:]
            for arg in args:
                text = _shape(arg)
                if text and re.sub(r"[{}\s:;,.()|]", "", text):
                    yield text


# Composed in two steps by the engine; each complete form has its own template.
_COMPOSED = {
    "{}: static inventory is bounded source analysis, not native collection",
    "{}: {} tests were deselected by the run's own filters; they are not evidenced",
    "all {} originally passing invocations still pass{}",
    "original tests no longer pass against the candidate: {}{}",
    "{}; all gating checks passed", "{}; a reproduced gating check failed", "{}; a reproduced check could not run",
    "no instability observed in {} executions of {} invocations; {}", "no relevant invocation was rerun; {}",
}
# Lists of test ids and failure-contract dimensions: technical text, shown as written; the check status is localized.
_RAW_BY_DESIGN = {"{} | not passing at runtime: {}", "{} | only type/status observed: {}"}


def test_every_engine_sentence_has_a_localized_template():
    norm = lambda t: re.sub(r"\{[^}]*\}", "{}", t)
    known = {norm(en) for en, _ in NARRATIVE}
    sentences = {norm(s) for s in _engine_sentences()}
    assert _COMPOSED | _RAW_BY_DESIGN <= sentences  # the exceptions still exist in the engine
    missing = sorted(s for s in sentences - _COMPOSED - _RAW_BY_DESIGN if s not in known)
    assert not missing, missing


def test_every_catalog_entry_has_both_languages():
    for table in (UI, METRICS, ACTIONS):
        for key, (en, pt) in table.items():
            assert en and pt, key
    for en, pt in NARRATIVE:
        assert re.findall(r"\{(\w+)", en) and sorted(re.findall(r"\{(\w+)", en)) == sorted(re.findall(r"\{(\w+)", pt)) or "{" not in en, en
    for code, meta in FINDINGS.items():
        for field in ("title", "summary", "why", "close", "rec"):
            if field in meta:
                assert all(meta[field]), (code, field)


# --- v3 contracts --------------------------------------------------------------------------------

def test_one_canonical_html_per_audit_run(calc_project, tmp_path, capsys):
    from assertiva import cli

    out = tmp_path / "reports"
    cli.main(["audit", str(calc_project), "--output", "json", "--report-dir", str(out)])
    report = json.loads(capsys.readouterr().out)
    assert sorted(p.name for p in out.iterdir()) == ["audit.html", "audit.json"]
    assert Path(report["report_path"]) == out / "audit.html"
    cli.main(["audit", str(calc_project), "--output", "json", "--report-dir", str(out)])
    capsys.readouterr()
    assert sorted(p.name for p in out.iterdir()) == ["audit.html", "audit.json"]  # a new run replaces, never adds pages


def _installed_package() -> bool:
    """Whether the imported package sits in a site-packages directory (an installed wheel), whatever the checkout layout."""
    return any(part in ("site-packages", "dist-packages") for part in PACKAGE.parts)


def test_provenance_names_the_runtime_that_produced_the_evidence(calc_project):
    """The invariants hold for an editable checkout and for an installed wheel alike; each is checked against a source
    independent of the code under test."""
    import importlib.metadata
    import subprocess
    import tomllib

    report = run_audit(calc_project)
    prov, runtime = report["provenance"], report["provenance"]["runtime"]
    if _installed_package():
        expected_kind, expected_version = "installed-package", importlib.metadata.version("assertiva")
    else:
        expected_kind = "source-checkout"
        expected_version = tomllib.loads((PACKAGE.parent / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert prov["assertiva_version"] == assertiva.__version__ == runtime["version"] == expected_version  # the code that ran
    assert runtime["install"] == expected_kind  # an installed package is never labelled a source checkout, or the reverse
    if expected_kind == "installed-package" or not (PACKAGE.parent / ".git").exists():
        assert runtime["revision"] is None and runtime["dirty"] is None  # no checkout identity exists to be claimed
    else:
        head = subprocess.run(["git", "-C", str(PACKAGE.parent), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        assert runtime["revision"] == head and isinstance(runtime["dirty"], bool)
    page_html = render_html(report)
    assert f'<meta name="generator" content="Assertiva {expected_version}">' in page_html
    assert 'class="prov-warn"' not in page_html


def test_evidence_from_another_version_is_announced_never_masked(report):
    from assertiva import __version__

    old = copy.deepcopy(report)
    old["provenance"]["assertiva_version"] = "0.0.1"
    page_html = render_html(old)
    warning = html_lib.unescape(section(page_html, 'class="prov-warn"', "</p>"))
    assert "0.0.1" in warning and __version__ in warning


def test_lifecycle_never_shows_a_candidate_as_applied():
    page_html = render_html(improve_model(pipeline="FAIL"))
    life = section(page_html, '<div class="life">', "</ol>")
    steps = dict(re.findall(r'<li class="step st-(\w+)[^"]*">.*?data-i18n="life\.(\w+)"', life))
    states = re.findall(r'<li class="step st-(\w+)', life)
    assert len(states) == 6
    assert states[0] == "done" and states[2] == "fail"  # baseline observed, review blocked
    assert states[3:] == ["todo", "todo", "todo"]  # approval not requested, nothing applied, nothing re-measured
    ready = section(render_html(improve_model(pipeline="PASS")), '<div class="life">', "</ol>")
    assert re.findall(r'<li class="step st-(\w+)', ready)[3:] == ["pending", "todo", "todo"]
    del steps


def test_evidence_strength_uses_distinct_glyphs_not_a_scale(report):
    page_html = render_html(report)
    assert 'class="meter"' not in page_html
    ledger = section(page_html, '<ol class="ledger"', "</ol>")
    glyphs = dict(re.findall(r'class="lrow lvl-(\w+)[^"]*".*?<use href="#i-(\w+)"', ledger))
    assert glyphs["declared"] != glyphs["not_evidenced"] != glyphs["inspected"]
    assert all('data-i18n="lvl.' in row for row in re.findall(r'<li class="lrow.*?</li>', ledger))  # always a label, never colour alone


def test_portuguese_numbers_and_dates_are_localized_but_canonical_values_kept():
    data = improve_model()
    page_html = render_html(data, lang="pt-BR")
    snapshot = re.sub(r"<[^>]+>", " ", section(page_html, 'id="domains"'))
    assert "89,5%" in snapshot and "89.5%" not in snapshot
    assert re.search(r'<time [^>]*datetime="2026-10-07T12:00:00\+00:00" data-local[^>]*>7 out 2026', page_html)  # browser shows local time
    raw = re.search(r'<pre class="code raw-json">(.*?)</pre>', page_html, re.S).group(1)
    assert json.loads(html_lib.unescape(raw))["states"]["candidate"]["metrics"]["line_coverage"]["value"] == 89.5


def test_terminology_is_progressive_tier_codes_only_as_metadata(report):
    page = parse(render_html(report, lang="pt-BR"))
    text = " ".join(page.decision_text)
    assert not re.search(r"\bE[0-4]\b", text)  # codes live in abbr/titles and technical detail
    assert "invocaç" not in text.lower()  # decision layer speaks of test cases


def test_technical_claim_boundary_is_grouped_and_counted(report):
    page_html = render_html(report)
    claim = section(page_html, 'id="claim"', '<section id="unknowns"')
    for name in ("observed", "not_evidenced", "limitations"):
        values = report["claim_boundary"][name]
        if values:
            assert f'<details class="claim-g cg-{name}"' in claim
            listed = re.findall(rf'<div class="cd" id="claim-{name}-\w+">.*?<span class="count">(\d+)</span>', claim)
            assert sum(map(int, listed)) == len(values)  # grouped, nothing dropped


def test_print_and_filters_and_raw_blocks_are_supported(report):
    data = copy.deepcopy(report)
    data["findings"] += [{**data["findings"][-1], "code": "NESTED_REPOSITORY", "severity": "info", "evidence": {}}] * 3
    page_html = render_html(data)
    assert "@media print" in page_html and "beforeprint" in page_html
    assert re.search(r'<button type="button" id="clear-filters"[^>]*hidden', page_html)
    assert "URLSearchParams" in page_html and "show_full" in page_html
