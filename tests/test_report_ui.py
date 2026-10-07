"""Contract of the HTML Assurance Report as a product surface: structure, honesty, accessibility, i18n, offline.

These tests parse the rendered page; they do not test pixels or styling."""

import ast
import copy
import html as html_lib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from assertiva.audit import run_audit
from assertiva.report import _RECOMMENDATION, render_html
from assertiva.report_i18n import FINDINGS, METRICS, UI

from conftest import write

ROOT = Path(__file__).resolve().parents[1]
LONG_COMMAND = "pytest " + " ".join(f"--option-{i}=/a/very/long/path/segment/{i}" for i in range(60))


class Page(HTMLParser):
    """Element tree light: tags with attributes, text per element id, heading levels in order."""

    def __init__(self):
        super().__init__()
        self.elements, self.headings, self.stack = [], [], []
        self.texts: dict[str, list[str]] = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.elements.append((tag, attrs))
        if re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))
        if tag not in {"br", "img", "input", "meta", "col", "use", "path", "rect", "circle"}:
            self.stack.append(attrs.get("id"))

    def handle_endtag(self, tag):
        if tag not in {"br", "img", "input", "meta", "col", "use", "path", "rect", "circle"} and self.stack:
            self.stack.pop()

    def handle_data(self, data):
        for element_id in self.stack:
            if element_id:
                self.texts.setdefault(element_id, []).append(data)

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


def pt_dictionary(page_html):
    raw = re.search(r'<script type="application/json" id="i18n">(.*?)</script>', page_html, re.S).group(1)
    return json.loads(raw.replace("<\\/", "</"))["pt-BR"]


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


def test_page_has_landmarks_one_h1_and_no_skipped_heading_levels(report):
    page = parse(render_html(report))
    tags = [t for t, _ in page.elements]
    for landmark in ("header", "nav", "main", "footer"):
        assert landmark in tags
    assert page.all("a", **{"class": "skip", "href": "#main"})
    assert page.headings.count(1) == 1 and page.headings[0] == 1
    assert all(b - a <= 1 for a, b in zip(page.headings, page.headings[1:])), page.headings


def test_four_areas_in_order_and_overview_answers_the_decision_questions(report):
    page_html = render_html(report)
    page = parse(page_html)
    areas = [a["id"] for a in page.with_class("area")]
    assert areas == ["overview", "evidence", "verification", "details"]
    decisions = page.with_class("decision")
    assert [d["class"].split()[1] for d in decisions] == ["d-working", "d-attention", "d-unknown", "d-next"]
    assert len(page.with_class("claim")) == 3  # observed / not evidenced / limitations
    assert page.all(id="summary") and page.all(id="improvements") and page.all(id="top-findings")


def test_overall_status_is_humanized_keeps_the_raw_enum_and_is_never_green(report):
    page_html = render_html(report)
    hero = page_html[page_html.index('class="hero-status"'):]
    hero = hero[:hero.index("</div>")]
    assert f'<code class="hero-raw">{report["status"]}</code>' in hero
    assert "tone-pass" not in hero  # a status for the whole project is never painted as success


def test_absence_of_findings_or_runs_is_never_a_strength(calc_project):
    data = run_audit(calc_project)
    data["findings"], data["recommendations"] = [], []
    data["states"]["current"]["metrics"].pop("negative_paths_with_state_after_rejection", None)
    page = parse(render_html(data))
    working = page.with_class("d-working")[0]
    assert working
    page_html = render_html(data)
    working_html = page_html[page_html.index('class="decision d-working"'):page_html.index('class="decision d-attention"')]
    assert 'data-i18n="decision.working.none"' in working_html and "<li>" not in working_html
    assert 'data-i18n="findings.none"' in page_html  # "not raised in scope", not "no problems"


def test_next_action_comes_only_from_existing_recommendations(report):
    one_high = render_html(report)
    action = one_high[one_high.index('class="decision d-next"'):]
    assert 'data-i18n="f.CI_TEST_EXECUTION_GAP.rec"' in action[:action.index("</article>")]

    tied = copy.deepcopy(report)
    tied["findings"].append({**tied["findings"][-1], "code": "LOCAL_CHECK_NOT_OBSERVED_IN_CI",
                             "summary": "Local/hook checks were not observed in CI; a green pipeline does not cover them.", "evidence": {}})
    tied["recommendations"].append({"finding": "LOCAL_CHECK_NOT_OBSERVED_IN_CI", "recommendation": _RECOMMENDATION["LOCAL_CHECK_NOT_OBSERVED_IN_CI"], "status": "PROPOSED"})
    action = render_html(tied)
    action = action[action.index('class="decision d-next"'):]
    assert 'data-i18n="decision.next.none"' in action[:action.index("</article>")]

    first = copy.deepcopy(tied)
    first["findings"].append({"code": "NATIVE_TESTS_FAILING", "severity": "high", "summary": "Some tests fail or error in the current state.",
                              "evidence": {"count": 1, "tests": ["t"]}})
    first["recommendations"].append({"finding": "NATIVE_TESTS_FAILING", "recommendation": _RECOMMENDATION["NATIVE_TESTS_FAILING"], "status": "PROPOSED"})
    action = render_html(first)
    action = action[action.index('class="decision d-next"'):]
    assert 'data-i18n="f.NATIVE_TESTS_FAILING.rec"' in action[:action.index("</article>")]


def test_findings_are_readable_cards_with_metadata_and_expandable_raw_evidence(report):
    page_html = render_html(report)
    for index, finding in enumerate(report["findings"]):
        start = page_html.index(f'id="finding-{index}"')
        card = page_html[start:page_html.index("</details></div></details>", start)]
        summary = card[:card.index("</summary>")]
        assert f'data-i18n="severity.{finding["severity"]}"' in summary  # severity in words, not only colour
        assert f'<code class="f-code">{finding["code"]}</code>' in summary  # the code is metadata, not the title
        title = re.search(r'class="f-title"[^>]*>([^<]+)<', summary).group(1)
        assert title != finding["code"]
        raw = re.search(r'<details class="tech">.*?<pre class="code">(.*?)</pre>', card, re.S).group(1)
        assert json.loads(html_lib.unescape(raw)) == finding["evidence"]
    big = page_html[page_html.index("tests/deep/module_299/test_299.py") - 2000:]
    assert '<details class="more">' in big  # long evidence lists are disclosed progressively, never dropped


def test_verification_surface_is_grouped_by_origin_with_full_commands_and_a_table_view(report):
    page = parse(render_html(report))
    origins = {c["origin"] for c in report["verification_surface"]}
    assert len(page.with_class("origin")) == len(origins)
    assert len([a for a in page.with_class("check") if a.get("data-kind")]) == len(report["verification_surface"])
    assert page.all("table", id="surface")
    assert LONG_COMMAND in html_lib.unescape(render_html(report))  # never truncated in the expandable detail
    assert all(b.get("aria-label") for b in page.with_class("copy"))


def test_metrics_are_humanized_keep_ids_and_show_delta_only_when_comparing(report):
    page_html = render_html(report)
    for name in report["states"]["current"]["metrics"]:
        assert f'<code class="m-id">{name}</code>' in page_html
        if name in METRICS:
            assert f'data-i18n="m.{name}">{METRICS[name][0]}<' in page_html
    assert 'data-i18n="metrics.delta"' not in page_html  # only CURRENT: no empty delta column
    compared = copy.deepcopy(report)
    compared["evidence_delta"] = {"improved": [], "unchanged": [{"name": "weak_oracle_tests", "state": "UNCHANGED"}], "regressed": [], "changed": [], "unknown": []}
    assert 'data-i18n="metrics.delta"' in render_html(compared)


def test_provenance_pairs_and_raw_json_keep_every_canonical_value(report):
    page_html = render_html(report)
    page = parse(page_html)
    provenance = page.text("provenance")
    assert report["provenance"]["assertiva_version"] in provenance and "Revision" in provenance
    raw = re.search(r'<pre class="code raw-json">(.*?)</pre>', page_html, re.S).group(1)
    assert json.loads(html_lib.unescape(raw)) == json.loads(json.dumps(report, default=str))
    text = html_lib.unescape(page_html)
    for item in report["claim_boundary"]["observed"] + report["claim_boundary"]["not_evidenced"]:
        assert item in text


def test_unknowns_already_shown_as_not_evidenced_are_not_repeated(report):
    page = parse(render_html(report))
    shared = set(report["remaining_unknowns"]) & set(report["claim_boundary"]["not_evidenced"])
    assert shared and all(item not in page.text("unknowns") for item in shared)
    assert "same as under" in page.text("unknowns")


def test_light_and_dark_themes_and_offline_self_containment(report):
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


def test_every_ui_key_on_the_page_has_its_portuguese_text_embedded_and_nothing_else(report):
    page_html = render_html(report)
    dictionary = pt_dictionary(page_html)
    keys = set(re.findall(r'data-i18n="([^"]+)"', page_html)) | set(re.findall(r'data-i18n-(?:aria-label|placeholder|title)="([^"]+)"', page_html))
    for key in keys:
        assert key in dictionary or f"{key}.one" in dictionary, key
    plural_bases = {k.rsplit(".", 1)[0] for k in dictionary if k.endswith((".one", ".other"))}
    unused = {k for k in dictionary if k not in keys and k.rsplit(".", 1)[0] not in plural_bases and k != "copied"}
    assert not unused, unused  # only what the page uses is embedded
    assert parse(page_html).all("select", id="lang") and 'value="pt-BR"' in page_html


def test_engine_text_without_a_fixed_template_is_shown_as_written_and_marked_english(report):
    data = copy.deepcopy(report)
    data["findings"][0]["summary"] = "An adapter-specific sentence with a dynamic value 42."
    page_html = render_html(data)
    assert '<p lang="en">An adapter-specific sentence with a dynamic value 42.</p>' in page_html


def _engine_findings():
    """(code, fixed English summary or None) for every Finding the engine can emit."""
    found = {}
    for path in (ROOT / "assertiva").rglob("*.py"):
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


def test_every_catalog_entry_has_both_languages():
    for key, (en, pt) in UI.items():
        assert en and pt, key
    for name, (en, pt) in METRICS.items():
        assert en and pt, name
    for code, meta in FINDINGS.items():
        for field in ("title", "summary", "why", "close", "rec"):
            if field in meta:
                assert all(meta[field]), (code, field)
