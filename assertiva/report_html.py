"""HTML rendering of the Assurance Report: one self-contained, offline, bilingual (en / pt-BR) page.

Presentation only. The canonical report model is never changed or re-interpreted here: every card, list and
"next action" is drawn from fields the engine already produced. The page reads in four areas:

  Overview      decision surface (working / attention / not evidenced / next action), key evidence,
                "What does green prove?", highest-priority findings, recommended improvements
  Evidence      metrics by state, delta, qualification, change set, negative paths, mutation, artifact,
                delivery, selection, history
  Verification  verification surface grouped by origin, runs and provenance, execution budget
  Details       all findings, remaining unknowns, provenance, raw JSON

Translations are looked up by stable key (report_i18n). Engine sentences are translated only on an exact
match of a fixed English template; otherwise they are shown as written and marked lang="en". English is
rendered into the HTML; the pt-BR strings the page uses are embedded and swapped in by a small script, so
the page works without JavaScript and without any network access.
"""

from __future__ import annotations

import html
import json
from typing import Any

from .report_i18n import FINDINGS, METRIC_GROUPS, METRICS, SENTENCES, UI

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
_STATE_ORDER = ("current", "baseline", "candidate", "applied")
_SENTENCE_KEYS = {en: f"s.{i}" for i, (en, _) in enumerate(SENTENCES)}
_LIST_LIMIT = 6


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _humanize(identifier: str) -> str:
    text = str(identifier).replace("_", " ").strip()
    return text[:1].upper() + text[1:].lower() if text else text


def _fmt_value(metric: dict | None) -> str:
    if not metric or metric.get("value") is None:
        return "—"
    value, unit = metric["value"], metric.get("unit")
    text = f"{value:.2f}" if isinstance(value, float) else str(value)
    if not unit:
        return text
    return text + unit if unit == "%" else f"{text} {unit}"


# Tone classes for statuses. The overall report status is never shown as success: green belongs to
# specific evidence (a passed run, a qualified artifact), not to the project as a whole.
_TONE = {
    "pass": "pass", "executed": "pass", "improved": "pass", "killed": "pass", "no_instability_observed": "neutral",
    "fail": "fail", "regressed": "fail", "consistent_failure": "fail", "survived": "fail", "high": "fail",
    "historically_flaky": "fail", "observed_unstable_current_run": "fail",
    "blocked": "blocked", "medium": "warn", "findings": "warn", "needs_attention": "warn", "retire_candidate": "warn",
    "environment_specific": "warn", "bounded_by_unknowns": "warn",
    "unknown": "unknown", "not_run": "not_run", "insufficient_evidence": "unknown", "not_configured": "not_run",
    "info": "neutral", "low": "neutral", "unchanged": "neutral", "changed": "neutral", "reused": "neutral",
    "no_findings_in_scope": "neutral", "full_suite": "neutral",
    "ready_for_review": "accent", "applied": "accent", "add": "accent", "modify": "accent", "proven_paths": "accent",
    "proposed": "accent",
}
_ICON = {"pass": "check", "fail": "cross", "blocked": "block", "warn": "alert", "unknown": "question", "not_run": "dash",
         "neutral": "dot", "accent": "dot"}


class _Renderer:
    """Collects the translation keys a page uses so only those are embedded."""

    def __init__(self, report: dict):
        self.report = report
        self.used: dict[str, str] = {}  # key -> pt-BR text

    # --- translation -----------------------------------------------------------------
    def _lookup(self, key: str, n: Any = None) -> tuple[str, str] | None:
        if n is not None and f"{key}.one" in UI:
            for form in ("one", "other"):
                self.used[f"{key}.{form}"] = UI[f"{key}.{form}"][1]
            return UI[f"{key}.one" if n == 1 else f"{key}.other"]
        entry = UI.get(key)
        if entry:
            self.used[key] = entry[1]
        return entry

    def ref(self, key: str) -> dict:
        """An argument that is itself translated (e.g. a state name inside a sentence)."""
        entry = self._lookup(key)
        if entry:
            self.used[key] = entry[1]
        return {"$": key, "en": entry[0] if entry else key}

    def text(self, key: str, **args: Any) -> str:
        """English text for a key (registers the key); for attributes and plain contexts."""
        entry = self._lookup(key, args.get("n"))
        if entry is None:
            return key
        values = {k: (v["en"] if isinstance(v, dict) else v) for k, v in args.items()}
        try:
            return entry[0].format(**values)
        except (KeyError, IndexError):
            return entry[0]

    def t(self, key: str, tag: str = "span", cls: str | None = None, attrs: str = "", **args: Any) -> str:
        english = self.text(key, **args)
        extra = f' data-i18n-args="{_e(json.dumps(args, ensure_ascii=False))}"' if args else ""
        klass = f' class="{cls}"' if cls else ""
        return f'<{tag}{klass} data-i18n="{key}"{extra}{(" " + attrs) if attrs else ""}>{_e(english)}</{tag}>'

    def attr(self, name: str, key: str) -> str:
        """An attribute whose value is translated (aria-label, title, placeholder)."""
        return f'{name}="{_e(self.text(key))}" data-i18n-{name}="{key}"'

    def raw_key(self, key: str, en: str, pt: str | None, tag: str = "span", cls: str | None = None) -> str:
        """A catalog entry outside UI (finding/metric texts)."""
        if pt:
            self.used[key] = pt
        klass = f' class="{cls}"' if cls else ""
        return f'<{tag}{klass} data-i18n="{key}">{_e(en)}</{tag}>'

    def canon(self, sentence: str, tag: str = "span", cls: str | None = None) -> str:
        """Engine text: translated only on an exact template match, otherwise shown as written (lang=en)."""
        key = _SENTENCE_KEYS.get(sentence)
        if key:
            return self.raw_key(key, sentence, SENTENCES[int(key[2:])][1], tag, cls)
        klass = f' class="{cls}"' if cls else ""
        return f'<{tag}{klass} lang="en">{_e(sentence)}</{tag}>'

    # --- small components ------------------------------------------------------------
    def icon(self, name: str) -> str:
        return f'<svg class="ic" aria-hidden="true" focusable="false"><use href="#i-{name}"></use></svg>'

    def chev(self) -> str:
        return '<svg class="ic chev" aria-hidden="true" focusable="false"><use href="#i-chev"></use></svg>'

    def pill(self, raw: str, prefix: str = "st.", show_raw: bool = False) -> str:
        cls = str(raw).lower()
        tone = _TONE.get(cls, "neutral")
        key = f"{prefix}{raw}"
        label = self.t(key) if key in UI else f"<span>{_e(_humanize(raw))}</span>"
        raw_html = f'<code class="raw">{_e(raw)}</code>' if show_raw else ""
        return f'<span class="pill {_e(cls)} tone-{tone}" data-raw="{_e(raw)}">{self.icon(_ICON[tone])}{label}{raw_html}</span>'

    def tier(self, tier: str | None) -> str:
        key = f"tier.{tier}" if tier else "tier.none"
        return f'<span class="tier">{self.t(key)}</span>'

    def items(self, values: list[str], empty_key: str, canon: bool = True, limit: int = _LIST_LIMIT) -> str:
        if not values:
            return f'<p class="empty">{self.t(empty_key)}</p>'
        render = (lambda v: self.canon(v)) if canon else (lambda v: f"<code>{_e(v)}</code>")
        head = "".join(f"<li>{render(v)}</li>" for v in values[:limit])
        rest = values[limit:]
        more = (
            f'<details class="more"><summary>{self.t("show_all", n=len(values))}</summary>'
            f'<ul class="list">{"".join(f"<li>{render(v)}</li>" for v in rest)}</ul></details>'
            if rest else ""
        )
        return f'<ul class="list">{head}</ul>{more}'

    def state(self, key: str) -> str:
        return self.t(f"state.{key}")


# --- finding helpers ------------------------------------------------------------------

def _finding_meta(code: str) -> dict:
    return FINDINGS.get(code) or {}


_COUNT_KEYS = ("count", "smoke_like", "total")


def _affected(r: _Renderer, evidence: dict) -> tuple[str, list[str]]:
    """(translatable markup, listed items) from the evidence the engine attached; never an invented count."""
    listed: list[str] = []
    for value in evidence.values():
        if isinstance(value, list) and all(isinstance(v, (str, int, float)) for v in value):
            listed = [str(v) for v in value]
            break
    if isinstance(evidence.get("smoke_like"), int) and isinstance(evidence.get("total"), int):
        return r.t("finding.of", a=evidence["smoke_like"], b=evidence["total"]), listed
    if isinstance(evidence.get("count"), int):
        return r.t("finding.count", n=evidence["count"]), listed
    if listed:
        return r.t("finding.listed", n=len(listed)), listed
    return "", listed


def _finding_title(r: _Renderer, f: dict) -> str:
    meta = _finding_meta(f["code"])
    if meta.get("title"):
        en, pt = meta["title"]
        return r.raw_key(f"f.{f['code']}.title", en, pt, cls="f-title")
    return f'<span class="f-title">{_e(_humanize(f["code"]))}</span>'


def _finding_summary(r: _Renderer, f: dict) -> str:
    meta = _finding_meta(f["code"])
    summary = meta.get("summary")
    if summary and summary[0] == f["summary"]:
        return r.raw_key(f"f.{f['code']}.summary", summary[0], summary[1], tag="p")
    return f'<p lang="en">{_e(f["summary"])}</p>'


def _recommendation_for(report: dict, code: str) -> str | None:
    return next((rec["recommendation"] for rec in report.get("recommendations") or [] if rec["finding"] == code), None)


def _rec_html(r: _Renderer, code: str, text: str, tag: str = "p") -> str:
    rec = _finding_meta(code).get("rec")
    if rec and rec[0] == text:
        return r.raw_key(f"f.{code}.rec", rec[0], rec[1], tag=tag)
    return f'<{tag} lang="en">{_e(text)}</{tag}>'


def _sorted_findings(findings: list[dict]) -> list[tuple[int, dict]]:
    indexed = list(enumerate(findings))
    return sorted(indexed, key=lambda item: (_SEVERITY_ORDER.get(item[1]["severity"], 9), item[0]))


def _category(code: str) -> str:
    return _finding_meta(code).get("category") or "other"


def _finding_card(r: _Renderer, index: int, f: dict) -> str:
    code, report = f["code"], r.report
    meta = _finding_meta(code)
    affected, listed = _affected(r, f.get("evidence") or {})
    rec = _recommendation_for(report, code)
    why = meta.get("why")
    close = meta.get("close")
    category = _category(code)
    other = {k: v for k, v in (f.get("evidence") or {}).items() if not isinstance(v, (list, dict)) and k not in _COUNT_KEYS}
    kv = "".join(f"<dt><code>{_e(k)}</code></dt><dd><code>{_e(v)}</code></dd>" for k, v in other.items())
    evidence_html = (
        (f'<p class="affected"><strong>{r.t("finding.affected")}</strong> {affected}</p>' if affected else "")
        + (r.items(listed, "none", canon=False, limit=8) if listed else "")
        + (f'<dl class="kv">{kv}</dl>' if kv else "")
    )
    original = (
        f'<dt>{r.t("original")}</dt><dd lang="en">{_e(f["summary"])}</dd>'
        if meta.get("summary") else ""
    )
    sections = [
        f'<div class="f-block"><h4>{r.t("finding.observed")}</h4>{_finding_summary(r, f)}</div>',
    ]
    if why:
        sections.append(f'<div class="f-block"><h4>{r.t("finding.why")}</h4>{r.raw_key(f"f.{code}.why", why[0], why[1], tag="p")}</div>')
    if evidence_html:
        sections.append(f'<div class="f-block"><h4>{r.t("finding.evidence")}</h4>{evidence_html}</div>')
    if rec:
        sections.append(
            f'<div class="f-block rec"><h4>{r.t("finding.recommendation")} {r.pill("PROPOSED")}</h4>'
            f"{_rec_html(r, code, rec)}</div>"
        )
    if close:
        sections.append(f'<div class="f-block"><h4>{r.t("finding.close")}</h4>{r.raw_key(f"f.{code}.close", close[0], close[1], tag="p")}</div>')
    sections.append(
        f'<details class="tech"><summary>{r.t("finding.technical")}</summary><dl class="kv">'
        f'<dt>{r.t("finding.code")}</dt><dd><code>{_e(code)}</code></dd>{original}</dl>'
        f'<h5>{r.t("finding.raw")}</h5><pre class="code">{_e(json.dumps(f.get("evidence") or {}, indent=2, ensure_ascii=False))}</pre></details>'
    )
    severity = f["severity"]
    affected_html = f'<span aria-hidden="true">·</span>{affected}' if affected else ""
    return (
        f'<details class="finding" id="finding-{index}" data-severity="{_e(severity)}" data-category="{_e(category)}">'
        f'<summary><span class="f-head">{r.pill(severity, prefix="severity.")}{_finding_title(r, f)}</span>'
        f'<span class="f-meta">{r.t(f"cat.{category}")}<span aria-hidden="true">·</span>{r.tier(meta.get("tier"))}'
        f"{affected_html}"
        f'<code class="f-code">{_e(code)}</code></span>{r.chev()}</summary>'
        f'<div class="f-body">{"".join(sections)}</div></details>'
    )


# --- decision surface -----------------------------------------------------------------

def _states(report: dict) -> list[tuple[str, dict]]:
    return [(k, report["states"][k]) for k in _STATE_ORDER if report["states"].get(k)]


def _strengths(r: _Renderer, report: dict) -> list[str]:
    """Positive statements backed by structured evidence only (never by the absence of a finding)."""
    out: list[str] = []
    for key, state in _states(report):
        label = r.ref(f"state.{key}")
        for run in state.get("runs", []):
            if run["status"] == "PASS" and run["invocations"]:
                which = "strength.report" if run["mode"] == "report" else "strength.run"
                out.append(r.t(which, state=label, adapter=run["adapter"], n=run["invocations"]) + " " + r.tier("E0"))
        for artifact in state.get("artifacts", []):
            if artifact["status"] == "PASS":
                out.append(r.t("strength.artifact", state=label, kind=artifact["kind"]) + " " + r.tier("E0"))
        metrics = state.get("metrics") or {}
        evaluated = (metrics.get("mutation_evaluated") or {}).get("value")
        if evaluated and not (metrics.get("mutation_survived") or {}).get("value") and not (metrics.get("mutation_no_coverage") or {}).get("value"):
            tools = ", ".join(sorted({m["tool"] or "?" for m in state.get("mutation", []) if not m["error"]}))
            out.append(r.t("strength.mutation", state=label, n=evaluated, tool=tools) + " " + r.tier("E0"))
        killed = (metrics.get("negative_controls_killed") or {}).get("value")
        if killed and not (metrics.get("negative_controls_survived") or {}).get("value") and not (metrics.get("negative_controls_invalid") or {}).get("value"):
            out.append(r.t("strength.controls", state=label, n=killed) + " " + r.tier("E0"))
        post = (metrics.get("negative_paths_with_state_after_rejection") or {}).get("value")
        if post:
            out.append(r.t("strength.post_rejection", state=label, n=post) + " " + r.tier("E3"))
    for stage in (report.get("candidate_qualification") or {}).get("stages", []):
        for check in stage["checks"]:
            if check["status"] == "PASS":
                name = r.ref(f"q.{check['check']}") if f"q.{check['check']}" in UI else _humanize(check["check"])
                out.append(r.t("strength.check", check=name) + f' <span class="muted" lang="en">— {_e(check["summary"])}</span>')
    return out


def _attention(r: _Renderer, report: dict) -> list[str]:
    out = []
    for index, f in _sorted_findings(report["findings"]):
        if f["severity"] in ("high", "medium"):
            out.append(f'<a href="#finding-{index}">{r.pill(f["severity"], prefix="severity.")}{_finding_title(r, f)}</a>')
    for stage in (report.get("candidate_qualification") or {}).get("stages", []):
        for check in stage["checks"]:
            if check["status"] in ("FAIL", "BLOCKED"):
                name = r.t(f"q.{check['check']}") if f"q.{check['check']}" in UI else _e(_humanize(check["check"]))
                out.append(f'<a href="#qualification">{r.pill(check["status"])}{name}</a>')
    return out


# Findings whose own engine recommendation states that they come first.
_FIRST = ("NATIVE_COLLECTION_ERRORS", "NATIVE_TESTS_FAILING")


def _next_action(r: _Renderer, report: dict) -> str:
    """One action only when the existing evidence ranks it; otherwise say so."""
    if report["workflow"] == "improve":
        q = report.get("candidate_qualification") or {}
        if report["status"] == "READY_FOR_REVIEW" and not report["states"].get("applied"):
            return (f'<p class="next-action">{r.t("decision.next.review")}</p>'
                    f'<p class="muted"><strong>{r.t("decision.next.because")}</strong> {r.t("decision.next.review.why")}</p>'
                    f'<a class="link" href="#changes">{r.t("changes.title")}</a>') if q else ""
        link = f'<a class="link" href="#qualification">{r.t("qual.title")}</a>' if q else ""
        return f'<p class="muted">{r.t("decision.next.none")}</p>{link}'
    findings = report["findings"]
    with_rec = [(i, f) for i, f in enumerate(findings) if _recommendation_for(report, f["code"])]
    chosen = next(((i, f) for code in _FIRST for i, f in with_rec if f["code"] == code), None)
    if chosen is None and with_rec:
        top = min(_SEVERITY_ORDER.get(f["severity"], 9) for _, f in with_rec)
        at_top = [(i, f) for i, f in with_rec if _SEVERITY_ORDER.get(f["severity"], 9) == top]
        if len(at_top) == 1 and at_top[0][1]["severity"] in ("high", "medium"):
            chosen = at_top[0]
    if chosen is None:
        link = f'<a class="link" href="#improvements">{r.t("decision.next.see")}</a>' if with_rec else ""
        return f'<p class="muted">{r.t("decision.next.none")}</p>{link}'
    index, f = chosen
    action = _rec_html(r, f["code"], _recommendation_for(report, f["code"]), tag="p").replace("<p", '<p class="next-action"', 1)
    return (f"{action}"
            f'<p class="muted"><strong>{r.t("decision.next.because")}</strong> <a href="#finding-{index}">{_finding_title(r, f)}</a></p>')


def _decision_card(r: _Renderer, cls: str, icon: str, title_key: str, count_html: str, items: list[str], empty_key: str) -> str:
    shown = items[:3]
    body = (
        "<ul class=\"list tight\">" + "".join(f"<li>{i}</li>" for i in shown) + "</ul>"
        if shown else f'<p class="muted">{r.t(empty_key)}</p>'
    )
    more = (f'<details class="more"><summary>{r.t("decision.more", n=len(items) - 3)}</summary><ul class="list tight">'
            + "".join(f"<li>{i}</li>" for i in items[3:]) + "</ul></details>") if len(items) > 3 else ""
    return (
        f'<article class="decision {cls}"><h4>{r.icon(icon)}{r.t(title_key)}</h4>'
        f'<p class="decision-count">{count_html}</p>{body}{more}</article>'
    )


def _overview(r: _Renderer) -> str:
    report = r.report
    findings = report["findings"]
    boundary = report["claim_boundary"]
    strengths = _strengths(r, report)
    attention = _attention(r, report)
    not_evidenced = boundary.get("not_evidenced") or []
    decision = (
        f'<section id="decision" aria-labelledby="h-decision" class="sub"><div class="sub-head"><h3 id="h-decision">{r.t("overview.title")}</h3>'
        f'<p class="lead">{r.t("overview.lead")}</p></div><div class="decisions">'
        + _decision_card(r, "d-working", "check", "decision.working",
                         r.t("decision.working.count", n=len(strengths)) if strengths else r.t("decision.working.sub"),
                         strengths, "decision.working.none")
        + _decision_card(r, "d-attention", "alert", "decision.attention", r.t("decision.attention.count", n=len(attention)),
                         attention, "decision.attention.none")
        + _decision_card(r, "d-unknown", "question", "decision.unknown", r.t("decision.unknown.count", n=len(not_evidenced)),
                         [r.canon(v) for v in not_evidenced], "decision.unknown.none")
        + f'<article class="decision d-next"><h4>{r.icon("arrow")}{r.t("decision.next")}</h4>{_next_action(r, report)}</article>'
        + "</div></section>"
    )
    green = _green(r, boundary)
    top = [(i, f) for i, f in _sorted_findings(findings) if f["severity"] in ("high", "medium")][:3]
    top_html = "".join(
        f'<li class="top-finding"><a href="#finding-{i}">{r.pill(f["severity"], prefix="severity.")}{_finding_title(r, f)}</a>'
        + (r.raw_key("f." + f["code"] + ".why", *_finding_meta(f["code"])["why"], tag="p") if _finding_meta(f["code"]).get("why") else "")
        + "</li>"
        for i, f in top
    )
    top_section = (
        f'<section id="top-findings" aria-labelledby="h-top" class="sub"><div class="sub-head"><h3 id="h-top">{r.t("findings.top")}</h3>'
        f'<a class="link" href="#all-findings">{r.t("findings.view_all")}</a></div>'
        + (f'<ul class="top-list">{top_html}</ul>' if top_html else f'<p class="empty">{r.t("findings.none.top")}</p>')
        + "</section>"
    )
    return (
        f'<section id="overview" class="area" aria-labelledby="h-overview"><h2 id="h-overview" class="area-title">{r.t("nav.overview")}</h2>'
        f"{_not_applied(r)}{decision}{_cards(r)}{green}{top_section}{_improvements(r)}</section>"
    )


def _not_applied(r: _Renderer) -> str:
    report = r.report
    if report["workflow"] != "improve" or report["states"].get("applied"):
        return ""
    return f'<div class="banner" role="note">{r.icon("alert")}<p><strong>{r.t("not_applied.banner")}</strong></p></div>'


def _cards(r: _Renderer) -> str:
    report = r.report
    findings = report["findings"]
    cards = []
    runs = [(k, run) for k, s in _states(report) for run in s.get("runs", [])]
    executed = [run for _, run in runs if run["mode"] != "report"]
    ingested = [run for _, run in runs if run["mode"] == "report"]
    mode = ("evmode.executed_ingested" if executed and ingested else "evmode.executed" if executed
            else "evmode.ingested" if ingested else "evmode.static")
    sub = {"evmode.static": "evmode.static.sub", "evmode.executed": "evmode.executed.sub", "evmode.ingested": "evmode.ingested.sub",
           "evmode.executed_ingested": "evmode.executed.sub"}[mode]
    cards.append(("card.mode", f'<p class="card-value">{r.t(mode)}</p><p class="card-sub">{r.t(sub)}</p>'))
    if runs:
        total = sum(run["invocations"] for _, run in runs)
        cards.append(("card.execution", f'<p class="card-value num">{total} <small>{r.t("card.invocations")}</small></p>'
                                        f'<p class="card-sub">{r.t("card.execution.sub", n=len(runs))}</p>'))
    else:
        cards.append(("card.execution", f'<p class="card-value">{r.t("card.execution.none")}</p><p class="card-sub">{r.t("card.execution.none.sub")}</p>'))
    if report["workflow"] == "audit" or findings:
        counts = {s: sum(f["severity"] == s for f in findings) for s in ("high", "medium", "info")}
        bars = "".join(
            f'<li class="sev-{s}">{r.pill(s, prefix="severity.")}<span class="num">{counts[s]}</span></li>' for s in counts if counts[s]
        )
        cards.append(("card.findings", f'<p class="card-value num">{len(findings)}</p>'
                                       + (f'<ul class="sev-list">{bars}</ul>' if bars else f'<p class="card-sub">{r.t("card.findings.none")}</p>')))
    q = report.get("candidate_qualification")
    if q:
        checks = [c for s in q["stages"] for c in s["checks"]]
        passed = sum(c["status"] == "PASS" for c in checks)
        cards.append(("qual.ready", f'<p class="card-value">{r.t("yes" if q["ready_for_review"] else "no")}</p>'
                                    f'<p class="card-sub num">{r.t("finding.of", a=passed, b=len(checks))} {r.pill("PASS")}</p>'))
    delta = report.get("evidence_delta")
    if delta:
        parts = "".join(f'<li>{r.pill(k)}<span class="num">{len(v)}</span></li>' for k, v in delta.items() if v)
        cards.append(("delta.title", f'<ul class="sev-list">{parts}</ul>'))
    not_evidenced = report["claim_boundary"].get("not_evidenced") or []
    cards.append(("card.unknowns", f'<p class="card-value num">{len(not_evidenced)}</p><p class="card-sub">{r.t("card.unknowns.sub")}</p>'))
    checks = report.get("verification_surface") or []
    cards.append(("card.checks", f'<p class="card-value num">{len(checks)}</p><p class="card-sub">{r.t("card.checks.sub")}</p>'))
    body = "".join(f'<article class="card"><h4 class="card-title">{r.t(title)}</h4>{content}</article>' for title, content in cards)
    return (f'<section id="summary" aria-labelledby="h-summary" class="sub"><div class="sub-head"><h3 id="h-summary">{r.t("cards.title")}</h3></div>'
            f'<div class="cards">{body}</div></section>')


def _green(r: _Renderer, boundary: dict) -> str:
    def column(cls: str, icon: str, title: str, sub: str, values: list[str], empty: str) -> str:
        return (f'<article class="claim {cls}"><h4>{r.icon(icon)}{r.t(title)}</h4><p class="claim-sub">{r.t(sub)}</p>'
                f'{r.items(values, empty)}</article>')
    return (
        f'<section id="green" aria-labelledby="h-green" class="sub green"><div class="sub-head"><h3 id="h-green">{r.t("green.title")}</h3>'
        f'<p class="lead">{r.t("green.lead")}</p></div><div class="claims">'
        + column("c-observed", "check", "green.observed", "green.observed.sub", boundary.get("observed") or [], "green.observed.none")
        + column("c-not", "question", "green.not", "green.not.sub", boundary.get("not_evidenced") or [], "green.not.none")
        + column("c-limits", "info", "green.limits", "green.limits.sub", boundary.get("limitations") or [], "green.limits.none")
        + "</div></section>"
    )


def _improvements(r: _Renderer) -> str:
    report = r.report
    recs = report.get("recommendations") or []
    by_code = {f["code"]: (i, f) for i, f in enumerate(report["findings"])}
    groups: dict[str, list[str]] = {}
    for rec in recs:
        index, f = by_code.get(rec["finding"], (None, {"code": rec["finding"], "severity": "medium", "summary": ""}))
        meta = _finding_meta(rec["finding"])
        close = meta.get("close")
        item = (
            f'<li class="improvement"><div class="imp-head">{r.pill(rec.get("status") or "PROPOSED")}'
            f'{_rec_html(r, rec["finding"], rec["recommendation"], tag="p")}</div>'
            f'<p class="imp-meta"><span>{r.t("improve.related")}:</span> '
            + (f'<a href="#finding-{index}">{_finding_title(r, f)}</a>' if index is not None else f"<code>{_e(rec['finding'])}</code>")
            + f' {r.pill(f["severity"], prefix="severity.")}{r.tier(meta.get("tier"))}<code class="f-code">{_e(rec["finding"])}</code></p>'
            + (f'<p class="imp-close"><strong>{r.t("improve.closes")}:</strong> {r.raw_key("f." + rec["finding"] + ".close", close[0], close[1])}</p>' if close else "")
            + "</li>"
        )
        groups.setdefault(_category(rec["finding"]), []).append(item)
    order = ["tests", "negative", "coverage", "mutation", "execution", "discovery", "delivery", "artifact", "project", "other"]
    body = "".join(
        f'<div class="imp-group"><h4>{r.t(f"cat.{cat}")}</h4><ul class="imp-list">{"".join(groups[cat])}</ul></div>'
        for cat in order if cat in groups
    )
    return (
        f'<section id="improvements" aria-labelledby="h-improve" class="sub"><div class="sub-head"><h3 id="h-improve">{r.t("improve.title")}</h3>'
        f'<p class="lead">{r.t("improve.lead")}</p></div>'
        + (body or f'<p class="empty">{r.t("improve.none")}</p>') + "</section>"
    )


# --- evidence ---------------------------------------------------------------------------

def _metric_label(r: _Renderer, name: str) -> str:
    entry = METRICS.get(name)
    if entry:
        return r.raw_key(f"m.{name}", entry[0], entry[1], cls="m-name")
    return f'<span class="m-name">{_e(_humanize(name))}</span>'


def _metrics(r: _Renderer) -> str:
    report = r.report
    states = _states(report)
    if not states:
        return f'<p class="empty">{r.t("metrics.none_state")}</p>'
    order = {name: i for i, name in enumerate(METRICS)}
    names = sorted({name for _, s in states for name in s["metrics"]}, key=lambda n: (order.get(n, len(order)), n))
    if not names:
        return f'<p class="empty">{r.t("metrics.none")}</p>'
    delta = {d["name"]: bucket for bucket, items in (report.get("evidence_delta") or {}).items() for d in items}
    notes = {d["name"]: d.get("note") for items in (report.get("evidence_delta") or {}).values() for d in items}
    show_delta = bool(report.get("evidence_delta"))
    groups: dict[str, list[str]] = {}
    for name in names:
        group = METRIC_GROUPS.get(name) or ("coverage" if "coverage" in name or name.endswith(("_covered", "_total")) else "other")
        groups.setdefault(group, []).append(name)
    head = "".join(
        f'<th scope="col" class="num-col">{r.state(k)}<span class="th-note">{r.t(f"state.note.{k}")}</span></th>' for k, _ in states
    )
    tables = []
    for group in ("execution", "coverage", "static", "fault", "artifact", "other"):
        if group not in groups:
            continue
        rows = []
        for name in groups[group]:
            first = next(s["metrics"][name] for _, s in states if name in s["metrics"])
            cells = "".join(
                f'<td class="num-col" data-label="{_e(r.text(f"state.{k}"))}">{_meter(s["metrics"].get(name))}{_e(_fmt_value(s["metrics"].get(name)))}</td>'
                for k, s in states
            )
            direction = first.get("direction") or ""
            dir_html = r.t(f"dir.{direction}") if f"dir.{direction}" in UI else _e(direction)
            delta_cell = ""
            if show_delta:
                state = delta.get(name, "")
                delta_cell = (f'<td data-label="{_e(r.text("metrics.delta"))}">{r.pill(state) if state else ""}'
                              + (f'<span class="th-note" lang="en">{_e(notes[name])}</span>' if notes.get(name) else "") + "</td>")
            rows.append(
                f'<tr><th scope="row">{_metric_label(r, name)}<code class="m-id">{_e(name)}</code></th>{cells}'
                f'<td data-label="{_e(r.text("metrics.direction"))}"><span class="dir">{dir_html}</span> {r.tier(first.get("evidence_tier"))}</td>{delta_cell}</tr>'
            )
        delta_head = f'<th scope="col">{r.t("metrics.delta")}</th>' if show_delta else ""
        cols = '<col class="c-metric">' + '<col class="c-value">' * len(states) + '<col class="c-dir">' + ('<col class="c-delta">' if show_delta else "")
        tables.append(
            f'<div class="table-wrap"><table class="metrics responsive"><colgroup>{cols}</colgroup><caption>{r.t(f"metrics.group.{group}")}</caption>'
            f'<thead><tr><th scope="col">{r.t("metrics.metric")}</th>{head}<th scope="col">{r.t("metrics.direction")}</th>{delta_head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        )
    sources = [
        f'<li>{r.state(k)}: <span lang="en">' + _e(f"{c.get('tool') or 'unknown tool'}" + (f" ({c['scope']})" if c.get("scope") else "")
                                                 + (f" — {c['error']}" if c.get("error") else "") + "".join(f"; {lim}" for lim in c.get("limitations") or ()))
        + "</span></li>"
        for k, s in states for c in s.get("coverage") or []
    ]
    coverage = f'<div class="muted"><strong>{r.t("metrics.coverage_sources")}</strong><ul class="list tight">{"".join(sources)}</ul></div>' if sources else ""
    return f'<p class="sr-note">{r.t("metrics.caption")}</p>' + "".join(tables) + coverage + _chart(r, states, names)


def _meter(metric: dict | None) -> str:
    """Decorative bar for percentages; the number next to it is the information."""
    if not metric or metric.get("unit") != "%" or not isinstance(metric.get("value"), (int, float)):
        return ""
    width = max(0.0, min(100.0, float(metric["value"])))
    return f'<span class="meter" aria-hidden="true"><span style="width:{width:.1f}%"></span></span>'


def _chart(r: _Renderer, states: list, names: list[str]) -> str:
    if len(states) < 2:
        return ""
    plotted = [
        n for n in names
        if all(n in s["metrics"] and s["metrics"][n]["value"] is not None for _, s in states)
        and states[0][1]["metrics"][n]["direction"] in ("HIGHER_IS_BETTER", "LOWER_IS_BETTER")
        and any(s["metrics"][n]["value"] for _, s in states)
    ]
    if not plotted:
        return ""
    bar_h, label_h, gap, width = 14, 18, 16, 720
    height = len(plotted) * (label_h + len(states) * bar_h + gap) + gap
    parts, y = [], gap
    for name in plotted:
        values = [s["metrics"][name]["value"] for _, s in states]
        scale = 100.0 if states[0][1]["metrics"][name]["unit"] == "%" else (max(values) or 1)
        entry = METRICS.get(name)
        label = (r.raw_key(f"m.{name}", entry[0], entry[1], tag="text") if entry else f"<text>{_e(_humanize(name))}</text>")
        parts.append(label.replace("<text", f'<text x="0" y="{y + 12}" class="lbl"', 1))
        y += label_h
        for (key, state), value in zip(states, values):
            w = max(2.0, (width - 90) * float(value) / float(scale))
            parts.append(f'<rect x="0" y="{y}" width="{w:.1f}" height="{bar_h - 4}" rx="3" class="bar {key}"></rect>')
            parts.append(f'<text x="{w + 8:.1f}" y="{y + bar_h - 5}" class="val">{_e(_fmt_value(state["metrics"][name]))}</text>')
            y += bar_h
        y += gap
    legend = "".join(f'<span class="legend-item"><span class="swatch {k}" aria-hidden="true"></span>{r.state(k)}</span>' for k, _ in states)
    return (
        f'<figure class="chart"><svg role="img" aria-labelledby="chart-title" viewBox="0 0 {width} {height}" width="100%" style="max-width:{width}px">'
        f'<title id="chart-title">{_e(r.text("chart.title"))}</title>{"".join(parts)}</svg>'
        f'<figcaption>{legend}<span class="muted">{r.t("chart.caption")}</span></figcaption></figure>'
    )


def _delta(r: _Renderer) -> str:
    delta = r.report.get("evidence_delta")
    if not delta:
        return ""
    columns = "".join(
        f'<article class="delta-col"><h4>{r.pill(bucket)}<span class="num">{len(items)}</span></h4>'
        + ("<ul class=\"list tight\">" + "".join(f"<li>{_metric_label(r, d['name'])}</li>" for d in items) + "</ul>" if items else "")
        + "</article>"
        for bucket, items in delta.items()
    )
    return (f'<section id="delta" aria-labelledby="h-delta" class="sub"><div class="sub-head"><h3 id="h-delta">{r.t("delta.title")}</h3>'
            f'<p class="lead">{r.t("delta.lead")}</p></div><div class="delta-grid">{columns}</div></section>')


def _sub(r: _Renderer, sid: str, title_key: str, body: str, lead_key: str | None = None, title_html: str | None = None) -> str:
    lead = f'<p class="lead">{r.t(lead_key)}</p>' if lead_key else ""
    return (f'<section id="{sid}" aria-labelledby="h-{sid}" class="sub"><div class="sub-head"><h3 id="h-{sid}">{title_html or r.t(title_key)}</h3>{lead}</div>'
            f"{body}</section>")


def _negative(r: _Renderer) -> str:
    states = [(k, s) for k, s in _states(r.report) if s.get("negative_paths")]
    if not states:
        return ""
    tests = sorted({t for _, s in states for t in s["negative_paths"]})
    head = "".join(f'<th scope="col">{r.state(k)}</th>' for k, _ in states)
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(t)}</code></th>'
        + "".join(
            f'<td data-label="{_e(r.text(f"state.{k}"))}">'
            + (" ".join(f'<span class="tag">{_e(d)}</span>' for d in s["negative_paths"][t]) or f'<span class="muted">{r.t("neg.any")}</span>'
               if t in s["negative_paths"] else "—")
            + "</td>" for k, s in states)
        + "</tr>"
        for t in tests
    )
    table = (f'<div class="table-wrap"><table class="responsive"><caption>{r.t("neg.caption")}</caption><thead><tr><th scope="col">{r.t("neg.test")}</th>{head}</tr></thead>'
             f"<tbody>{rows}</tbody></table></div>")
    if len(tests) > 12:
        table = f'<details class="more"><summary>{r.t("show_all", n=len(tests))}</summary>{table}</details>'
    return _sub(r, "negative-paths", "neg.title", table, "neg.lead")


def _mutation(r: _Renderer) -> str:
    rows = []
    for key, state in _states(r.report):
        for run in state.get("mutation", []):
            counts = ", ".join(f"{k.lower()}: {v}" for k, v in sorted(run["counts"].items())) or "—"
            status = (f'{r.t("mut.unreadable")}: <span lang="en">{_e(run["error"])}</span>' if run["error"]
                      else r.t("mut.mismatch") if run["matches_state"] is False else f"<code>{_e(counts)}</code>")
            survivors = (r.items(run["survivors"], "mut.none_listed" if run["per_mutant"] else "mut.no_identity", canon=False)
                         if run["survivors"] else f'<p class="muted">{r.t("mut.none_listed" if run["per_mutant"] else "mut.no_identity")}</p>')
            rows.append(
                f'<tr><th scope="row">{r.state(key)}</th><td data-label="{_e(r.text("mut.tool"))}">{_e(run["tool"] or "unknown")}</td>'
                f'<td data-label="{_e(r.text("mut.result"))}">{status}</td><td data-label="{_e(r.text("mut.survivors"))}">{survivors}</td>'
                f'<td data-label="{_e(r.text("green.limits"))}">{r.items(run["limitations"], "none")}</td></tr>'
            )
    if not rows:
        return ""
    table = (f'<div class="table-wrap"><table class="responsive"><caption>{r.t("mut.caption")}</caption><thead><tr><th scope="col">{r.t("prov.state")}</th>'
             f'<th scope="col">{r.t("mut.tool")}</th><th scope="col">{r.t("mut.result")}</th><th scope="col">{r.t("mut.survivors")}</th>'
             f'<th scope="col">{r.t("green.limits")}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return _sub(r, "mutation-evidence", "mut.title", table, "mut.lead")


def _artifacts(r: _Renderer) -> str:
    cards = []
    for key, state in _states(r.report):
        for a in state.get("artifacts", []):
            checks = "".join(f'<li>{r.pill(c["status"])} <span lang="en">{_e(c["name"])}: {_e(c["detail"])}</span></li>' for c in a["checks"])
            built = f'<code>{_e(a["artifact"])}</code>' if a["artifact"] else r.t("art.not_built")
            fidelity = (f'<p class="muted">{r.t("art.proves")}: <span lang="en">'
                        + _e(", ".join(f"{k.lower().replace('_', ' ')} {v}" for k, v in a.get("fidelity", {}).items())) + "</span></p>"
                        if a.get("fidelity") else "")
            omitted = (f'<p class="muted">{r.t("art.missing")}: <code>{_e(", ".join(a["omitted_files"][:10]))}</code></p>' if a["omitted_files"] else "")
            cards.append(
                f'<article class="panel"><div class="panel-head">{r.state(key)}{r.pill(a["status"])}</div>'
                f'<p><strong>{_e(a["kind"])}</strong> {built}</p>'
                f'<p class="muted">sha256 <code>{_e((a["sha256"] or "—")[:16])}</code></p><ul class="list tight">{checks}</ul>{fidelity}'
                f'{r.items(a["limitations"], "none") if a["limitations"] else ""}{omitted}</article>'
            )
    if not cards:
        return ""
    return _sub(r, "artifact-evidence", "art.title", f'<div class="panels">{"".join(cards)}</div>', "art.lead")


def _delivery(r: _Renderer) -> str:
    report = r.report
    delivery = report.get("delivery")
    review = report.get("review_candidates") or []
    if not delivery and not review:
        return ""
    matrix = (delivery or {}).get("matrix") or {}
    declared = [f'{dim}: {", ".join(info["values"])} ({info["source"]})' for dim, info in sorted((matrix.get("declared") or {}).items())]
    ci = [f'{dim}: {", ".join(values)}' for dim, values in sorted((matrix.get("ci") or {}).items())]
    lineage = [f'{item["artifact"]} sha256 {(item["sha256"] or "?")[:12]} · tested {item["tested"]} · published {item["published"] if isinstance(item["published"], str) else len(item["published"])} '
               f'· deployed {item["deployed"] if isinstance(item["deployed"], str) else len(item["deployed"])}' for item in (delivery or {}).get("artifact_lineage") or []]
    candidates = [f'{c["kind"]}: {c["subject"]} — {c["tests"]} test(s), e.g. {", ".join(c["examples"][:3])}' for c in review]
    body = (
        '<div class="panels">'
        f'<article class="panel"><h4>{r.t("delivery.declared")}</h4>{r.items(declared, "delivery.declared.none")}</article>'
        f'<article class="panel"><h4>{r.t("delivery.ci")}</h4>{r.items(ci, "delivery.ci.none")}</article>'
        f'<article class="panel"><h4>{r.t("delivery.lineage")}</h4>{r.items(lineage, "delivery.lineage.none")}</article>'
        f'<article class="panel"><h4>{r.t("delivery.review")}</h4><p class="muted">{r.t("delivery.review.note")}</p>{r.items(candidates, "none")}</article>'
        "</div>"
    )
    return _sub(r, "delivery", "delivery.title", body)


def _selection(r: _Renderer) -> str:
    selection = r.report.get("test_selection")
    if not selection:
        return ""
    counts = selection["counts"]
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(test)}</code></th><td data-label="{_e(r.text("sel.reason"))}" lang="en">{_e(reasons[0]["reason"])}</td>'
        f'<td data-label="{_e(r.text("sel.tier"))}"><code>{_e(reasons[0]["tier"] or reasons[0]["trigger"] or "")}</code></td>'
        f'<td data-label="{_e(r.text("sel.path"))}"><code>{_e(" → ".join(reasons[0]["path"]))}</code></td></tr>'
        for test, reasons in sorted(selection["selected"].items())[:200]
    )
    widening = [f'{w["trigger"]}{" (full suite)" if w["full"] else ""}: {w["path"] or ""} {w["reason"]}'.strip() for w in selection["widening"]]
    unknowns = [f'{u["node"]}: {u["reason"]}' for u in selection["unknown_dependencies"]]
    affected = sorted((selection.get("affected_components") or {}).items())
    components = f'<h4>{r.t("sel.components")}</h4>{r.items([f"{n}: {why}" for n, why in affected], "none")}' if affected else ""
    body = (
        f'<p class="meta-row"><span>{r.t("sel.base")} <code>{_e(selection["base"] or "none")}</code></span>'
        f'<span>{r.t("sel.changed", n=len(selection["changes"]))}</span>'
        f'<span>{r.t("sel.confidence")} {r.pill(selection["confidence"], show_raw=True)}</span>'
        f'<span>{r.t("sel.selected", a=counts["selected"], b=counts["mapped"])}</span>'
        + (f'<span lang="en">{_e(selection["fallback"])}</span>' if selection["fallback"] else "") + "</p>"
        + components
        + f'<div class="panels"><article class="panel"><h4>{r.t("sel.widening")}</h4>{r.items(widening, "sel.widening.none")}</article>'
        f'<article class="panel"><h4>{r.t("sel.unknowns")}</h4>{r.items(unknowns, "sel.unknowns.none")}</article></div>'
        f'<div class="table-wrap"><table class="responsive"><caption>{r.t("sel.caption")}</caption><thead><tr><th scope="col">{r.t("neg.test")}</th>'
        f'<th scope="col">{r.t("sel.reason")}</th><th scope="col">{r.t("sel.tier")}</th><th scope="col">{r.t("sel.path")}</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
        + (f'<p class="muted" lang="en">{_e(selection["limitations"][0])}</p>' if selection["limitations"] else "")
    )
    return _sub(r, "selection", "sel.title", body)


def _history(r: _Renderer) -> str:
    history = r.report.get("history")
    if not history:
        return ""
    if not history.get("enabled"):
        return _sub(r, "history", "hist.title", r.items(history.get("limitations") or [], "hist.unused"))
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(e["invocation_id"])}</code></th><td data-label="{_e(r.text("hist.stability"))}">{r.pill(e["stability"], show_raw=True)}</td>'
        f'<td data-label="{_e(r.text("finding.evidence"))}" lang="en">{_e(e["note"])}</td>'
        f'<td data-label="{_e(r.text("hist.signature"))}"><code>{_e(e["failure_signature"] or "")}</code></td>'
        f'<td data-label="{_e(r.text("hist.same"))}" class="num-col">{e["fingerprint_occurrences"] or ""}</td></tr>'
        for e in history["invocations"]
    )
    table = (f'<div class="table-wrap"><table class="responsive"><caption>{r.t("hist.caption")}</caption><thead><tr><th scope="col">{r.t("hist.invocation")}</th>'
             f'<th scope="col">{r.t("hist.stability")}</th><th scope="col">{r.t("finding.evidence")}</th><th scope="col">{r.t("hist.signature")}</th>'
             f'<th scope="col">{r.t("hist.same")}</th></tr></thead><tbody>{rows}</tbody></table></div>') if rows else f'<p class="empty">{r.t("hist.none")}</p>'
    timings = [f'{t["invocation_id"]}: p50 {t["p50"]}s' + (f', p95 {t["p95"]}s' if t["p95"] is not None else "") + f' ({t["samples"]} samples)'
               for t in history["durations"]]
    previous = history.get("previous_state")
    earlier = []
    if previous:
        coverage = ", ".join(f'{kind} {c["covered"]}/{c["total"]}' for kind, c in ((previous.get("coverage") or {}).get("counts") or {}).items())
        artifacts = ", ".join(f'{a["artifact"]} sha256 {(a["sha256"] or "?")[:12]} {a["status"]}' for a in previous.get("artifacts") or [])
        pillars = ", ".join(f"{k} {v}" for k, v in (previous.get("qualification") or {}).items())
        earlier = [f'recorded {previous["recorded_at"]} at revision {previous["revision"][:12]}',
                   *([f"coverage: {coverage}"] if coverage else []), *([f"artifacts: {artifacts}"] if artifacts else []),
                   *([f"qualification: {pillars}"] if pillars else [])]
    body = (
        f'<p>{r.t("hist.states", n=history["states_recorded"])}</p>{table}'
        f'<div class="panels"><article class="panel"><h4>{r.t("hist.previous")}</h4>{r.items(earlier, "hist.previous.none")}</article>'
        f'<article class="panel"><h4>{r.t("hist.durations")}</h4>{r.items(timings, "hist.durations.none")}</article></div>'
        + (r.items(history["limitations"], "none") if history["limitations"] else "")
    )
    return _sub(r, "history", "hist.title", body)


def _qualification(r: _Renderer) -> str:
    q = r.report.get("candidate_qualification")
    if not q:
        return ""
    stages = []
    for s in q["stages"]:
        name = r.t(f"q.{s['stage']}") if f"q.{s['stage']}" in UI else _e(_humanize(s["stage"]))
        checks = "".join(
            f'<li class="check-row">{r.pill(c["status"])}<span class="qcheck-name">'
            + (r.t(f"q.{c['check']}") if f"q.{c['check']}" in UI else _e(_humanize(c["check"])))
            + f'</span><span class="check-sum" lang="en">{_e(c["summary"])}</span>'
            + (f'<details class="more check-lims"><summary>{r.t("green.limits")} ({len(c["limitations"])})</summary>'
               f'{r.items(c["limitations"], "none", limit=50)}</details>' if c["limitations"] else "") + "</li>"
            for c in s["checks"]
        )
        stages.append(f'<article class="panel stage"><div class="panel-head"><h4>{name}</h4>{r.pill(s["status"], show_raw=True)}</div>'
                      f'<ul class="checks">{checks}</ul></article>')
    records = (q.get("stability") or {}).get("records") or []
    reruns = ""
    if records:
        rows = "".join(
            f'<tr><th scope="row"><code>{_e(rec["invocation_id"])}</code></th><td data-label="{_e(r.text("qual.outcomes"))}"><code>{_e(" / ".join(o or "?" for o in rec["outcomes"]))}</code></td>'
            f'<td data-label="{_e(r.text("qual.durations"))}" class="num-col">{_e(" / ".join(f"{d:.3f}s" if d is not None else "?" for d in rec["durations_s"]))}</td>'
            f'<td data-label="{_e(r.text("qual.verdict"))}">{r.pill(rec["verdict"], show_raw=True)}</td></tr>'
            for rec in records
        )
        reruns = (f'<div class="table-wrap"><table class="responsive"><caption>{r.t("qual.reruns")}</caption><thead><tr><th scope="col">{r.t("hist.invocation")}</th>'
                  f'<th scope="col">{r.t("qual.outcomes")}</th><th scope="col">{r.t("qual.durations")}</th><th scope="col">{r.t("qual.verdict")}</th></tr></thead>'
                  f"<tbody>{rows}</tbody></table></div>")
        if len(records) > 12:
            reruns = f'<details class="more"><summary>{r.t("show_all", n=len(records))}</summary>{reruns}</details>'
    body = (f'<p class="meta-row"><span>{r.t("qual.ready")}: <strong>{r.t("yes" if q["ready_for_review"] else "no")}</strong></span></p>'
            f'<div class="panels stages">{"".join(stages)}</div>{reruns}')
    return _sub(r, "qualification", "qual.title", body, "qual.lead")


def _changes(r: _Renderer) -> str:
    cs = r.report.get("change_set")
    if not cs:
        return ""
    applied = set(cs.get("applied") or [])
    items = "".join(
        f'<details class="change"><summary>{r.pill(c["kind"], show_raw=True)}<code class="path">{_e(c["path"])}</code>'
        f'{r.pill("APPLIED") if c["change_id"] in applied else r.t("changes.not_applied", cls="pill not_run tone-not_run")}{r.chev()}</summary>'
        f'<p lang="en">{_e(c["reason"])}</p>'
        f'<p class="muted">{r.t("changes.fingerprints", a=(c["original_fingerprint"] or "none")[:12], b=(c["candidate_fingerprint"] or "none")[:12])}</p>'
        f'<pre class="code diff">{_e(c["diff"])}</pre></details>'
        for c in cs["changes"]
    )
    return _sub(r, "changes", "changes.title", items or f'<p class="empty">{r.t("changes.none")}</p>', "changes.lead")


def _evidence(r: _Renderer) -> str:
    metrics = _sub(r, "metrics", "metrics.title", _metrics(r))
    return (
        f'<section id="evidence" class="area" aria-labelledby="h-evidence"><h2 id="h-evidence" class="area-title">{r.t("nav.evidence")}</h2>'
        f'<p class="lead area-lead">{r.t("evidence.lead")}</p>'
        f"{_qualification(r)}{_changes(r)}{metrics}{_delta(r)}{_negative(r)}{_mutation(r)}{_artifacts(r)}"
        f"{_delivery(r)}{_selection(r)}{_history(r)}</section>"
    )


# --- verification -----------------------------------------------------------------------

def _copy_button(r: _Renderer) -> str:
    return f'<button type="button" class="copy" {r.attr("aria-label", "copy.label")}>{r.icon("copy")}{r.t("copy")}</button>'


def _surface(r: _Renderer) -> str:
    checks = r.report.get("verification_surface") or []
    if not checks:
        return _sub(r, "surface-section", "surface.title", f'<p class="empty">{r.t("surface.none")}</p>', "surface.lead")
    origins: dict[str, list[dict]] = {}
    for c in checks:
        origins.setdefault(c["origin"], []).append(c)
    order = ["LOCAL", "HOOK", "CI", "BUILD", "PACKAGE", "DEPLOY", "DECLARED", "UNKNOWN"]
    groups = []
    chev = r.chev()
    for origin in sorted(origins, key=lambda o: order.index(o) if o in order else len(order)):
        rows = []
        for c in origins[origin]:
            meta = c.get("metadata") or {}
            name = c.get("tool") or (c.get("command") or c["check_id"]).split("\n")[0][:60]
            where = " · ".join(str(v) for v in (meta.get("job"), meta.get("step"), meta.get("script")) if v)
            lifecycle = meta.get("lifecycle") or {}
            kind_label = r.t(f"kind.{c['kind']}") if f"kind.{c['kind']}" in UI else _e(_humanize(c["kind"]))
            gate_label = r.t(f"gate.{c['gate']}") if f"gate.{c['gate']}" in UI else _e(c["gate"])
            details = []
            if c.get("command"):
                details.append(f'<div class="cmd"><div class="cmd-head"><span>{r.t("surface.command")}</span>{_copy_button(r)}</div>'
                               f'<pre class="code"><code>{_e(c["command"])}</code></pre></div>')
            details.append(f'<dl class="kv"><dt>{r.t("surface.check")}</dt><dd><code>{_e(c["check_id"])}</code></dd>'
                           + (f'<dt>{r.t("surface.source")}</dt><dd><code>{_e(c["source"])}</code></dd>' if c.get("source") else "")
                           + f'<dt>{r.t("surface.gate")}</dt><dd><code>{_e(c["gate"])}</code></dd>'
                           + (f'<dt>{r.t("surface.lifecycle")}</dt><dd><code>{_e(", ".join(f"{k}: {v}" for k, v in lifecycle.items()))}</code></dd>' if lifecycle else "")
                           + "</dl>")
            if c.get("limitations"):
                details.append(f'<h5>{r.t("surface.limitations")}</h5>{r.items(list(c["limitations"]), "none")}')
            rows.append(
                f'<li class="check" data-kind="{_e(c["kind"])}"><details><summary>'
                f'<span class="kind kind-{_e(c["kind"].lower())}">{kind_label}</span>'
                f'<span class="check-title"><span class="check-name">{_e(name)}</span>'
                + (f'<span class="check-where">{_e(where)}</span>' if where else "")
                + f'</span><span class="check-tags"><span class="gate gate-{_e(c["gate"].lower())}">{gate_label}</span>{r.tier(c.get("evidence_tier"))}</span>'
                f'{chev}</summary><div class="check-body">{"".join(details)}</div></details></li>'
            )
        label = r.t(f"origin.{origin}") if f"origin.{origin}" in UI else _e(origin)
        groups.append(f'<article class="origin"><h4 class="origin-head">{label}<span class="count">{r.t("surface.checks", n=len(origins[origin]))}</span></h4>'
                      f'<ul class="check-list">{"".join(rows)}</ul></article>')
    kinds = sorted({c["kind"] for c in checks})
    options = "".join(f'<option value="{_e(k)}" data-i18n="kind.{_e(k)}">{_e(r.text(f"kind.{k}") if f"kind.{k}" in UI else k)}</option>' for k in kinds)
    table_rows = "".join(
        f'<tr data-kind="{_e(c["kind"])}"><th scope="row"><code>{_e(c["check_id"])}</code></th><td data-label="{_e(r.text("surface.kind"))}">{_e(c["kind"])}</td>'
        f'<td data-label="{_e(r.text("surface.origin"))}">{_e(c["origin"])}</td><td data-label="{_e(r.text("surface.gate"))}">{_e(c["gate"])}</td>'
        f'<td data-label="{_e(r.text("surface.command"))}"><code class="wrap">{_e(c["command"] or c["tool"] or "")}</code></td>'
        f'<td data-label="{_e(r.text("surface.tier"))}">{_e(c["evidence_tier"])}</td>'
        f'<td data-label="{_e(r.text("surface.limitations"))}" lang="en">{_e("; ".join(c["limitations"]))}</td></tr>'
        for c in checks
    )
    body = (
        f'<div class="filters"><label for="kind">{r.t("surface.filter.kind")}</label><select id="kind" class="select">'
        f'<option value="" data-i18n="surface.filter.all">{_e(r.text("surface.filter.all"))}</option>{options}</select></div>'
        f'<div class="origins">{"".join(groups)}</div>'
        f'<details class="more table-view"><summary>{r.t("surface.table")}</summary><div class="table-wrap"><table id="surface" class="responsive">'
        f'<caption>{r.t("surface.caption")}</caption><thead><tr><th scope="col">{r.t("surface.check")}</th><th scope="col">{r.t("surface.kind")}</th>'
        f'<th scope="col">{r.t("surface.origin")}</th><th scope="col">{r.t("surface.gate")}</th><th scope="col">{r.t("surface.command")}</th>'
        f'<th scope="col">{r.t("surface.tier")}</th><th scope="col">{r.t("surface.limitations")}</th></tr></thead><tbody>{table_rows}</tbody></table></div></details>'
    )
    return _sub(r, "surface-section", "surface.title", body, "surface.lead")


def _runs(r: _Renderer) -> str:
    cards = []
    for key, state in _states(r.report):
        for run in state.get("runs", []):
            how = r.t("runs.ingested") if run["mode"] == "report" else r.t("runs.executed", where=state["observed_in"])
            matrix = "".join(f'<li><span lang="en">{_e(name)}</span> <code class="raw">{_e(value)}</code></li>' for name, value in (run.get("matrix") or {}).items())
            command = " ".join(run["command"]) if isinstance(run["command"], list) else str(run["command"] or "")
            cards.append(
                f'<article class="panel run"><div class="panel-head"><span class="run-title"><strong>{_e(run["adapter"])}</strong> · {r.state(key)}</span>'
                f'{r.pill(run["status"], show_raw=True)}</div><p class="muted">{how}</p>'
                f'<dl class="kv"><dt>{r.t("runs.invocations")}</dt><dd class="num">{_e(run["invocations"])}</dd>'
                + (f'<dt>{r.t("runs.exit")}</dt><dd><code>{_e(run["exit_code"])}</code></dd>' if run.get("exit_code") is not None else "")
                + (f'<dt>{r.t("runs.attachments")}</dt><dd class="num">{_e(run["attachments"])}</dd>' if run.get("attachments") else "")
                + "</dl>"
                + (f'<h5>{r.t("runs.matrix")}</h5><ul class="matrix">{matrix}</ul>' if matrix else "")
                + (f'<div class="cmd"><div class="cmd-head"><span>{r.t("surface.command")}</span>{_copy_button(r)}</div><pre class="code"><code>{_e(command)}</code></pre></div>' if command else "")
                + (r.items(run["limitations"], "none") if run.get("limitations") else "")
                + "</article>"
            )
    body = f'<div class="panels">{"".join(cards)}</div>' if cards else f'<p class="empty">{r.t("runs.none")}</p>'
    return _sub(r, "runs", "runs.title", body)


def _budget(r: _Renderer) -> str:
    budget = r.report.get("execution_budget")
    if not budget:
        return ""
    rows = "".join(
        f'<li class="budget-row">{r.pill(d["decision"], show_raw=True)}<span class="budget-stage"><code>{_e(d["stage"])}</code></span>'
        f'<span class="budget-reason" lang="en">{_e(d["reason"])}</span></li>'
        for d in budget["decisions"]
    )
    body = (f'<p class="meta-row"><span>{r.t("budget.level", l=budget["level"], d=budget["depth"], m=budget["max_depth"])}</span></p>'
            f'<ul class="budget">{rows}</ul>')
    return _sub(r, "budget", "budget.title", body, "budget.lead")


def _verification(r: _Renderer) -> str:
    return (f'<section id="verification" class="area" aria-labelledby="h-verification"><h2 id="h-verification" class="area-title">{r.t("nav.verification")}</h2>'
            f"{_surface(r)}{_runs(r)}{_budget(r)}</section>")


# --- details ----------------------------------------------------------------------------

def _all_findings(r: _Renderer) -> str:
    report = r.report
    findings = report["findings"]
    if not findings and report["workflow"] != "audit":
        return ""
    cards = "".join(_finding_card(r, i, f) for i, f in _sorted_findings(findings))
    categories = sorted({_category(f["code"]) for f in findings})
    sev_options = "".join(f'<option value="{s}" data-i18n="severity.{s}">{_e(r.text(f"severity.{s}"))}</option>' for s in ("high", "medium", "info"))
    cat_options = "".join(f'<option value="{c}" data-i18n="cat.{c}">{_e(r.text(f"cat.{c}"))}</option>' for c in categories)
    filters = (
        f'<div class="filters" role="search"><label for="sev">{r.t("findings.filter.severity")}</label>'
        f'<select id="sev" class="select"><option value="" data-i18n="findings.filter.all">{_e(r.text("findings.filter.all"))}</option>{sev_options}</select>'
        f'<label for="cat">{r.t("findings.filter.category")}</label>'
        f'<select id="cat" class="select"><option value="" data-i18n="findings.filter.all">{_e(r.text("findings.filter.all"))}</option>{cat_options}</select>'
        f'<label for="q" class="sr-only">{r.t("findings.filter.search")}</label>'
        f'<input id="q" class="search" type="search" {r.attr("placeholder", "findings.filter.search")}>'
        f'<span id="findings-count" class="muted" aria-live="polite"></span></div>'
        f'<p id="findings-empty" class="empty" hidden>{r.t("findings.filter.empty")}</p>'
    ) if findings else ""
    body = filters + (f'<div class="finding-list">{cards}</div>' if cards else f'<p class="empty">{r.t("findings.none")}</p>')
    return f'<section id="findings" aria-labelledby="h-all-findings" class="sub"><div class="sub-head" id="all-findings"><h3 id="h-all-findings">{r.t("findings.all")}</h3></div>{body}</section>'


def _unknowns(r: _Renderer) -> str:
    report = r.report
    unknowns = report.get("remaining_unknowns") or []
    shown_above = set(report["claim_boundary"].get("not_evidenced") or [])
    extra = [u for u in unknowns if u not in shown_above]
    same = len(unknowns) - len(extra)
    note = f'<p class="muted">{r.t("unknowns.dedup", n=same)} <a href="#green">{r.t("green.title")}</a></p>' if same else ""
    body = (r.items(extra, "unknowns.none") if extra or not same else "") + note
    return _sub(r, "unknowns", "unknowns.title", body or f'<p class="empty">{r.t("unknowns.none")}</p>')


def _provenance(r: _Renderer) -> str:
    report = r.report
    project, prov = report["project"], report.get("provenance") or {}
    rows = [
        ("prov.version", f'<code>{_e(prov.get("assertiva_version"))}</code>'),
        ("prov.revision", f'<code>{_e(project.get("revision") or "—")}</code>'),
        ("prov.state", r.t("header.dirty" if project.get("dirty") else "header.clean")),
        ("prov.mode", f'<code>{_e(report["workflow"])}</code>'),
        ("prov.generated", f'<time datetime="{_e(report["generated_at"])}">{_e(report["generated_at"])}</time>'),
        ("prov.root", f'<code class="wrap">{_e(project.get("root"))}</code>'),
    ]
    if prov.get("adapters") is not None:
        rows.append(("prov.adapters", " ".join(f'<code class="tag">{_e(a)}</code>' for a in prov["adapters"]) or "—"))
    if prov.get("interpreter"):
        rows.append(("prov.interpreter", f'<code class="wrap">{_e(prov["interpreter"])}</code>'))
    if "read_only_verified" in prov:
        rows.append(("prov.readonly", r.t("yes" if prov["read_only_verified"] else "no")))
    if "read_only_until_approval" in prov:
        rows.append(("prov.until", r.t("yes" if prov["read_only_until_approval"] else "no")))
    if project.get("baseline_digest"):
        rows.append(("prov.digest", f'<code class="wrap">{_e(project["baseline_digest"])}</code>'))
    if prov.get("trace"):
        rows.append(("prov.trace", f'<code class="wrap">{_e(prov["trace"])}</code>'))
    rows.append(("prov.report_version", f'<code>{_e(report.get("report_version"))}</code>'))
    pairs = "".join(f"<dt>{r.t(k)}</dt><dd>{v}</dd>" for k, v in rows)
    body = (f'<dl class="kv prov">{pairs}</dl>'
            f'<details class="more"><summary>{r.t("raw.title")}</summary><pre class="code">{_e(json.dumps(prov, indent=2, ensure_ascii=False))}</pre></details>')
    return _sub(r, "provenance", "prov.title", body)


def _raw(r: _Renderer) -> str:
    data = json.dumps(r.report, indent=2, ensure_ascii=False, default=str)
    return _sub(r, "raw", "raw.title",
                f'<details class="more"><summary>{r.t("raw.title")}</summary><p class="muted">{r.t("raw.lead")}</p><pre class="code raw-json">{_e(data)}</pre></details>')


def _details(r: _Renderer) -> str:
    return (f'<section id="details" class="area" aria-labelledby="h-details"><h2 id="h-details" class="area-title">{r.t("nav.details")}</h2>'
            f"{_all_findings(r)}{_unknowns(r)}{_provenance(r)}{_raw(r)}</section>")


# --- page -------------------------------------------------------------------------------

def _hero(r: _Renderer) -> str:
    report = r.report
    project = report["project"]
    if report["workflow"] == "audit":
        mode = "mode.audit"
    else:
        mode = "mode.improve_applied" if report["states"].get("applied") else "mode.improve"
    revision = project.get("revision")
    revision_html = f"<code>{_e(revision[:12])}</code>" if revision else r.t("header.no_revision")
    states = " · ".join(r.state(k) for k, _ in _states(report))
    return (
        f'<div class="hero"><div class="hero-main"><p class="eyebrow">{r.t(mode)}</p>'
        f'<h1>{_e(project.get("name") or "project")}</h1>'
        f'<p class="meta-row"><span>{r.t("header.revision")} {revision_html}</span>'
        f'<span class="ws {"dirty" if project.get("dirty") else "clean"}">{r.t("header.dirty" if project.get("dirty") else "header.clean")}</span>'
        f'<span>{r.t("header.generated", t=report["generated_at"])}</span>'
        f'<span>{r.t("states.shown")}: {states or "—"}</span></p></div>'
        f'<div class="hero-status"><span class="hero-status-label">{r.t("header.status")}</span>{r.pill(report["status"])}'
        f'<code class="hero-raw">{_e(report["status"])}</code></div></div>'
    )


def _nav(r: _Renderer) -> str:
    report = r.report
    evidence = [("metrics", "metrics.title")]
    if report.get("candidate_qualification"):
        evidence.insert(0, ("qualification", "qual.title"))
    if report.get("change_set"):
        evidence.insert(1 if report.get("candidate_qualification") else 0, ("changes", "changes.title"))
    if report.get("evidence_delta"):
        evidence.append(("delta", "delta.title"))
    for sid, key, present in (
        ("negative-paths", "neg.title", any(s.get("negative_paths") for _, s in _states(report))),
        ("mutation-evidence", "mut.title", any(s.get("mutation") for _, s in _states(report))),
        ("artifact-evidence", "art.title", any(s.get("artifacts") for _, s in _states(report))),
        ("delivery", "delivery.title", bool(report.get("delivery") or report.get("review_candidates"))),
        ("selection", "sel.title", bool(report.get("test_selection"))),
        ("history", "hist.title", bool(report.get("history"))),
    ):
        if present:
            evidence.append((sid, key))
    verification = [("surface-section", "surface.title"), ("runs", "runs.title")]
    if report.get("execution_budget"):
        verification.append(("budget", "budget.title"))
    details = [("unknowns", "unknowns.title"), ("provenance", "prov.title"), ("raw", "raw.title")]
    if report["findings"] or report["workflow"] == "audit":
        details.insert(0, ("findings", "findings.all"))
    areas = [
        ("overview", "nav.overview", [("decision", "overview.title"), ("summary", "cards.title"), ("green", "green.title"),
                                      ("top-findings", "findings.top"), ("improvements", "improve.title")]),
        ("evidence", "nav.evidence", evidence),
        ("verification", "nav.verification", verification),
        ("details", "nav.details", details),
    ]
    items = "".join(
        f'<li><a class="nav-area" href="#{aid}">{r.t(key)}</a><ul>'
        + "".join(f'<li><a href="#{sid}">{r.t(skey)}</a></li>' for sid, skey in subs)
        + "</ul></li>"
        for aid, key, subs in areas
    )
    return f'<nav class="sidenav" {r.attr("aria-label", "nav.label")}><ul>{items}</ul></nav>'


_ICONS = {
    "check": '<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "cross": '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "alert": '<path d="M8 2.5l6 11H2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M8 6.5v3.2M8 11.6v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "question": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2.2 1.8"/><path d="M6.4 6.3a1.7 1.7 0 113 1.1c-.6.4-1.4.8-1.4 1.6M8 11.3v.1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
    "block": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M4 12L12 4" stroke="currentColor" stroke-width="1.5"/>',
    "dash": '<path d="M4 8h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "dot": '<circle cx="8" cy="8" r="3" fill="currentColor"/>',
    "info": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 7.3v4M8 4.8v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "chev": '<path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "arrow": '<path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    "copy": '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M3.5 10.5v-7a1 1 0 011-1h7" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "moon": '<path d="M13 9.5A5.5 5.5 0 016.5 3a5.5 5.5 0 106.5 6.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>',
    "globe": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2 8h12M8 2c1.8 1.7 2.6 3.7 2.6 6S9.8 12.3 8 14C6.2 12.3 5.4 10.3 5.4 8S6.2 3.7 8 2z" fill="none" stroke="currentColor" stroke-width="1.2"/>',
}


def _sprite() -> str:
    symbols = "".join(f'<symbol id="i-{name}" viewBox="0 0 16 16">{body}</symbol>' for name, body in _ICONS.items())
    return f'<svg class="sprite" aria-hidden="true" focusable="false">{symbols}</svg>'


_LOGO = ('<svg class="logo" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="1" y="1" width="22" height="22" rx="6" fill="var(--accent)"/>'
         '<path d="M7 16.5L12 6l5 10.5M9.2 12.4h5.6" fill="none" stroke="var(--on-accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def render_html(report: dict) -> str:
    from .report import REPORT_VERSION  # the model module owns the report format version

    r = _Renderer(report)
    r.text("copied")  # copy-button feedback, announced by the script
    project = report["project"]
    title = f"Assertiva {report['workflow']} — {project.get('name') or 'project'}"
    main = _hero(r) + _overview(r) + _evidence(r) + _verification(r) + _details(r)
    header = (
        f'<header class="topbar"><div class="topbar-inner"><a class="brand" href="#overview">{_LOGO}'
        f'<span class="brand-name">ASSERTIVA</span><span class="brand-product">{r.t("brand.product")}</span></a>'
        f'<div class="controls"><label class="lang">{r.icon("globe")}<span class="sr-only">{r.t("lang.label")}</span>'
        f'<select id="lang" class="select" {r.attr("aria-label", "lang.label")}><option value="en" lang="en">English</option>'
        f'<option value="pt-BR" lang="pt-BR">Português (Brasil)</option></select></label>'
        f'<button id="theme" type="button" class="toggle" aria-pressed="false" {r.attr("aria-label", "theme.label")}>'
        f'<span class="toggle-track" aria-hidden="true"><span class="toggle-thumb"></span></span>{r.icon("moon")}{r.t("theme.toggle")}</button>'
        f"</div></div></header>"
    )
    nav = _nav(r)
    footer = f'<footer class="footer"><p>{r.t("footer", v=REPORT_VERSION)}</p></footer>'
    skip = f'<a class="skip" href="#main">{r.t("skip")}</a>'
    dictionary = json.dumps({"pt-BR": dict(sorted(r.used.items()))}, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark"><title>{_e(title)}</title><style>{_CSS}</style></head>
<body>
{skip}
{_sprite()}
{header}
<div class="shell">{nav}
<main id="main" tabindex="-1">{main}</main></div>
{footer}
<div id="live" class="sr-only" aria-live="polite"></div>
<script type="application/json" id="i18n">{dictionary}</script>
<script>{_JS}</script>
</body></html>
"""


_CSS = """
:root{color-scheme:light;
--bg:#f6f6f4;--surface:#ffffff;--surface-2:#f0f0ed;--surface-elevated:#ffffff;--border:#e3e3de;--border-strong:#cfcfc8;
--text:#17181b;--muted:#5c5e66;--faint:#86888f;--accent:#3b4fd8;--on-accent:#ffffff;--accent-soft:#eceefe;
--success:#17773a;--warning:#8f5d00;--danger:#c0262d;--unknown:#5f636b;--info:#2b67a8;
--c-baseline:#8c9099;--c-candidate:#3b4fd8;--c-applied:#17773a;--c-current:#3b4fd8;
--shadow:0 1px 2px rgba(17,17,26,.04),0 1px 1px rgba(17,17,26,.03);--shadow-lg:0 8px 24px -12px rgba(17,17,26,.18);
--r-sm:6px;--r:10px;--r-lg:14px;--s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--s6:32px;--s7:48px;
--font:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#0d0e10;--surface:#15161a;--surface-2:#1b1c21;--surface-elevated:#1d1e23;--border:#26282e;--border-strong:#35373e;
--text:#ececef;--muted:#a3a5ad;--faint:#7b7e86;--accent:#8b9cff;--on-accent:#0d0e10;--accent-soft:#1e2240;
--success:#4cc574;--warning:#e0b04a;--danger:#ff7a7a;--unknown:#a2a6ae;--info:#72b4ff;
--c-baseline:#71757e;--c-candidate:#8b9cff;--c-applied:#4cc574;--c-current:#8b9cff;
--shadow:0 1px 2px rgba(0,0,0,.4);--shadow-lg:0 12px 32px -12px rgba(0,0,0,.6)}}
:root[data-theme="dark"]{color-scheme:dark;
--bg:#0d0e10;--surface:#15161a;--surface-2:#1b1c21;--surface-elevated:#1d1e23;--border:#26282e;--border-strong:#35373e;
--text:#ececef;--muted:#a3a5ad;--faint:#7b7e86;--accent:#8b9cff;--on-accent:#0d0e10;--accent-soft:#1e2240;
--success:#4cc574;--warning:#e0b04a;--danger:#ff7a7a;--unknown:#a2a6ae;--info:#72b4ff;
--c-baseline:#71757e;--c-candidate:#8b9cff;--c-applied:#4cc574;--c-current:#8b9cff;
--shadow:0 1px 2px rgba(0,0,0,.4);--shadow-lg:0 12px 32px -12px rgba(0,0,0,.6)}
*,*::before,*::after{box-sizing:border-box}
html{scroll-padding-top:72px;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 var(--font);font-feature-settings:"cv11","ss01";-webkit-font-smoothing:antialiased}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
code,pre,.mono{font-family:var(--mono);font-size:.86em}
code{overflow-wrap:anywhere;word-break:break-word}
.num,.num-col,.card-value{font-variant-numeric:tabular-nums}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.sprite{display:none}
.ic{width:16px;height:16px;flex:none;vertical-align:-3px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.skip{position:absolute;left:var(--s4);top:-48px;background:var(--surface);padding:var(--s2) var(--s3);border-radius:var(--r-sm);z-index:20;box-shadow:var(--shadow-lg)}
.skip:focus{top:var(--s2)}
/* top bar */
.topbar{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:saturate(1.4) blur(8px);border-bottom:1px solid var(--border)}
.topbar-inner{max-width:1560px;margin:0 auto;padding:0 var(--s5);height:56px;display:flex;align-items:center;justify-content:space-between;gap:var(--s4)}
.brand{display:flex;align-items:center;gap:10px;color:var(--text);text-decoration:none;min-width:0}
.logo{width:24px;height:24px;flex:none}
.brand-name{font-weight:700;letter-spacing:.14em;font-size:.8rem}
.brand-product{color:var(--muted);font-size:.85rem;padding-left:10px;border-left:1px solid var(--border-strong);white-space:nowrap}
.controls{display:flex;align-items:center;gap:var(--s2)}
.lang{display:flex;align-items:center;gap:6px;color:var(--muted)}
.select,.search{font:inherit;font-size:.86rem;color:var(--text);background:var(--surface);border:1px solid var(--border-strong);border-radius:var(--r-sm);padding:6px 10px;min-height:34px}
.select{appearance:none;padding-right:28px;background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%);background-position:calc(100% - 14px) 50%,calc(100% - 9px) 50%;background-size:5px 5px;background-repeat:no-repeat}
.select:hover,.search:hover{border-color:var(--faint)}
.toggle{font:inherit;font-size:.86rem;display:inline-flex;align-items:center;gap:8px;color:var(--text);background:var(--surface);border:1px solid var(--border-strong);border-radius:999px;padding:4px 12px 4px 6px;min-height:34px;cursor:pointer}
.toggle:hover{border-color:var(--faint)}
.toggle-track{width:30px;height:18px;border-radius:999px;background:var(--surface-2);border:1px solid var(--border-strong);position:relative;flex:none}
.toggle-thumb{position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:var(--muted);transition:transform .15s ease}
.toggle[aria-pressed="true"] .toggle-track{background:var(--accent);border-color:var(--accent)}
.toggle[aria-pressed="true"] .toggle-thumb{transform:translateX(12px);background:var(--on-accent)}
/* layout */
.shell{max-width:1560px;margin:0 auto;padding:0 var(--s5);display:grid;grid-template-columns:220px minmax(0,1fr);gap:var(--s6)}
.sidenav{position:sticky;top:56px;align-self:start;max-height:calc(100vh - 56px);overflow:auto;padding:var(--s5) 0;font-size:.86rem}
.sidenav ul{list-style:none;margin:0;padding:0}
.sidenav>ul>li{margin-bottom:var(--s4)}
.sidenav a{display:block;color:var(--muted);text-decoration:none;padding:3px 10px;border-radius:var(--r-sm)}
.sidenav a:hover{color:var(--text);background:var(--surface-2)}
.sidenav .nav-area{color:var(--text);font-weight:600;font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;margin-bottom:2px}
main{min-width:0;padding:var(--s5) 0 var(--s7)}
main:focus{outline:none}
/* hero */
.hero{display:flex;justify-content:space-between;align-items:flex-start;gap:var(--s5);padding:var(--s4) 0 var(--s5);border-bottom:1px solid var(--border);margin-bottom:var(--s5);flex-wrap:wrap}
.eyebrow{margin:0 0 6px;font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
h1{font-size:clamp(1.6rem,2.6vw,2.15rem);line-height:1.15;letter-spacing:-.02em;margin:0 0 var(--s2);overflow-wrap:anywhere}
.meta-row{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0;color:var(--muted);font-size:.86rem;align-items:center}
.ws.dirty{color:var(--warning)}
.ws.dirty::before{content:"● ";}
.ws.clean::before{content:"○ ";}
.hero-status{display:flex;flex-direction:column;align-items:flex-end;gap:6px}
.hero-status-label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.hero-status .pill{font-size:.95rem;padding:6px 14px 6px 10px;margin:0}
.hero-status .pill .ic{width:18px;height:18px}
.hero-raw{font-size:.72rem;color:var(--faint)}
/* areas and subsections */
.area{padding-top:var(--s5)}
.area+.area{margin-top:var(--s6);border-top:1px solid var(--border)}
.area-title{font-size:.78rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:0 0 var(--s4)}
.area-lead{margin-top:calc(-1*var(--s2))}
.sub{margin:0 0 var(--s6)}
.sub-head{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:baseline;gap:2px var(--s4);margin-bottom:var(--s3)}
.sub-head .lead{grid-column:1/-1;grid-row:2}
h3{font-size:1.18rem;letter-spacing:-.01em;margin:0;line-height:1.3}
h4{font-size:.95rem;margin:0 0 var(--s2);line-height:1.35}
h5{font-size:.8rem;margin:var(--s3) 0 var(--s1);color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.lead{color:var(--muted);margin:2px 0 0;max-width:80ch}
.muted{color:var(--muted)}
.empty{color:var(--muted);margin:var(--s2) 0;font-style:italic}
.link{font-size:.86rem;font-weight:500}
p{margin:var(--s2) 0}
/* pills and tags */
.pill{--tone:var(--unknown);display:inline-flex;align-items:center;gap:5px;font-size:.76rem;font-weight:600;line-height:1.2;padding:3px 9px 3px 7px;border-radius:999px;color:var(--tone);background:color-mix(in srgb,var(--tone) 11%,transparent);border:1px solid color-mix(in srgb,var(--tone) 32%,transparent);white-space:nowrap;vertical-align:middle;margin-right:6px}
.pill .raw{font-size:.88em;font-weight:500;opacity:.85;padding-left:6px;border-left:1px solid color-mix(in srgb,var(--tone) 32%,transparent)}
.tone-pass,.pass{--tone:var(--success)}
.tone-fail,.fail{--tone:var(--danger)}
.tone-blocked,.blocked{--tone:var(--warning);border-style:double}
.tone-warn{--tone:var(--warning)}
.tone-unknown,.unknown{--tone:var(--unknown);border-style:dotted}
.tone-not_run,.not_run{--tone:var(--unknown);border-style:dashed;opacity:.92}
.tone-neutral{--tone:var(--muted)}
.tone-accent{--tone:var(--accent)}
.tier{display:inline-block;font-size:.72rem;font-weight:500;color:var(--muted);border:1px solid var(--border-strong);border-radius:var(--r-sm);padding:1px 6px;white-space:nowrap;vertical-align:middle}
.tag{display:inline-block;font-family:var(--mono);font-size:.74rem;background:var(--surface-2);border:1px solid var(--border);border-radius:5px;padding:1px 6px;margin:1px 4px 1px 0}
/* banner */
.banner{display:flex;gap:var(--s3);align-items:flex-start;padding:var(--s3) var(--s4);border-radius:var(--r);background:color-mix(in srgb,var(--warning) 10%,var(--surface));border:1px solid color-mix(in srgb,var(--warning) 35%,transparent);color:var(--text);margin-bottom:var(--s5)}
.banner .ic{color:var(--warning);margin-top:3px}
.banner p{margin:0}
/* decision surface */
.decisions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--s3)}
.decision{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--s4);box-shadow:var(--shadow);border-top:3px solid var(--tone,var(--border));min-width:0}
.decision h4{display:flex;align-items:center;gap:8px;font-size:.78rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.decision h4 .ic{color:var(--tone)}
.decision-count{font-size:1.02rem;font-weight:600;margin:0 0 var(--s2)}
.d-working{--tone:var(--success)}.d-attention{--tone:var(--warning)}.d-unknown{--tone:var(--unknown)}.d-next{--tone:var(--accent)}
.next-action{font-weight:600;font-size:1rem;line-height:1.45}
.list{margin:var(--s1) 0;padding-left:1.1em}
.list li{margin:3px 0;overflow-wrap:anywhere}
.list li::marker{color:var(--faint)}
.list.tight{font-size:.88rem}
.decision .list a{color:var(--text);text-decoration:none;display:inline}
.decision .list a:hover .f-title{text-decoration:underline}
/* cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:var(--s3)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:var(--s3) var(--s4);box-shadow:var(--shadow);min-width:0}
.card-title{font-size:.74rem;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
.card-value{font-size:1.5rem;font-weight:650;letter-spacing:-.02em;margin:0;line-height:1.2}
.card-value small{font-size:.8rem;font-weight:500;color:var(--muted);letter-spacing:0}
.card-sub{font-size:.82rem;color:var(--muted);margin:4px 0 0}
.sev-list{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:4px 10px}
.sev-list li{display:flex;align-items:center;font-size:.85rem}
/* claim boundary */
.green{background:var(--surface);border:1px solid var(--border);border-radius:var(--r-lg);padding:var(--s5);box-shadow:var(--shadow)}
.claims{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--s4)}
.claim{min-width:0;padding:var(--s3) var(--s4);border-radius:var(--r);background:var(--surface-2);border:1px solid var(--border)}
.claim h4{display:flex;align-items:center;gap:8px;margin-bottom:0}
.claim h4 .ic{color:var(--tone)}
.claim-sub{font-size:.8rem;color:var(--muted);margin:2px 0 var(--s2)}
.c-observed{--tone:var(--success)}.c-not{--tone:var(--unknown);border-style:dashed}.c-limits{--tone:var(--info)}
/* top findings */
.top-list{list-style:none;margin:0;padding:0;display:grid;gap:var(--s2)}
.top-finding{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:var(--s3) var(--s4)}
.top-finding a{text-decoration:none;color:var(--text);font-weight:600}
.top-finding a:hover .f-title{text-decoration:underline}
.top-finding p{margin:4px 0 0;color:var(--muted);font-size:.9rem}
/* improvements */
.imp-group{margin-bottom:var(--s4)}
.imp-group>h4{font-size:.78rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted)}
.imp-list{list-style:none;margin:0;padding:0;display:grid;gap:var(--s2)}
.improvement{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:var(--s3) var(--s4)}
.imp-head{display:flex;gap:var(--s2);align-items:baseline}
.imp-head p{margin:0;font-weight:600}
.imp-meta{font-size:.84rem;color:var(--muted);margin:6px 0 0;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.imp-meta a{color:var(--text)}
.imp-close{font-size:.86rem;margin:6px 0 0;color:var(--muted)}
.f-code{font-size:.74rem;color:var(--faint)}
/* findings */
.filters{display:flex;flex-wrap:wrap;align-items:center;gap:var(--s2) var(--s3);margin:0 0 var(--s3);padding:var(--s2) var(--s3);background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.filters label{font-size:.82rem;color:var(--muted);font-weight:500}
.search{flex:1 1 200px;min-width:0}
.finding-list{display:grid;gap:var(--s2)}
.finding,.change,.check details,.more,.tech{border-radius:var(--r)}
.finding{background:var(--surface);border:1px solid var(--border);box-shadow:var(--shadow)}
.finding[open]{box-shadow:var(--shadow-lg)}
summary{cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
.finding>summary{padding:var(--s3) var(--s4);display:flex;flex-direction:column;gap:4px;position:relative;padding-right:40px}
.chev{position:absolute;right:14px;top:16px;color:var(--muted);transition:transform .15s ease}
details[open]>summary>.chev{transform:rotate(180deg)}
.f-head{display:flex;align-items:center;flex-wrap:wrap;gap:4px}
.f-title{font-weight:600;font-size:1rem}
.f-meta{display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:.82rem;color:var(--muted)}
.f-meta .f-code{margin-left:auto}
.f-body{padding:0 var(--s4) var(--s4);display:grid;gap:var(--s3);border-top:1px solid var(--border);padding-top:var(--s3)}
.f-block h4{font-size:.74rem;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin:0 0 4px;display:flex;align-items:center;gap:8px}
.f-block p{margin:0}
.f-block.rec p{font-weight:550}
.affected{margin:0 0 4px}
.tech>summary,.more>summary{display:inline-flex;align-items:center;gap:6px;font-size:.84rem;color:var(--accent);font-weight:500;padding:2px 0}
.tech>summary::before,.more>summary::before{content:"";width:6px;height:6px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(-45deg);transition:transform .15s ease}
.tech[open]>summary::before,.more[open]>summary::before{transform:rotate(45deg)}
.kv{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:4px var(--s4);margin:var(--s2) 0;font-size:.88rem}
.kv dt{color:var(--muted)}
.kv dd{margin:0;min-width:0;overflow-wrap:anywhere}
pre.code{margin:var(--s2) 0 0;padding:var(--s3);background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-sm);white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;max-height:420px;overflow:auto;font-size:.8rem;line-height:1.5}
pre.diff{white-space:pre;overflow-x:auto}
pre.raw-json{max-height:640px}
/* tables */
.table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin:0 0 var(--s3)}
table{border-collapse:collapse;width:100%;font-size:.88rem}
caption{text-align:left;font-size:.74rem;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);padding:var(--s3) var(--s4) var(--s2)}
th,td{text-align:left;vertical-align:top;padding:8px var(--s4);border-top:1px solid var(--border)}
table.metrics{table-layout:fixed}
.c-metric{width:44%}.c-value{width:150px}.c-delta{width:150px}
.meter{display:inline-block;width:56px;height:6px;border-radius:3px;background:var(--surface-2);border:1px solid var(--border);margin-right:8px;vertical-align:middle;overflow:hidden}
.meter>span{display:block;height:100%;background:var(--accent);opacity:.75}
thead th{font-size:.76rem;font-weight:600;color:var(--muted);background:var(--surface-2);border-top:1px solid var(--border)}
tbody th{font-weight:500}
.num-col{text-align:right;white-space:nowrap}
thead .num-col{white-space:normal}
.th-note{display:block;font-weight:400;font-size:.72rem;color:var(--faint);text-transform:none;letter-spacing:0}
.m-name{display:block}
.m-id{display:block;font-size:.7rem;color:var(--faint);margin-top:0;font-weight:400}
.dir{white-space:nowrap;color:var(--muted)}
tbody tr:hover{background:color-mix(in srgb,var(--surface-2) 60%,transparent)}
.sr-note{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.chart{margin:var(--s3) 0;padding:var(--s4);background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.chart svg .lbl{fill:var(--text);font-size:12px;font-family:var(--font)}
.chart svg .val{fill:var(--muted);font-size:11px;font-family:var(--mono)}
.bar.baseline{fill:var(--c-baseline)}.bar.candidate{fill:var(--c-candidate)}.bar.applied{fill:var(--c-applied)}.bar.current{fill:var(--c-current)}
.chart figcaption{display:flex;flex-wrap:wrap;gap:var(--s3);font-size:.82rem;margin-top:var(--s2)}
.legend-item{display:inline-flex;align-items:center;gap:6px}
.swatch{display:inline-block;width:10px;height:10px;border-radius:3px}
.swatch.baseline{background:var(--c-baseline)}.swatch.candidate{background:var(--c-candidate)}.swatch.applied{background:var(--c-applied)}.swatch.current{background:var(--c-current)}
.delta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:var(--s3)}
.delta-col{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:var(--s3) var(--s4)}
.delta-col h4{display:flex;align-items:center;justify-content:space-between}
/* panels */
.panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:var(--s3);margin-bottom:var(--s3)}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:var(--s3) var(--s4);min-width:0;box-shadow:var(--shadow)}
.panel-head{display:flex;justify-content:space-between;align-items:center;gap:var(--s2);margin-bottom:var(--s2)}
.panel-head h4{margin:0}
.checks{list-style:none;margin:0;padding:0;display:grid;gap:var(--s2)}
.check-row{display:grid;grid-template-columns:auto minmax(0,1fr);gap:2px var(--s2);font-size:.88rem}
.check-row .check-sum{grid-column:2;color:var(--muted);font-size:.84rem}
.check-row .check-lims{grid-column:2;margin:0}
.qcheck-name{font-weight:550}
.matrix{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.matrix li{font-size:.8rem;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-sm);padding:2px 8px}
.change{background:var(--surface);border:1px solid var(--border);margin-bottom:var(--s2)}
.change>summary{display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:var(--s3) var(--s4);padding-right:40px;position:relative}
.change>*:not(summary){margin-left:var(--s4);margin-right:var(--s4)}
.change>pre{margin-bottom:var(--s4)}
.path{font-weight:600}
/* verification surface */
.origins{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:var(--s3);margin-bottom:var(--s3)}
.origin{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--shadow);min-width:0}
.origin-head{display:flex;justify-content:space-between;align-items:center;margin:0;padding:var(--s3) var(--s4);border-bottom:1px solid var(--border);font-size:.9rem}
.origin-head .count{font-size:.78rem;font-weight:500;color:var(--muted)}
.check-list{list-style:none;margin:0;padding:0}
.check{border-top:1px solid var(--border)}
.check:first-child{border-top:0}
.check summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:var(--s3);padding:10px var(--s4);padding-right:40px;position:relative}
.check summary:hover{background:var(--surface-2)}
.kind{font-size:.72rem;font-weight:600;padding:2px 7px;border-radius:var(--r-sm);background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.kind-unknown,.kind-custom{background:var(--surface-2);color:var(--muted);border:1px dashed var(--border-strong)}
.kind-deploy{background:color-mix(in srgb,var(--danger) 12%,transparent);color:var(--danger)}
.check-title{display:flex;flex-direction:column;min-width:0}
.check-name{font-weight:550;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.check-where{font-size:.78rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.check-tags{display:flex;gap:6px;align-items:center}
.gate{font-size:.72rem;color:var(--muted);white-space:nowrap}
.gate-blocking{color:var(--text);font-weight:600}
.check-body{padding:0 var(--s4) var(--s3)}
.cmd{margin-top:var(--s2)}
.cmd-head{display:flex;justify-content:space-between;align-items:center;font-size:.74rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.copy{font:inherit;font-size:.76rem;display:inline-flex;gap:5px;align-items:center;color:var(--muted);background:var(--surface);border:1px solid var(--border-strong);border-radius:var(--r-sm);padding:2px 8px;cursor:pointer;text-transform:none;letter-spacing:0}
.copy:hover{color:var(--text)}
.copy .ic{width:13px;height:13px}
code.wrap{white-space:pre-wrap}
.budget{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--border);border-radius:var(--r)}
.budget-row{display:grid;grid-template-columns:auto minmax(120px,240px) minmax(0,1fr);gap:var(--s3);align-items:baseline;padding:10px var(--s4);border-top:1px solid var(--border);font-size:.88rem}
.budget-row:first-child{border-top:0}
.budget-reason{color:var(--muted)}
.prov{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:var(--s3) var(--s4)}
.more{margin:var(--s2) 0}
.footer{max-width:1560px;margin:0 auto;padding:var(--s5);color:var(--muted);font-size:.8rem;border-top:1px solid var(--border)}
/* responsive */
@media (max-width:1180px){.shell{grid-template-columns:minmax(0,1fr);gap:0}
.sidenav{position:static;max-height:none;padding:var(--s3) 0 0;border-bottom:1px solid var(--border)}
.sidenav>ul{display:flex;flex-wrap:wrap;gap:4px}.sidenav>ul>li{margin:0}.sidenav>ul>li>ul{display:none}
.sidenav .nav-area{padding:6px 12px;border:1px solid var(--border);border-radius:999px;background:var(--surface);text-transform:none;letter-spacing:0;font-size:.85rem}
.decisions{grid-template-columns:repeat(2,minmax(0,1fr))}.claims{grid-template-columns:minmax(0,1fr)}}
@media (max-width:720px){:root{--s5:16px;--s6:24px}
body{font-size:14.5px}.topbar-inner{padding:0 16px}.shell{padding:0 16px}.brand-product{display:none}
.toggle{padding:4px 8px 4px 6px}.toggle>span[data-i18n]{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
.decisions{grid-template-columns:minmax(0,1fr)}.hero-status{align-items:flex-start}
.green{padding:var(--s3)}
table.responsive thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
table.responsive tr{display:block;border-top:1px solid var(--border);padding:var(--s2) 0}
table.responsive th,table.responsive td{display:block;border:0;padding:3px var(--s4);text-align:left}
table.responsive td[data-label]::before{content:attr(data-label);display:block;font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.num-col{text-align:left}
.check summary{grid-template-columns:minmax(0,1fr);gap:4px}.kind{justify-self:start}
.lang .ic{display:none}.controls{gap:6px}.brand{gap:8px}.brand-name{font-size:.72rem;letter-spacing:.1em}
.lang .select{max-width:150px}
.budget-row{grid-template-columns:minmax(0,1fr);gap:4px}
.kv{grid-template-columns:minmax(0,1fr)}.kv dt{margin-top:6px}
.f-meta .f-code{margin-left:0}}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
@media print{.topbar,.sidenav,.filters,.copy,.skip{display:none}.shell{display:block}details>*{display:block}body{background:#fff}}
"""

_JS = r"""
(function(){
var root=document.documentElement,dict={};
try{dict=JSON.parse(document.getElementById('i18n').textContent)||{};}catch(e){}
function load(k){try{return localStorage.getItem(k);}catch(e){return null;}}
function save(k,v){try{localStorage.setItem(k,v);}catch(e){}}
function fill(text,args){return text.replace(/\{(\w+)\}/g,function(m,k){var v=args[k];if(v===undefined)return m;
 if(v&&typeof v==='object'){return lang==='en'?v.en:((dict[lang]||{})[v['$']]||v.en);}return String(v);});}
function pick(key,args){var d=dict[lang]||{};if(args&&args.n!==undefined&&d[key+'.one']!==undefined){return d[key+(Number(args.n)===1?'.one':'.other')];}return d[key];}
var lang='en';
function apply(next){lang=next;root.setAttribute('lang',lang);
 document.querySelectorAll('[data-i18n]').forEach(function(el){
  if(el.dataset.en===undefined)el.dataset.en=el.textContent;
  var args={};if(el.dataset.i18nArgs){try{args=JSON.parse(el.dataset.i18nArgs);}catch(e){}}
  var t=lang==='en'?null:pick(el.dataset.i18n,args);
  el.textContent=t?fill(t,args):el.dataset.en;});
 ['aria-label','placeholder','title'].forEach(function(a){  document.querySelectorAll('[data-i18n-'+a+']').forEach(function(el){
   var store='en'+a.replace(/-/g,'');if(el.dataset[store]===undefined)el.dataset[store]=el.getAttribute(a)||'';
   var key=el.getAttribute('data-i18n-'+a),t=lang==='en'?null:(dict[lang]||{})[key];el.setAttribute(a,t||el.dataset[store]);});});
 var s=document.getElementById('lang');if(s)s.value=lang;counts();}
var saved=load('assertiva.lang'),nav=(navigator.language||'').toLowerCase();
var initial=saved==='pt-BR'||saved==='en'?saved:(nav.indexOf('pt')===0?'pt-BR':'en');
var sel=document.getElementById('lang');
if(sel)sel.addEventListener('change',function(){save('assertiva.lang',sel.value);apply(sel.value);});
var btn=document.getElementById('theme');
function dark(){var t=root.getAttribute('data-theme');return t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches;}
function sync(){if(btn)btn.setAttribute('aria-pressed',String(dark()));}
var savedTheme=load('assertiva.theme');if(savedTheme==='dark'||savedTheme==='light')root.setAttribute('data-theme',savedTheme);
if(btn)btn.addEventListener('click',function(){var next=dark()?'light':'dark';root.setAttribute('data-theme',next);save('assertiva.theme',next);sync();});
sync();
function counts(){var c=document.getElementById('findings-count');if(!c)return;var shown=document.querySelectorAll('.finding:not([hidden])').length;
 c.textContent=shown+' / '+document.querySelectorAll('.finding').length;var em=document.getElementById('findings-empty');if(em)em.hidden=shown>0;}
function filter(){var s=(document.getElementById('sev')||{}).value||'',c=(document.getElementById('cat')||{}).value||'',q=((document.getElementById('q')||{}).value||'').toLowerCase();
 document.querySelectorAll('.finding').forEach(function(e){e.hidden=(s&&e.dataset.severity!==s)||(c&&e.dataset.category!==c)||(q&&e.textContent.toLowerCase().indexOf(q)<0);});counts();}
['sev','cat','q'].forEach(function(i){var e=document.getElementById(i);e&&e.addEventListener('input',filter);});
var k=document.getElementById('kind');k&&k.addEventListener('input',function(){
 document.querySelectorAll('.check[data-kind],#surface tbody tr').forEach(function(t){t.hidden=!!k.value&&t.dataset.kind!==k.value;});
 document.querySelectorAll('.origin').forEach(function(o){o.hidden=!o.querySelector('.check:not([hidden])');});});
function reveal(){var id=decodeURIComponent(location.hash.slice(1));if(!id)return;var el=document.getElementById(id);if(!el)return;
 for(var n=el;n;n=n.parentElement){if(n.tagName==='DETAILS')n.open=true;}if(el.tagName==='DETAILS')el.open=true;}
window.addEventListener('hashchange',reveal);reveal();
var live=document.getElementById('live');
document.addEventListener('click',function(ev){var b=ev.target.closest&&ev.target.closest('.copy');if(!b)return;
 var pre=b.closest('.cmd').querySelector('pre');var text=pre?pre.textContent:'';
 function done(){var msg=(dict[lang]||{})['copied']||'Copied';if(live)live.textContent=msg;}
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,function(){});}
 else{var r=document.createRange();r.selectNodeContents(pre);var s=getSelection();s.removeAllRanges();s.addRange(r);try{document.execCommand('copy');done();}catch(e){}}});
apply(initial);
})();
"""
