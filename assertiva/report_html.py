"""HTML rendering of the Assurance Report: one self-contained, offline, bilingual (en / pt-BR) page in two layers.

Layer 1, decision (marked ``data-layer="decision"``): what was examined and how strongly, the conclusion and why,
what is confirmed, what needs attention, what is not proven, and the next step only when the evidence ranks one.
Every text in it is localized. Layer 2, auditability: findings in full, every metric, every check, provenance, the
complete claim boundary and the canonical JSON. Both are drawn from the same report model; nothing here changes
or re-interprets it.

Localization is by stable key (report_i18n) and by the engine's exact sentence templates (report_narrative).
Engine text that matches no template is shown as written, marked ``lang="en"``, only in technical detail.
English is rendered unless ``lang="pt-BR"``; the strings a page uses in the other language are embedded and
swapped by a small script, so the page works without JavaScript and without any network access.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from typing import Any

from .report_i18n import ACTIONS, FINDINGS, METRIC_GROUPS, METRICS, UI
from .report_narrative import match as _narrative_match
from .report_narrative import strip_kinds, template as _narrative_template

Pair = tuple[str, str]

_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
_STATE_ORDER = ("current", "baseline", "candidate", "applied")
_FIRST = ("NATIVE_COLLECTION_ERRORS", "NATIVE_TESTS_FAILING")  # their own recommendation says they come first
_LIST_LIMIT = 6
_DOT_SEP = '<span class="dot-sep" aria-hidden="true">·</span>'
_ARROW_SEP = '<span class="arrow" aria-hidden="true">→</span>'
_BAD = ("FAIL", "BLOCKED")
_OPEN = ("UNKNOWN", "NOT_RUN")


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _humanize(identifier: str) -> str:
    text = str(identifier).replace("_", " ").strip()
    return text[:1].upper() + text[1:].lower() if text else text


def _key(pair: Pair) -> str:
    return "x." + hashlib.sha1((pair[0] + "\x00" + pair[1]).encode("utf-8")).hexdigest()[:12]


def _num(value: Any, unit: str | None = None, digits: int = 2) -> Pair:
    if value is None:
        return ("—", "—")
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, float) and not value.is_integer():
        en = f"{value:,.{digits}f}"
    else:
        en = f"{int(value):,}"
    pt = en.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if unit == "%":
        return (en + "%", pt + "%")
    if unit:
        return (f"{en} {unit}", f"{pt} {unit}")
    return (en, pt)


_MONTHS = (("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
           ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"))


def _when(iso: str) -> Pair:
    try:
        moment = datetime.fromisoformat(iso).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return (str(iso), str(iso))
    clock = f"{moment.hour:02d}:{moment.minute:02d} UTC"
    return (f"{_MONTHS[0][moment.month - 1]} {moment.day}, {moment.year}, {clock}",
            f"{moment.day} {_MONTHS[1][moment.month - 1]} {moment.year}, {clock}")


def _join(pairs: list[Pair], sep: Pair = ("; ", "; ")) -> Pair:
    return (sep[0].join(p[0] for p in pairs), sep[1].join(p[1] for p in pairs))


def _and(pairs: list[Pair]) -> Pair:
    if len(pairs) <= 1:
        return pairs[0] if pairs else ("", "")
    head = _join(pairs[:-1], (", ", ", "))
    return (f"{head[0]} and {pairs[-1][0]}", f"{head[1]} e {pairs[-1][1]}")


def _ui(key: str, n: Any = None, **args: Any) -> tuple[str, Pair]:
    """(dictionary key, (en, pt)) for a UI key; arguments are filled per language, plurals chosen by ``n``."""
    full = key
    if n is not None and key + ".one" in UI:
        full = key + (".one" if n == 1 else ".other")
    en, pt = UI[full]
    if n is not None:
        args["n"] = n
    if not args:
        return full, (en, pt)
    values = [{}, {}]
    for name, value in args.items():
        if isinstance(value, tuple):
            values[0][name], values[1][name] = value
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            values[0][name], values[1][name] = _num(value)
        else:
            values[0][name] = values[1][name] = str(value)
    pair = (en.format(**values[0]), pt.format(**values[1]))
    return _key(pair), pair


def pair_of(key: str, n: Any = None, **args: Any) -> Pair:
    return _ui(key, n=n, **args)[1]


def _label(prefix: str, raw: str) -> Pair:
    entry = UI.get(prefix + raw)
    return entry if entry else (_humanize(raw), _humanize(raw))


def _lower(pair: Pair) -> Pair:
    return (pair[0][:1].lower() + pair[0][1:], pair[1][:1].lower() + pair[1][1:])


# --- engine narrative ------------------------------------------------------------------

def _kind_value(value: str, kind: str | None) -> Pair:
    if kind == "st":
        return _lower(_label("st.", value))
    if kind == "metrics":
        names = [METRICS.get(n, (n, n)) for n in value.split(", ")]
        return (", ".join(_lower(m)[0] for m in names), ", ".join(_lower(m)[1] for m in names))
    if kind == "check":
        return _label("q.", value)
    if kind == "num":
        return (value, value.replace(".", ","))
    return (value, value)


_CHECK_STATUS = re.compile(r"([A-Z_]+) \(([A-Z_]+)\): (.+)", re.S)
_CHECK_ONLY = re.compile(r"([A-Z_]+): (.+)", re.S)
_PREFIXED = re.compile(r"([^\s:][^:]*?): (.+)", re.S)


def narrate(text: str) -> Pair | None:
    """Localized presentation of an engine sentence, or None when no template covers the whole sentence."""
    found = _narrative_match(text)
    if found:
        index, values, kinds = found
        en, pt = _narrative_template(index)
        en_values = {k: _kind_value(v, kinds.get(k))[0] for k, v in values.items()}
        pt_values = {k: _kind_value(v, kinds.get(k))[1] for k, v in values.items()}
        return strip_kinds(en).format(**en_values), strip_kinds(pt).format(**pt_values)
    m = _CHECK_STATUS.fullmatch(text)
    if m and "q." + m.group(1) in UI:
        inner = narrate(m.group(3))
        if inner:
            check, status = _label("q.", m.group(1)), _lower(_label("st.", m.group(2)))
            return (f"{check[0]} ({status[0]}): {inner[0]}", f"{check[1]} ({status[1]}): {inner[1]}")
        return None
    m = _CHECK_ONLY.fullmatch(text)
    if m and "q." + m.group(1) in UI:
        inner = narrate(m.group(2))
        if inner:
            check = _label("q.", m.group(1))
            return (f"{check[0]}: {inner[0]}", f"{check[1]}: {inner[1]}")
        return None
    m = _PREFIXED.fullmatch(text)
    if m:
        inner = narrate(m.group(2))
        if inner:
            prefix = m.group(1)
            return (f"{prefix}: {inner[0]}", f"{prefix}: {inner[1]}")
    return None


# --- tones and icons -------------------------------------------------------------------

_TONE = {
    "pass": "pass", "executed": "pass", "improved": "pass", "killed": "pass",
    "fail": "fail", "regressed": "fail", "consistent_failure": "fail", "survived": "fail", "high": "fail",
    "historically_flaky": "fail", "observed_unstable_current_run": "fail",
    "blocked": "blocked", "medium": "warn", "findings": "warn", "needs_attention": "warn", "retire_candidate": "warn",
    "environment_specific": "warn", "bounded_by_unknowns": "warn",
    "unknown": "unknown", "not_run": "not_run", "insufficient_evidence": "unknown",
    "info": "neutral", "low": "neutral", "unchanged": "neutral", "changed": "neutral", "reused": "neutral",
    "no_findings_in_scope": "neutral", "full_suite": "neutral", "no_instability_observed": "neutral",
    "ready_for_review": "accent", "applied": "accent", "add": "accent", "modify": "accent", "proven_paths": "accent",
    "proposed": "accent",
}
_ICON = {"pass": "check", "fail": "cross", "blocked": "block", "warn": "alert", "unknown": "question", "not_run": "dash",
         "neutral": "dot", "accent": "dot"}


def _tone(raw: str) -> str:
    return _TONE.get(str(raw).lower(), "neutral")


class _R:
    def __init__(self, report: dict, lang: str):
        self.report, self.lang = report, lang
        self.used: dict[str, str] = {}  # key -> pt-BR text

    def pick(self, pair: Pair) -> str:
        return pair[1] if self.lang == "pt-BR" else pair[0]

    # --- localized nodes
    def node(self, key: str, pair: Pair, tag: str = "span", cls: str | None = None, attrs: str = "") -> str:
        self.used[key] = pair[1]
        klass = f' class="{cls}"' if cls else ""
        original = f' data-en="{_e(pair[0])}"' if self.lang != "en" else ""
        return f'<{tag}{klass} data-i18n="{key}"{original}{attrs}>{_e(self.pick(pair))}</{tag}>'

    def t(self, key: str, tag: str = "span", cls: str | None = None, attrs: str = "", n: Any = None, **args: Any) -> str:
        k, pair = _ui(key, n=n, **args)
        return self.node(k, pair, tag, cls, attrs)

    def p(self, pair: Pair, tag: str = "span", cls: str | None = None, attrs: str = "") -> str:
        if pair[0] == pair[1]:
            klass = f' class="{cls}"' if cls else ""
            return f"<{tag}{klass}{attrs}>{_e(pair[0])}</{tag}>"
        return self.node(_key(pair), pair, tag, cls, attrs)

    def s(self, key: str, n: Any = None, **args: Any) -> str:
        return self.pick(_ui(key, n=n, **args)[1])

    def attr(self, name: str, key: str, n: Any = None, **args: Any) -> str:
        k, pair = _ui(key, n=n, **args)
        self.used[k] = pair[1]
        original = f' data-en{name.replace("-", "")}="{_e(pair[0])}"' if self.lang != "en" else ""
        return f'{name}="{_e(self.pick(pair))}" data-i18n-{name}="{k}"{original}'

    def label_attr(self, key: str) -> str:
        return self.attr("data-label", key)

    def attr_text(self, key: str) -> str:
        """Translation hook for an element whose text is written directly (an <option>)."""
        k, pair = _ui(key)
        self.used[k] = pair[1]
        original = f' data-en="{_e(pair[0])}"' if self.lang != "en" else ""
        return f' data-i18n="{k}"{original}'

    def narr(self, text: str, tag: str = "span", cls: str | None = None) -> str:
        """Engine sentence: localized on a template match, otherwise as written (lang=en)."""
        pair = narrate(text)
        if pair:
            return self.p(pair, tag, cls)
        klass = f' class="{cls} raw-text"' if cls else ' class="raw-text"'
        return f'<{tag}{klass} lang="en">{_e(text)}</{tag}>'

    # --- small components
    def icon(self, name: str, cls: str = "ic") -> str:
        return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"></use></svg>'

    def pill(self, raw: str, prefix: str = "st.", tone: str | None = None) -> str:
        tone = tone or _tone(raw)
        key = prefix + str(raw)
        label = self.t(key) if key in UI else f"<span>{_e(_humanize(raw))}</span>"
        return f'<span class="pill tone-{tone}">{self.icon(_ICON[tone])}{label}</span>'

    def tier(self, tier: str | None) -> str:
        return self.t("tier." + tier if tier else "tier.none", cls="tier")

    def items(self, values: list[str], empty_key: str = "none", kind: str = "narr", limit: int = _LIST_LIMIT) -> str:
        if not values:
            return self.t(empty_key, tag="p", cls="empty")

        def one(v: str) -> str:
            return f"<li>{self.narr(v) if kind == 'narr' else '<code>' + _e(v) + '</code>'}</li>"

        head = "".join(one(v) for v in values[:limit])
        rest = values[limit:]
        more = (f'<details class="more"><summary>{self.t("show_all", n=len(values))}</summary>'
                f'<ul class="list">{"".join(one(v) for v in rest)}</ul></details>') if rest else ""
        return f'<ul class="list">{head}</ul>{more}'

    def state(self, key: str) -> str:
        return self.t("state." + key)

    def link(self, href: str, key: str, n: Any = None, **args: Any) -> str:
        return f'<a class="link" href="{href}">{self.t(key, n=n, **args)}{self.icon("arrow")}</a>'


# --- model readers (presentation only) -------------------------------------------------

def _states(report: dict) -> list[tuple[str, dict]]:
    return [(k, report["states"][k]) for k in _STATE_ORDER if report["states"].get(k)]


def _metric(state: dict | None, name: str) -> Any:
    return ((state or {}).get("metrics") or {}).get(name, {}).get("value")


def _checks(report: dict) -> list[dict]:
    q = report.get("candidate_qualification") or {}
    return [c for s in q.get("stages", []) for c in s["checks"]]


def _finding_meta(code: str) -> dict:
    return FINDINGS.get(code) or {}


def _sorted_findings(findings: list[dict]) -> list[tuple[int, dict]]:
    return sorted(enumerate(findings), key=lambda item: (_SEVERITY_ORDER.get(item[1]["severity"], 9), item[0]))


def _category(code: str) -> str:
    return _finding_meta(code).get("category") or "other"


def _recommendation_for(report: dict, code: str) -> str | None:
    return next((rec["recommendation"] for rec in report.get("recommendations") or [] if rec["finding"] == code), None)


def _severity_counts(findings: list[dict]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "info": 0}
    for f in findings:
        counts[f["severity"] if f["severity"] in ("high", "medium") else "info"] += 1
    return counts


def _finding_title(f: dict) -> Pair:
    meta = _finding_meta(f["code"])
    return meta["title"] if meta.get("title") else (_humanize(f["code"]), _humanize(f["code"]))


def _finding_summary(f: dict) -> Pair | None:
    summary = _finding_meta(f["code"]).get("summary")
    if summary and summary[0] == f["summary"]:
        return summary
    return narrate(f["summary"])


def _rec_pair(code: str, text: str) -> Pair | None:
    rec = _finding_meta(code).get("rec")
    if rec and rec[0] == text:
        return rec
    return narrate(text)


def _action(code: str, text: str) -> Pair | None:
    return ACTIONS.get(code) or _rec_pair(code, text)


def _next_step(report: dict) -> dict:
    """The next action only when the evidence ranks one; a tie is reported as a tie, never broken by guessing."""
    with_rec = [(i, f) for i, f in enumerate(report["findings"]) if _recommendation_for(report, f["code"])]
    for code in _FIRST:
        first = [(i, f) for i, f in with_rec if f["code"] == code]
        if first:
            return {"kind": "one", "items": first[:1]}
    if not with_rec:
        return {"kind": "none", "items": []}
    top = min(_SEVERITY_ORDER.get(f["severity"], 9) for _, f in with_rec)
    at_top = [(i, f) for i, f in with_rec if _SEVERITY_ORDER.get(f["severity"], 9) == top]
    if at_top[0][1]["severity"] not in ("high", "medium"):
        return {"kind": "optional", "items": at_top}
    return {"kind": "one" if len(at_top) == 1 else "tie", "items": at_top}


# --- evidence facts --------------------------------------------------------------------

def _confirmed(state: dict | None) -> list[tuple[Pair, str | None]]:
    """Positive facts backed by execution or deterministic evidence; never by the absence of a finding."""
    if not state:
        return []
    out: list[tuple[Pair, str | None]] = []
    tier = ((state.get("metrics") or {}).get("passed") or {}).get("evidence_tier")
    for run in state.get("runs", []):
        if run["status"] == "PASS" and run["invocations"]:
            if run["mode"] == "report":
                out.append((pair_of("conf.ingested", n=run["invocations"], adapter=run["adapter"]), tier))
            else:
                out.append((pair_of("conf.tests", n=run["invocations"], adapter=run["adapter"]), tier))
    for artifact in state.get("artifacts", []):
        if artifact["status"] == "PASS":
            out.append((pair_of("conf.artifact", kind=artifact["kind"]), "E0"))
    evaluated = _metric(state, "mutation_evaluated")
    if evaluated and not _metric(state, "mutation_survived") and not _metric(state, "mutation_no_coverage"):
        out.append((pair_of("conf.mutation", n=evaluated), "E0"))
    killed = _metric(state, "negative_controls_killed")
    if killed and not _metric(state, "negative_controls_survived") and not _metric(state, "negative_controls_invalid"):
        out.append((pair_of("conf.controls", n=killed), "E0"))
    return out


def _signals(state: dict | None) -> list[tuple[Pair, str]]:
    """Positive heuristic signals (E3): shown apart from confirmed facts, with less weight."""
    post = _metric(state, "negative_paths_with_state_after_rejection")
    return [(pair_of("signal.post_rejection", n=post), "E3")] if post else []


_SHORT_FIXED = {
    "no tests were executed; test outcomes are UNKNOWN": "short.no_tests",
    "whether declared CI checks actually ran, on which revision, and whether they gate merges": "short.ci",
    "coverage": "short.coverage",
    "mutation / negative-control strength": "short.mutation",
    "build, package and installed-artifact behavior": "short.artifact",
    "startup, health and deployment behavior": "short.deploy",
    "preview/deployment behavior: no authorized non-production preview adapter; production is never used to qualify tests": "short.preview",
    "preview/deployment behavior: no authorized non-production preview adapter": "short.preview",
}
_SHORT_MATRIX = re.compile(r"(\S+) (\S+): (.+), not executed")
_SHORT_SUITE = re.compile(r"full-suite outcome: (\d+) mapped test files were not run")


def _short_unknown(item: str, report: dict) -> Pair:
    """A short localized label for one 'not evidenced' entry of the claim boundary."""
    if item in _SHORT_FIXED:
        return pair_of(_SHORT_FIXED[item])
    m = _CHECK_STATUS.fullmatch(item)
    if m and "q." + m.group(1) in UI:
        check, status = _label("q.", m.group(1)), _lower(_label("st.", m.group(2)))
        return (f"{check[0]} ({status[0]})", f"{check[1]} ({status[1]})")
    m = _SHORT_MATRIX.fullmatch(item)
    if m:
        return pair_of("short.matrix", adapter=m.group(1), dimension=m.group(2))
    m = _SHORT_SUITE.fullmatch(item)
    if m:
        return pair_of("short.full_suite", n=int(m.group(1)))
    for state in report["states"].values():
        for a in (state or {}).get("artifacts", []):
            if item.startswith(f"{a['kind']} {a['artifact'] or '(not built)'}: "):
                return pair_of("short.artifact_kind", kind=a["kind"])
    return pair_of("short.other")


def _scope(report: dict) -> list[dict]:
    """What the audit examined and with which evidence strength. Values come only from the report model."""
    state = report["states"].get("current") or {}
    rows: list[dict] = []
    runs = state.get("runs", [])
    executed = [run for run in runs if run["mode"] != "report"]
    ingested = [run for run in runs if run["mode"] == "report"]
    if executed or ingested:
        group = executed or ingested
        total = sum(run["invocations"] for run in group)
        failing = [run for run in group if run["status"] in _BAD]
        unknown = [run for run in group if run["status"] in _OPEN]
        level = "FAILED" if failing else ("EXECUTED" if executed else "INGESTED")
        status = "FAIL" if failing else ("UNKNOWN" if unknown else "PASS")
        detail = pair_of("scope.tests.run", n=total, status=_lower(_label("st.", status)))
        if executed and ingested:
            detail = _join([detail, pair_of("scope.tests.also_ingested", n=sum(r["invocations"] for r in ingested))], (" · ", " · "))
        rows.append({"area": "tests", "level": level, "detail": detail, "href": "#runs"})
    elif _metric(state, "test_declarations") is not None:
        rows.append({"area": "tests", "level": "INSPECTED", "detail": pair_of("scope.tests.static", n=_metric(state, "test_declarations")), "href": "#metrics"})
    elif _metric(state, "weak_oracle_tests") is not None:
        rows.append({"area": "tests", "level": "INSPECTED", "detail": pair_of("scope.tests.static_only"), "href": "#domains"})
    else:
        rows.append({"area": "tests", "level": "NOT_EVIDENCED", "detail": pair_of("scope.tests.none"), "href": "#claim"})
    line, branch = _metric(state, "line_coverage"), _metric(state, "branch_coverage")
    if line is not None or branch is not None:
        parts = []
        if line is not None:
            parts.append(pair_of("scope.coverage.line", value=_num(line, "%", 1)))
        if branch is not None:
            parts.append(pair_of("scope.coverage.branch", value=_num(branch, "%", 1)))
        rows.append({"area": "coverage", "level": "MEASURED", "detail": _join(parts, (" · ", " · ")), "href": "#domains"})
    else:
        rows.append({"area": "coverage", "level": "NOT_EVIDENCED", "detail": pair_of("scope.coverage.none"), "href": "#claim"})
    weak = _metric(state, "weak_oracle_tests")
    if weak is not None:
        rows.append({"area": "quality", "level": "INSPECTED", "detail": pair_of("scope.quality", n=weak), "href": "#domains"})
    negative = _metric(state, "negative_path_tests")
    if negative:
        rows.append({"area": "negative", "level": "INSPECTED",
                     "detail": pair_of("scope.negative", n=negative, m=_num(_metric(state, "negative_paths_without_contract_detail") or 0)),
                     "href": "#negative-paths"})
    usable = [m for m in state.get("mutation", []) if not m["error"] and m["matches_state"] is not False]
    killed, survived = _metric(state, "negative_controls_killed"), _metric(state, "negative_controls_survived")
    if usable:
        rows.append({"area": "fault", "level": "INGESTED",
                     "detail": pair_of("scope.mutation", n=sum(m["evaluated"] or 0 for m in usable), m=_num(_metric(state, "mutation_survived") or 0)),
                     "href": "#mutation-evidence"})
    elif killed is not None or survived is not None:
        rows.append({"area": "fault", "level": "EXECUTED", "detail": pair_of("scope.controls", n=(killed or 0) + (survived or 0), m=_num(killed or 0)),
                     "href": "#domains"})
    else:
        rows.append({"area": "fault", "level": "NOT_EVIDENCED", "detail": pair_of("scope.fault.none"), "href": "#claim"})
    artifacts = state.get("artifacts", [])
    if artifacts:
        bad = [a for a in artifacts if a["status"] != "PASS"]
        kinds = ", ".join(sorted({a["kind"] for a in artifacts}))
        rows.append({"area": "artifact", "level": "FAILED" if any(a["status"] in _BAD for a in bad) else ("VERIFIED" if not bad else "PARTIAL"),
                     "detail": pair_of("scope.artifact.bad" if bad else "scope.artifact.ok", kind=kinds), "href": "#artifact-evidence"})
    else:
        rows.append({"area": "artifact", "level": "NOT_EVIDENCED", "detail": pair_of("scope.artifact.none"), "href": "#claim"})
    surface = report.get("verification_surface") or []
    ci = [c for c in surface if c["origin"] == "CI"]
    local = [c for c in surface if c["origin"] in ("LOCAL", "HOOK")]
    if ci:
        rows.append({"area": "ci", "level": "DECLARED", "detail": pair_of("scope.ci", n=len(ci)), "href": "#surface-section"})
    else:
        rows.append({"area": "ci", "level": "NOT_EVIDENCED", "detail": pair_of("scope.ci.none"), "href": "#surface-section"})
    if local:
        rows.append({"area": "local", "level": "DECLARED", "detail": pair_of("scope.local", n=len(local)), "href": "#surface-section"})
    rows.append({"area": "deploy", "level": "NOT_EVIDENCED", "detail": pair_of("scope.deploy"), "href": "#claim"})
    order = {"FAILED": 0, "VERIFIED": 1, "EXECUTED": 1, "PARTIAL": 2, "MEASURED": 3, "INGESTED": 3, "INSPECTED": 4, "DECLARED": 5, "NOT_EVIDENCED": 6}
    return sorted(rows, key=lambda row: order[row["level"]])


_STRENGTH = {"VERIFIED": 4, "EXECUTED": 4, "FAILED": 4, "MEASURED": 3, "INGESTED": 3, "PARTIAL": 2, "INSPECTED": 2, "DECLARED": 1, "NOT_EVIDENCED": 0}
_LEVEL_TONE = {"FAILED": "fail", "VERIFIED": "pass", "EXECUTED": "pass", "MEASURED": "info", "INGESTED": "info", "PARTIAL": "warn",
               "INSPECTED": "info", "DECLARED": "muted", "NOT_EVIDENCED": "unknown"}


# --- shared pieces ---------------------------------------------------------------------

# Evidence strength is a kind of evidence, not a scale: each level has its own glyph and label.
_LEVEL_GLYPH = {"VERIFIED": "checkc", "EXECUTED": "checkc", "FAILED": "crossc", "MEASURED": "half", "INGESTED": "half",
                "PARTIAL": "half", "INSPECTED": "diamond", "DECLARED": "ring", "NOT_EVIDENCED": "question"}
_LEVEL_TONE = {"FAILED": "fail", "VERIFIED": "pass", "EXECUTED": "pass", "MEASURED": "info", "INGESTED": "info", "PARTIAL": "warn",
               "INSPECTED": "info", "DECLARED": "muted", "NOT_EVIDENCED": "unknown"}


def _glyph(r: _R, level: str) -> str:
    return r.icon(_LEVEL_GLYPH[level], "ic lv")


def _legend(r: _R) -> str:
    items = "".join(f'<li class="tone-{_LEVEL_TONE[level]}">{_glyph(r, level)}{r.t("lvl." + level)}</li>'
                    for level in ("EXECUTED", "MEASURED", "INSPECTED", "DECLARED", "NOT_EVIDENCED"))
    return f'<ul class="legend" {r.attr("aria-label", "legend.label")}>{items}</ul>'


def _ledger_row(r: _R, area: Pair, level: str, detail: str, href: str | None = None, row_id: str = "") -> str:
    tone = _LEVEL_TONE[level]
    rid = f' id="{row_id}"' if row_id else ""
    more = f'<a class="l-go" href="{href}" {r.attr("aria-label", "ledger.open")}>{r.icon("arrow")}</a>' if href else ""
    return (f'<li class="lrow lvl-{level.lower()} tone-{tone}"{rid}><span class="l-area">{r.p(area)}</span>'
            f'<span class="l-level">{_glyph(r, level)}{r.t("lvl." + level)}</span>'
            f'<span class="l-detail">{detail}</span>{more}</li>')


def _basis(r: _R, tier: str | None) -> str:
    """Human evidence basis; the E-tier code stays visible as metadata."""
    if not tier:
        return r.t("tier.none", cls="basis")
    return f'<span class="basis">{r.t("basis." + tier)} <abbr class="tier-code" title="{_e(r.s("tier." + tier))}">{_e(tier)}</abbr></span>'


def _chip(r: _R, key: str, n: int, cls: str = "") -> str:
    return f'<span class="chip {cls}"><b>{n}</b>{r.t(key, n=n)}</span>'


def _sev_chips(r: _R, counts: dict[str, int]) -> str:
    chips = [_chip(r, "cnt." + sev, counts[sev], "sev-" + sev) for sev in ("high", "medium", "info") if counts[sev]]
    return "".join(chips)


# --- decision surface ---------------------------------------------------------------------

def _conclusion(r: _R) -> str:
    report = r.report
    tone, icon, headline, reason = _verdict(r)
    lines = []
    if report["workflow"] == "improve":
        lines.append(r.p(reason, tag="p", cls="c-reason"))
        delta = report.get("evidence_delta") or {}
        if delta:
            improved, regressed = len(delta.get("improved") or []), len(delta.get("regressed") or [])
            lines.append(f'<p class="c-chips">{_chip(r, "dc.improved", improved, "sev-pass" if improved else "zero")}'
                         f'{_chip(r, "dc.regressed", regressed, "sev-high" if regressed else "zero")}'
                         f'<a class="c-more" href="#delta">{r.t("conc.delta")}</a></p>')
        applied = bool(report["states"].get("applied"))
        lines.append(f'<p class="c-scope">{r.icon("checkc" if applied else "ring", "ic")}{r.t("story.applied" if applied else "story.not_applied")}</p>')
    if report["workflow"] != "improve":
        findings = report["findings"]
        if findings:
            lines.append(f'<p class="c-chips"><span class="c-total">{r.t("att.count", n=len(findings))}</span>{_sev_chips(r, _severity_counts(findings))}</p>')
        if report["status"] in ("UNKNOWN", "NO_FINDINGS_IN_SCOPE") or not findings:
            lines.append(r.p(reason, tag="p", cls="c-reason"))
        shape, evmode = _evidence_mode(r)
        glyph = {"solid": "checkc", "half": "half", "hollow": "diamond"}[shape]
        lines.append(f'<p class="c-scope mode-{shape}">{r.icon(glyph, "ic")}{r.p(evmode)}</p>')
    return (f'<div class="d-main"><p class="c-label" id="h-conclusion">{r.t("verdict.label")}</p>'
            f'<p class="c-headline">{r.icon(icon, "ic c-ic")}{r.p(headline)}</p>{"".join(lines)}</div>')


def _rail(r: _R) -> str:
    report = r.report
    head = f'<h2 id="h-next" class="rail-label">{r.icon("arrow")}{r.t("next.title")}</h2>'
    foot = r.t("next.no_auto", tag="p", cls="rail-foot")
    if report["workflow"] == "improve":
        status = report["status"]
        if status == "APPLIED":
            body, foot = r.t("next.applied", tag="p", cls="rail-act quiet"), ""
        elif status == "READY_FOR_REVIEW":
            body = (r.t("next.review", tag="p", cls="rail-act")
                    + f'<dl class="rail-dl"><div><dt>{r.t("next.why")}</dt><dd>{r.t("next.review.why")}</dd></div>'
                    f'<div><dt>{r.t("next.command")}</dt><dd><code>assertiva improve --approve &lt;change_id&gt;</code></dd></div></dl>'
                    + f'<a class="btn" href="#changes">{r.t("next.review.go")}{r.icon("arrow")}</a>')
        else:
            blockers = [c for c in _checks(report) if c["status"] in _BAD]
            if blockers:
                items = "".join(f'<li><a href="#check-{_e(c["check"])}">{r.p(_label("q.", c["check"]))}</a>{r.pill(c["status"])}</li>' for c in blockers)
                body = (r.t("next.unblock", tag="p", cls="rail-act")
                        + f'<dl class="rail-dl"><div><dt>{r.t("next.why")}</dt><dd>{r.t("next.unblock.why")}</dd></div>'
                        f'<div><dt>{r.t("next.blockers")}</dt><dd><ul class="rail-list">{items}</ul></dd></div></dl>'
                        + f'<a class="btn" href="#candidate">{r.t("next.unblock.go")}{r.icon("arrow")}</a>')
            else:
                body, foot = r.t("next.none", tag="p", cls="rail-act quiet"), ""
        return f'<aside class="rail" aria-labelledby="h-next">{head}{body}{foot}</aside>'
    step = _next_step(report)
    if step["kind"] == "one":
        index, f = step["items"][0]
        meta = _finding_meta(f["code"])
        act = _action(f["code"], _recommendation_for(report, f["code"]))
        rows = [("next.why", r.p(meta["why"]) if meta.get("why") else ""),
                ("next.origin", f'<a href="#finding-{index}">{r.p(_finding_title(f))}</a>{r.pill(f["severity"], prefix="severity.")}'),
                ("next.done", r.p(meta["close"]) if meta.get("close") else "")]
        dl = "".join(f"<div><dt>{r.t(k)}</dt><dd>{v}</dd></div>" for k, v in rows if v)
        body = ((r.p(act, tag="p", cls="rail-act") if act else "") + f'<dl class="rail-dl">{dl}</dl>'
                + f'<a class="btn" href="#finding-{index}-fix">{r.t("next.how")}{r.icon("arrow")}</a>')
    elif step["kind"] == "tie":
        severity = step["items"][0][1]["severity"]
        items = "".join(
            f'<li><a href="#finding-{i}">{r.p(_action(f["code"], _recommendation_for(report, f["code"])) or _finding_title(f))}</a></li>'
            for i, f in step["items"][:4]
        )
        more = r.t("decision.more", tag="li", cls="muted", n=len(step["items"]) - 4) if len(step["items"]) > 4 else ""
        body = (r.t("next.tie", tag="p", cls="rail-act", n=len(step["items"]), severity=_lower(pair_of("severity." + severity)))
                + f'<ul class="rail-list">{items}{more}</ul>' + r.t("next.tie.why", tag="p", cls="rail-note")
                + f'<a class="btn" href="#improvements">{r.t("next.plan")}{r.icon("arrow")}</a>')
    elif step["kind"] == "optional":
        body = r.t("next.optional", tag="p", cls="rail-act quiet") + f'<a class="btn ghost" href="#improvements">{r.t("next.optional.go")}{r.icon("arrow")}</a>'
    else:
        body, foot = r.t("next.none", tag="p", cls="rail-act quiet"), ""
    return f'<aside class="rail" aria-labelledby="h-next">{head}{body}{foot}</aside>'


def _fact(r: _R, cls: str, icon: str, title_key: str, figure: str, body: str, link: str = "") -> str:
    return (f'<section class="fact {cls}" aria-labelledby="h-{cls}"><h3 id="h-{cls}">{r.icon(icon)}{r.t(title_key)}</h3>'
            f'<p class="f-fig">{figure}</p>{body}{link}</section>')


def _bullets(r: _R, pairs: list[Pair], limit: int = 3) -> str:
    if not pairs:
        return ""
    more = r.t("decision.more", tag="li", cls="more-n", n=len(pairs) - limit) if len(pairs) > limit else ""
    return '<ul class="flist">' + "".join(f"<li>{r.p(p)}</li>" for p in pairs[:limit]) + more + "</ul>"


def _facts_audit(r: _R) -> str:
    report = r.report
    state = report["states"].get("current")
    confirmed, signals = _confirmed(state), _signals(state)
    conf_body = _bullets(r, [p for p, _ in confirmed]) if confirmed else r.t("conf.none.why", tag="p", cls="fnote")
    if signals:
        conf_body += (f'<p class="signal">{r.icon("diamond")}<span>{r.t("signal.label")}</span> {r.p(signals[0][0])}'
                      f'<abbr class="tier-code" title="{_e(r.s("tier.E3"))}">E3</abbr></p>')
    counts = _severity_counts(report["findings"])
    serious = [(i, f) for i, f in _sorted_findings(report["findings"]) if f["severity"] in ("high", "medium")]
    att_body = ""
    if serious:
        att_body = (f'<p class="f-chips">{_sev_chips(r, {**counts, "info": 0})}</p><ul class="flist links">'
                    + "".join(f'<li><a href="#finding-{i}">{r.p(_finding_title(f))}</a></li>' for i, f in serious[:2]) + "</ul>")
    if counts["info"]:
        att_body += r.t("att.info", tag="p", cls="fnote", n=counts["info"])
    not_evidenced = report["claim_boundary"].get("not_evidenced") or []
    shorts = [_short_unknown(item, report) for item in not_evidenced]
    return (
        f'<div class="facts"><h2 class="sr-only" id="h-facts">{r.t("strip.title")}</h2>'
        + _fact(r, "d-conf", "checkc", "conf.title", r.t("conf.count", n=len(confirmed)) if confirmed else r.t("conf.none", cls="quiet"),
                conf_body, r.link("#green", "conf.go"))
        + _fact(r, "d-att", "alert", "att.title", r.t("att.count", n=len(serious)) if serious else r.t("att.none", cls="quiet"),
                att_body, r.link("#findings", "att.go") if report["findings"] else "")
        + _fact(r, "d-unk", "question", "unk.title", r.t("unk.count", n=len(shorts)) if shorts else r.t("unk.none", cls="quiet"),
                _bullets(r, shorts), r.link("#green", "unk.go") if shorts else "")
        + "</div>"
    )


def _facts_improve(r: _R) -> str:
    report = r.report
    checks = _checks(report)
    passed = [c for c in checks if c["status"] == "PASS"]
    bad = [c for c in checks if c["status"] in _BAD]
    open_ = [c for c in checks if c["status"] in _OPEN]
    regressed = (report.get("evidence_delta") or {}).get("regressed") or []
    attention = [_label("q.", c["check"]) for c in bad] + [METRICS.get(d["name"], (d["name"], d["name"])) for d in regressed]
    unknown = [_label("q.", c["check"]) for c in open_] + [pair_of("short.preview")]
    return (
        f'<div class="facts"><h2 class="sr-only" id="h-facts">{r.t("strip.title")}</h2>'
        + _fact(r, "d-conf", "checkc", "conf.title", r.t("conf.checks", n=len(passed)) if passed else r.t("conf.none", cls="quiet"),
                _bullets(r, [_label("q.", c["check"]) for c in passed]), r.link("#candidate", "conf.go.checks"))
        + _fact(r, "d-att", "alert", "att.title", r.t("att.items", n=len(attention)) if attention else r.t("att.none.improve", cls="quiet"),
                _bullets(r, attention), r.link("#candidate", "att.go.checks") if attention else "")
        + _fact(r, "d-unk", "question", "unk.title", r.t("unk.count", n=len(unknown)), _bullets(r, unknown), r.link("#green", "unk.go"))
        + "</div>"
    )


_LIFE_GLYPH = {"done": ("checkc", "pass"), "partial": ("half", "warn"), "fail": ("crossc", "fail"), "pending": ("ring", "accent"), "todo": ("dash", "muted")}


def _lifecycle(r: _R) -> str:
    """Candidate lifecycle from the states the report holds; no step is shown as done without its evidence."""
    report = r.report
    checks = _checks(report)
    ready = bool((report.get("candidate_qualification") or {}).get("ready_for_review"))
    applied = bool(report["states"].get("applied"))
    blockers = [c for c in checks if c["status"] in _BAD]
    candidate = "done" if ready else ("partial" if any(c["status"] == "PASS" for c in checks) else "fail")
    steps = [
        ("baseline", "done" if report["states"].get("baseline") else "todo", "life.baseline." + ("done" if report["states"].get("baseline") else "todo"), {}),
        ("candidate", candidate, "life.candidate." + candidate, {}),
        ("review", "done" if ready else "fail", "life.review.ready" if ready else "life.review.blocked", {} if ready else {"n": len(blockers)}),
        ("approval", "done" if applied else ("pending" if ready else "todo"),
         "life.approval." + ("done" if applied else ("pending" if ready else "todo")), {}),
        ("applied", "done" if applied else "todo", "life.applied." + ("done" if applied else "todo"), {}),
        ("verify", "done" if applied else "todo", "life.verify." + ("done" if applied else "todo"), {}),
    ]
    items = "".join(
        f'<li class="step st-{state} tone-{_LIFE_GLYPH[state][1]}">{r.icon(_LIFE_GLYPH[state][0], "ic lv")}'
        f'<span class="step-name">{r.t("life." + name)}</span>{r.t(key, cls="step-state", **args)}</li>'
        for name, state, key, args in steps
    )
    return (f'<div class="life"><p class="mini-label" id="h-life">{r.t("life.title")}</p>'
            f'<ol class="steps" aria-labelledby="h-life">{items}</ol></div>')


def _scope_strip(r: _R) -> str:
    """The audit scope at a glance: every area with its kind of evidence (detail in "What does green prove?")."""
    items = "".join(
        f'<li class="tone-{_LEVEL_TONE[row["level"]]}"><a href="#scope-{row["area"]}">{_glyph(r, row["level"])}'
        f'<span class="ss-area">{r.t("area." + row["area"])}</span><span class="ss-level">{r.t("lvl." + row["level"])}</span></a></li>'
        for row in _scope(r.report)
    )
    return (f'<div class="scope-strip"><p class="mini-label" id="h-scope-strip">{r.t("scope.title")}</p>'
            f'<ul aria-labelledby="h-scope-strip">{items}</ul></div>')


def _identity(r: _R) -> str:
    report = r.report
    project = report["project"]
    if report["workflow"] == "audit":
        mode = "mode.audit"
    else:
        mode = "mode.improve_applied" if report["states"].get("applied") else "mode.improve"
    revision = project.get("revision")
    revision_html = f'<code title="{_e(revision)}">{_e(revision[:12])}</code>' if revision else r.t("header.no_revision")
    dirty = bool(project.get("dirty"))
    when = r.p(_when(report["generated_at"]), tag="time", attrs=f' datetime="{_e(report["generated_at"])}" data-local')
    states = _ARROW_SEP.join(r.state(k) for k, _ in _states(report)) if report["workflow"] == "improve" else ""
    return (
        f'<div class="ident"><p class="eyebrow">{r.t(mode)}</p><h1 id="h-project">{_e(project.get("name") or "project")}</h1>'
        f'<dl class="idline"><div><dt>{r.t("header.revision")}</dt><dd>{revision_html}</dd></div>'
        f'<div><dt>{r.t("prov.state")}</dt><dd class="ws {"dirty" if dirty else "clean"}">{r.t("header.dirty" if dirty else "header.clean")}</dd></div>'
        f'<div><dt>{r.t("prov.generated")}</dt><dd>{when}</dd></div>'
        + (f'<div><dt>{r.t("states.shown")}</dt><dd>{states}</dd></div>' if states else "")
        + "</dl></div>"
    )


def _decision(r: _R) -> str:
    tone = _verdict(r)[0]
    improve = r.report["workflow"] == "improve"
    facts = _facts_improve(r) if improve else _facts_audit(r)
    return (f'{_identity(r)}<section class="decision tone-{tone}" aria-labelledby="h-conclusion">'
            f'{_conclusion(r)}{_rail(r)}<div class="d-extra">{_lifecycle(r) if improve else _scope_strip(r)}</div>{facts}</section>')


# --- "What does green prove?" ------------------------------------------------------------

def _green_audit(r: _R) -> str:
    report = r.report
    rows = "".join(
        _ledger_row(r, pair_of("area." + row["area"]), row["level"], r.p(row["detail"]), row.get("href"), f"scope-{row['area']}")
        for row in _scope(report)
    )
    return (
        f'<section id="green" class="sub green" aria-labelledby="h-green">'
        f'<div class="sub-head"><h2 id="h-green">{r.t("green.title")}</h2>{r.t("green.lead.audit", tag="p", cls="lead")}</div>'
        f'<ol class="ledger" {r.attr("aria-label", "scope.title")}>{rows}</ol>'
        f'<div class="ledger-foot">{_legend(r)}{_limitations(r, report["claim_boundary"].get("limitations") or [])}'
        f'{r.link("#claim", "green.full")}</div></section>'
    )


def _check_summary(report: dict, c: dict) -> Pair | None:
    return (narrate(c["summary"]) or (_artifact_summary(report) if c["check"] == "BUILD_AND_ARTIFACT" else None)
            or (pair_of("qsum." + c["status"]) if "qsum." + c["status"] in UI else None))


def _green_improve(r: _R) -> str:
    report = r.report
    rows = []
    for c in sorted(_checks(report), key=lambda c: {"FAIL": 0, "BLOCKED": 0, "UNKNOWN": 1, "NOT_RUN": 1}.get(c["status"], 2)):
        level = {"PASS": "VERIFIED", "FAIL": "FAILED", "BLOCKED": "FAILED"}.get(c["status"], "NOT_EVIDENCED")
        summary = _check_summary(report, c)
        rows.append(_ledger_row(r, _label("q.", c["check"]), level, r.p(summary, cls="l-sum") if summary else "", f"#check-{c['check']}"))
    rows.append(_ledger_row(r, pair_of("area.deploy"), "NOT_EVIDENCED", r.t("scope.preview"), "#claim"))
    return (
        f'<section id="green" class="sub green" aria-labelledby="h-green">'
        f'<div class="sub-head"><h2 id="h-green">{r.t("green.title")}</h2>{r.t("green.lead.improve", tag="p", cls="lead")}</div>'
        f'<ol class="ledger" {r.attr("aria-label", "qual.title")}>{"".join(rows)}</ol>'
        f'<div class="ledger-foot">{_limitations(r, report["claim_boundary"].get("limitations") or [])}{r.link("#claim", "green.full")}</div></section>'
    )


def _overview(r: _R) -> str:
    improve = r.report["workflow"] == "improve"
    green = _green_improve(r) if improve else _green_audit(r)
    return (f'<section id="overview" class="area area-overview" data-layer="decision" aria-labelledby="h-project">'
            f"{_decision(r)}{green}</section>")


# --- findings ----------------------------------------------------------------------------

def _finding(r: _R, index: int, f: dict) -> str:
    code, report = f["code"], r.report
    meta = _finding_meta(code)
    evidence = f.get("evidence") or {}
    affected, listed = _affected(evidence)
    rec = _recommendation_for(report, code)
    category = _category(code)
    fid = f"finding-{index}"
    why = meta.get("why")
    severity = f["severity"]
    compact = severity not in ("high", "medium")
    summary = _finding_summary(f)
    meta_bits = [r.t("cat." + category)]
    if affected:
        meta_bits.append(r.p(affected))
    meta_bits.append(_basis(r, meta.get("tier")))
    observed = r.p(summary, tag="p") if summary else (r.t("finding.observed.original", tag="p") + f'<p class="original" lang="en">{_e(f["summary"])}</p>')
    other = {k: v for k, v in evidence.items() if not isinstance(v, (list, dict)) and k not in _COUNT_KEYS}
    kv = "".join(f"<dt><code>{_e(k)}</code></dt><dd><code>{_e(v)}</code></dd>" for k, v in other.items())
    evidence_html = ((f'<p class="affected">{r.p(affected)}</p>' if affected else "")
                     + (r.items(listed, kind="code", limit=8) if listed else "") + (f'<dl class="kv">{kv}</dl>' if kv else ""))
    blocks = [f'<div class="f-block"><h4>{r.t("finding.observed")}</h4>{observed}</div>']
    if why and compact:
        blocks.append(f'<div class="f-block"><h4>{r.t("finding.why")}</h4>{r.p(why, tag="p")}</div>')
    blocks.append(f'<div class="f-block" id="{fid}-evidence"><h4>{r.t("finding.evidence")}</h4>{evidence_html or r.t("finding.no_items", tag="p", cls="empty")}</div>')
    if rec:
        rec_pair = _rec_pair(code, rec)
        rec_html = r.p(rec_pair, tag="p") if rec_pair else f'<p lang="en" class="raw-text">{_e(rec)}</p>'
        blocks.append(f'<div class="f-block f-fix" id="{fid}-fix"><h4>{r.t("finding.recommendation")}<span class="pill tone-accent">{r.t("proposed.short")}</span></h4>'
                      f"{rec_html}</div>")
    if meta.get("close"):
        blocks.append(f'<div class="f-block"><h4>{r.t("finding.close")}</h4>{r.p(meta["close"], tag="p")}</div>')
    blocks.append(
        f'<details class="tech"><summary>{r.t("finding.technical")}</summary><dl class="kv">'
        f'<dt>{r.t("finding.code")}</dt><dd><code>{_e(code)}</code></dd><dt>{r.t("finding.basis")}</dt><dd>{r.tier(meta.get("tier"))}</dd>'
        f'<dt>{r.t("original")}</dt><dd lang="en">{_e(f["summary"])}</dd></dl>'
        f'<p class="tech-label">{r.t("finding.raw")}</p><pre class="code">{_e(json.dumps(evidence, indent=2, ensure_ascii=False))}</pre></details>'
    )
    return (
        f'<details class="finding sev-{_e(severity)}{" compact" if compact else ""}" id="{fid}" data-severity="{_e(severity)}" data-category="{_e(category)}">'
        f'<summary class="f-row" data-layer="decision"><span class="f-sev">{r.pill(severity, prefix="severity.")}</span>'
        f'<h3 class="f-title" id="{fid}-t">{r.p(_finding_title(f))}</h3>'
        + (r.p(why, cls="f-why") if why and not compact else "")
        + f'<span class="f-meta">{_DOT_SEP.join(meta_bits)}</span>{r.icon("chev", "ic chev")}</summary>'
        f'<div class="f-body">{"".join(blocks)}</div></details>'
    )


def _findings_area(r: _R) -> str:
    report = r.report
    findings = report["findings"]
    counts = _severity_counts(findings)
    head = (f'<div class="area-head"><h2 id="h-findings">{r.t("findings.title")}</h2>'
            + (f'<p class="lead"><span class="chips">{_sev_chips(r, counts)}</span> {r.t("findings.lead")}</p>'
               if findings else r.t("findings.none", tag="p", cls="lead")) + "</div>")
    if not findings:
        return f'<section id="findings" class="area" aria-labelledby="h-findings">{head}</section>'
    categories = sorted({_category(f["code"]) for f in findings})
    sev_options = "".join(f'<option value="{s}"{r.attr_text("severity." + s)}>{_e(r.s("severity." + s))}</option>' for s in ("high", "medium", "info") if counts[s])
    cat_options = "".join(f'<option value="{c}"{r.attr_text("cat." + c)}>{_e(r.s("cat." + c))}</option>' for c in categories)
    empty_attrs = ' id="findings-empty" hidden'
    filters = (
        f'<div class="filters" role="search"><label for="sev">{r.t("findings.filter.severity")}</label>'
        f'<select id="sev" class="select"><option value=""{r.attr_text("findings.filter.all")}>{_e(r.s("findings.filter.all"))}</option>{sev_options}</select>'
        f'<label for="cat">{r.t("findings.filter.category")}</label>'
        f'<select id="cat" class="select"><option value=""{r.attr_text("findings.filter.all")}>{_e(r.s("findings.filter.all"))}</option>{cat_options}</select>'
        f'<label for="q" class="sr-only">{r.t("findings.filter.search")}</label>'
        f'<input id="q" class="search" type="search" {r.attr("placeholder", "findings.filter.search")}>'
        f'<button type="button" id="clear-filters" class="btn ghost small" hidden>{r.t("findings.filter.clear")}</button>'
        f'<span id="findings-count" class="muted" aria-live="polite"></span></div>'
        f'{r.t("findings.filter.empty", tag="p", cls="empty", attrs=empty_attrs)}'
    ) if len(findings) > 3 else ""
    cards = "".join(_finding(r, i, f) for i, f in _sorted_findings(findings))
    return f'<section id="findings" class="area" aria-labelledby="h-findings">{head}{filters}<div class="finding-list">{cards}</div></section>'


# --- improvements: a prioritized plan --------------------------------------------------------

def _improvements_area(r: _R) -> str:
    report = r.report
    recs = report.get("recommendations") or []
    head = f'<div class="area-head"><h2 id="h-improvements">{r.t("improve.title")}</h2>{r.t("improve.lead", tag="p", cls="lead")}</div>'
    if not recs:
        return f'<section id="improvements" class="area" aria-labelledby="h-improvements">{head}{r.t("improve.none", tag="p", cls="empty")}</section>'
    index_of = {f["code"]: i for i, f in enumerate(report["findings"])}
    step = _next_step(report)
    first = {f["code"] for _, f in step["items"]} if step["kind"] == "one" else set()
    groups: dict[str, list[dict]] = {"first": [], "high": [], "medium": [], "info": []}
    for rec in recs:
        index = index_of.get(rec["finding"])
        f = report["findings"][index] if index is not None else {"code": rec["finding"], "severity": "medium", "summary": ""}
        group = "first" if rec["finding"] in first else ("info" if f["severity"] in ("info", "low") else f["severity"])
        groups[group].append({"rec": rec, "finding": f, "index": index})
    out = []
    number = 0
    for group in ("first", "high", "medium", "info"):
        items = groups[group]
        if not items:
            continue
        rows = []
        for item in items:
            number += 1
            rec, f, index = item["rec"], item["finding"], item["index"]
            code = rec["finding"]
            meta = _finding_meta(code)
            act = _action(code, rec["recommendation"]) or (rec["recommendation"], rec["recommendation"])
            text = _rec_pair(code, rec["recommendation"])
            link = f'<a href="#finding-{index}">{r.p(_finding_title(f))}</a>' if index is not None else f"<code>{_e(code)}</code>"
            rows.append(
                f'<li class="rec" id="rec-{_e(code)}"><details{" open" if group == "first" else ""}><summary>'
                f'<span class="rec-n" aria-hidden="true">{number:02d}</span><span class="rec-main">{r.p(act, cls="rec-act")}'
                + (r.p(meta["why"], cls="rec-why") if meta.get("why") else "")
                + f'</span><span class="rec-side">{r.pill(f["severity"], prefix="severity.")}<span class="pill tone-accent">{r.t("proposed.short")}</span></span>'
                f'{r.icon("chev", "ic chev")}</summary><div class="rec-body">'
                + (r.p(text, tag="p", cls="rec-text") if text else f'<p class="rec-text raw-text" lang="en">{_e(rec["recommendation"])}</p>')
                + '<dl class="rec-meta">'
                + f'<div><dt>{r.t("improve.related")}</dt><dd>{link}</dd></div>'
                + f'<div><dt>{r.t("improve.area")}</dt><dd>{r.t("cat." + _category(code))}</dd></div>'
                + (f'<div><dt>{r.t("improve.closes")}</dt><dd>{r.p(meta["close"])}</dd></div>' if meta.get("close") else "")
                + f'<div><dt>{r.t("improve.state")}</dt><dd><ol class="rec-states"><li class="on">{r.t("rec.proposed")}</li>'
                f'<li>{r.t("rec.applied")}</li><li>{r.t("rec.verified")}</li></ol></dd></div>'
                + "</dl></div></details></li>"
            )
        note = r.t("improve.tie", tag="p", cls="group-note", n=len(step["items"])) if step["kind"] == "tie" and group == step["items"][0][1]["severity"] else ""
        out.append(f'<section class="rec-group g-{group}" aria-labelledby="h-rec-{group}"><h3 id="h-rec-{group}">{r.t("improve.group." + group)}'
                   f'<span class="count">{len(items)}</span></h3>{note}<ol class="rec-list">{"".join(rows)}</ol></section>')
    return f'<section id="improvements" class="area" data-layer="decision" aria-labelledby="h-improvements">{head}{"".join(out)}</section>'


# --- evidence snapshot -----------------------------------------------------------------------

def _tile(r: _R, domain: str, level: str, value: str, label: str, sub: str = "", change: str = "", tone: str | None = None) -> str:
    tone = tone or _LEVEL_TONE[level]
    return (f'<div class="tile tone-{tone}"><p class="t-domain">{_glyph(r, level)}{r.t("metrics.group." + domain)}</p>'
            f'<p class="t-value">{value}</p><p class="t-label">{label}</p>{sub}{change}</div>')


def _snapshot(r: _R) -> str:
    report = r.report
    states = _states(report)
    if not states:
        return ""
    key, main = states[-1]
    base = states[0][1] if len(states) > 1 else None

    def num(state, name, digits=1):
        metric = ((state or {}).get("metrics") or {}).get(name)
        return r.p(_num(metric["value"], metric.get("unit"), digits)) if metric and metric.get("value") is not None else "—"

    def change(name):
        if not base:
            return ""
        bucket = _delta_state(report, name)
        if not bucket or bucket == "unchanged":
            return f'<p class="t-change same">{r.t("snap.unchanged")}</p>'
        note = next((d.get("note") for items in (report.get("evidence_delta") or {}).values() for d in items if d["name"] == name and d.get("note")), None)
        return (f'<p class="t-change dm-{bucket}">{r.state(states[0][0])} {num(base, name)}{_ARROW_SEP}{num(main, name)}'
                f' <span class="dmark dm-{bucket}">{r.t("st." + bucket)}</span></p>' + (r.narr(note, tag="p", cls="t-note") if note else ""))

    tiles = []
    invocations, passed = _metric(main, "test_invocations"), _metric(main, "passed")
    if invocations is not None and passed is not None:
        failing = (_metric(main, "failed") or 0) + (_metric(main, "errors") or 0) + (_metric(main, "collection_errors") or 0)
        sub = r.t("snap.failing", tag="p", cls="t-sub bad", n=failing) if failing else ""
        tiles.append(_tile(r, "execution", "FAILED" if failing else "EXECUTED", f'{num(main, "passed")}<span class="of">/</span>{num(main, "test_invocations")}',
                           r.t("snap.passed"), sub, change("passed")))
    line = _metric(main, "line_coverage")
    if line is not None:
        branch = _metric(main, "branch_coverage")
        sub = f'<p class="t-sub">{r.t("snap.branches", value=_num(branch, "%", 1))}</p>' if branch is not None else ""
        tiles.append(_tile(r, "coverage", "MEASURED", num(main, "line_coverage"), r.t("snap.lines"), sub, change("line_coverage")))
    weak = _metric(main, "weak_oracle_tests")
    if weak is not None:
        broad = _metric(main, "broad_error_expectations") or 0
        sub = r.t("snap.broad", tag="p", cls="t-sub", n=broad) if broad else ""
        tiles.append(_tile(r, "static", "INSPECTED", num(main, "weak_oracle_tests"), r.t("snap.weak", n=weak), sub, change("weak_oracle_tests"),
                           tone="warn" if weak else "info"))
    negative = _metric(main, "negative_path_tests")
    if negative:
        missing = _metric(main, "negative_paths_without_contract_detail") or 0
        sub = r.t("snap.incomplete", tag="p", cls="t-sub", n=missing) if missing else ""
        tiles.append(_tile(r, "negative", "INSPECTED", num(main, "negative_path_tests"), r.t("snap.negative", n=negative), sub, change("negative_path_tests")))
    killed, survived = _metric(main, "negative_controls_killed"), _metric(main, "negative_controls_survived")
    evaluated = _metric(main, "mutation_evaluated")
    if killed is not None or survived is not None:
        total = (killed or 0) + (survived or 0)
        tiles.append(_tile(r, "fault", "FAILED" if survived else "EXECUTED", f'{_e(killed or 0)}<span class="of">/</span>{_e(total)}',
                           r.t("snap.controls"), "", change("negative_controls_killed")))
    elif evaluated:
        mutants = _metric(main, "mutation_survived") or 0
        tiles.append(_tile(r, "fault", "FAILED" if mutants else "INGESTED", num(main, "mutation_survived"), r.t("snap.survivors", n=mutants),
                           r.t("snap.evaluated", tag="p", cls="t-sub", n=evaluated)))
    qualified = _metric(main, "artifact_qualified")
    if qualified is not None:
        tiles.append(_tile(r, "artifact", "VERIFIED" if qualified else "FAILED", r.t("yes.qualified" if qualified else "no.qualified"),
                           r.t("dom.artifact"), "", change("artifact_qualified")))
    if not tiles:
        return ""
    note = r.t("snap.state", tag="p", cls="lead", state=pair_of("state." + key)) if base else ""
    return (f'<section id="domains" class="sub" aria-labelledby="h-domains">{_section_head(r, "domains", "dom.title", "dom.lead")}{note}'
            f'<div class="tiles">{"".join(tiles)}</div></section>')


def _evidence_area(r: _R) -> str:
    panels = (_metrics_panel(r) + _surface(r) + _runs(r) + _negative(r) + _mutation(r) + _artifacts(r)
              + _delivery(r) + _selection(r) + _history(r))
    return (f'<section id="evidence" class="area" aria-labelledby="h-evidence"><div class="area-head"><h2 id="h-evidence">{r.t("evidence.title")}</h2>'
            f'{r.t("evidence.lead", tag="p", cls="lead")}</div>{_snapshot(r)}<div class="panels-d">{panels}</div></section>')


# --- improve: candidate pillars ---------------------------------------------------------------

def _check_row(r: _R, c: dict) -> str:
    pair = _check_summary(r.report, c)
    summary = r.p(pair, tag="p", cls="q-sum") if pair else ""
    lims = list(c.get("limitations") or [])
    tech = (f'<details class="tech"><summary>{r.t("finding.technical")}</summary><dl class="kv"><dt>{r.t("original")}</dt>'
            f'<dd lang="en">{_e(c["summary"])}</dd><dt>{r.t("finding.code")}</dt><dd><code>{_e(c["check"])}</code> <code>{_e(c["status"])}</code></dd></dl>'
            + (f'<p class="tech-label">{r.t("surface.limitations")}</p>{r.items(lims, limit=50)}' if lims else "") + "</details>")
    return (f'<li class="qrow st-{_e(c["status"].lower())}" id="check-{_e(c["check"])}">{r.pill(c["status"])}'
            f'<div class="q-main"><p class="q-name">{r.p(_label("q.", c["check"]))}</p>{summary}{tech}</div></li>')


def _pillar(r: _R, s: dict) -> str:
    checks = s["checks"]
    passed = sum(c["status"] == "PASS" for c in checks)
    first = next((c for c in checks if c["status"] != "PASS"), None)
    if first:
        summary = _check_summary(r.report, first)
        reason = r.p(_label("q.", first["check"]), cls="p-check") + (": " + r.p(summary) if summary else "")
    else:
        reason = r.t("pillar.all", n=len(checks))
    status = s["status"]
    return (
        f'<details class="pillar st-{_e(status.lower())}" id="pillar-{_e(s["stage"])}"{" open" if status in _BAD else ""}>'
        f'<summary>{r.pill(status)}<span class="p-main"><h3 class="p-name" id="h-p-{_e(s["stage"])}">{r.p(_label("q.", s["stage"]))}</h3>'
        f'<span class="p-reason">{reason}</span></span><span class="p-count">{passed}/{len(checks)}</span>{r.icon("chev", "ic chev")}</summary>'
        f'<ol class="qlist">{"".join(_check_row(r, c) for c in checks)}</ol></details>'
    )


def _candidate_area(r: _R) -> str:
    report = r.report
    q = report.get("candidate_qualification")
    head = f'<div class="area-head"><h2 id="h-candidate">{r.t("cand.title")}</h2>{r.t("cand.lead", tag="p", cls="lead")}</div>'
    if not q:
        return f'<section id="candidate" class="area" aria-labelledby="h-candidate">{head}</section>'
    order = {"FAIL": 0, "BLOCKED": 0, "UNKNOWN": 1, "NOT_RUN": 1}
    pillars = "".join(_pillar(r, s) for s in sorted(q["stages"], key=lambda s: order.get(s["status"], 2)))
    records = (q.get("stability") or {}).get("records") or []
    reruns = ""
    if records:
        rows = "".join(
            f'<tr><th scope="row"><code>{_e(rec["invocation_id"])}</code></th><td {r.label_attr("qual.outcomes")}><code>{_e(" / ".join(o or "?" for o in rec["outcomes"]))}</code></td>'
            f'<td {r.label_attr("qual.durations")} class="num-col"><code>{_e(" / ".join(f"{d:.3f}s" if d is not None else "?" for d in rec["durations_s"]))}</code></td>'
            f'<td {r.label_attr("qual.verdict")}>{r.pill(rec["verdict"])}</td></tr>' for rec in records
        )
        reruns = _panel(r, "reruns", "qual.reruns", r.t("qual.reruns.summary", n=len(records)),
                        f'<div class="table-wrap"><table class="responsive"><caption>{r.t("qual.reruns")}</caption><thead><tr><th scope="col">{r.t("hist.invocation")}</th>'
                        f'<th scope="col">{r.t("qual.outcomes")}</th><th scope="col">{r.t("qual.durations")}</th><th scope="col">{r.t("qual.verdict")}</th></tr></thead>'
                        f"<tbody>{rows}</tbody></table></div>", "qual.reruns.lead")
    return (f'<section id="candidate" class="area" data-layer="decision" aria-labelledby="h-candidate">{head}'
            f'<div class="pillars">{pillars}</div>{_changes(r)}<div class="panels-d">{reruns}</div></section>')


# --- technical details -------------------------------------------------------------------------

_CLAIM_DOMAINS = (
    ("deploy", ("deploy", "preview", "health", "startup")),
    ("artifact", ("artifact", "wheel", "sdist", "build", "package", "install", "bundle")),
    ("ci", ("ci ", " ci", "pipeline", "delivery", "gating", "gate ", "reproduced", "hook", "declared verification", "verification check")),
    ("fault", ("mutation", "mutant", "negative control", "negative-control")),
    ("coverage", ("coverage", "denominator")),
    ("static", ("static", "inventory", "ast ", "oracle", "heuristic")),
    ("tests", ("invocation", "executed", "collected", "test", "run ", "runner", "suite")),
)


def _claim_domain(text: str) -> str:
    lowered = f" {text.lower()} "
    return next((name for name, words in _CLAIM_DOMAINS if any(w in lowered for w in words)), "other")


def _claim(r: _R) -> str:
    boundary = r.report["claim_boundary"]
    groups = []
    for name, key in (("not_evidenced", "claim.not"), ("limitations", "claim.limits"), ("observed", "claim.observed")):
        values = boundary.get(name) or []
        by: dict[str, list[str]] = {}
        for value in values:
            by.setdefault(_claim_domain(value), []).append(value)
        index = "".join(f'<li><a href="#claim-{name}-{d}">{r.t("area." + d)}</a><span class="count">{len(v)}</span></li>' for d, v in by.items())
        body = "".join(
            f'<div class="cd" id="claim-{name}-{d}"><p class="cd-head">{r.t("area." + d)}<span class="count">{len(v)}</span></p>'
            f'{r.items(v, limit=50)}</div>' for d, v in by.items()
        )
        groups.append(
            f'<details class="claim-g cg-{name}"{" open" if len(values) <= 6 else ""}><summary><span class="cg-title">{r.t(key)}<span class="count">{len(values)}</span></span>'
            f'<ul class="cd-index">{index}</ul>{r.icon("chev", "ic chev")}</summary><div class="cg-body">{body or r.t("none", tag="p", cls="empty")}</div></details>'
        )
    return (f'<section id="claim" class="sub" aria-labelledby="h-claim">{_section_head(r, "claim", "claim.title", "claim.lead")}'
            f'<div class="claim-groups">{"".join(groups)}</div></section>')


def _provenance(r: _R) -> str:
    from . import __version__ as rendered_by

    report = r.report
    project, prov = report["project"], report.get("provenance") or {}
    runtime = prov.get("runtime") or {}
    runs = [run for _, s in _states(report) for run in s.get("runs", [])]
    executed = any(run["mode"] != "report" for run in runs)
    mode = f'<code>{_e(report["workflow"])}</code> · ' + r.t("prov.executed" if executed else ("prov.ingested" if runs else "prov.static"))
    runners = sorted({run["adapter"] for run in runs} | set(prov.get("adapters") or []))
    produced = prov.get("assertiva_version")
    identity = f'<code>{_e(produced)}</code>'
    if runtime.get("install"):
        identity += " " + r.t("prov.install." + runtime["install"], cls="muted")
    if runtime.get("revision"):
        identity += f' <code title="{_e(runtime["revision"])}">{_e(runtime["revision"][:10])}</code>' + (r.t("prov.dirty_runtime", cls="ws dirty") if runtime.get("dirty") else "")
    compact = [
        ("prov.version", identity),
        ("prov.revision", f'<code title="{_e(project.get("revision") or "")}">{_e((project.get("revision") or "—")[:12])}</code>'),
        ("prov.state", r.t("header.dirty" if project.get("dirty") else "header.clean")),
        ("prov.mode", mode),
        ("prov.adapters", " ".join(f"<code>{_e(a)}</code>" for a in runners) or "—"),
        ("prov.generated", r.p(_when(report["generated_at"]), tag="time", attrs=f' datetime="{_e(report["generated_at"])}" data-local')),
    ]
    warning = (r.t("prov.mismatch", tag="p", cls="prov-warn", a=str(produced), b=rendered_by)
               if produced and produced != rendered_by else "")
    full = [
        ("prov.revision", f'<code class="wrap">{_e(project.get("revision") or "—")}</code>'),
        ("prov.generated_utc", f'<code>{_e(report["generated_at"])}</code>'),
        ("prov.root", f'<code class="wrap">{_e(project.get("root"))}</code>'),
        ("prov.produced", f"<code>{_e(produced)}</code>"),
        ("prov.rendered", f"<code>{_e(rendered_by)}</code>"),
    ]
    if runtime:
        full.append(("prov.runtime", f'<code class="wrap">{_e(json.dumps(runtime, ensure_ascii=False))}</code>'))
    if prov.get("interpreter"):
        full.append(("prov.interpreter", f'<code class="wrap">{_e(prov["interpreter"])}</code>'))
    if "read_only_verified" in prov:
        full.append(("prov.readonly", r.t("yes" if prov["read_only_verified"] else "no")))
    if "read_only_until_approval" in prov:
        full.append(("prov.until", r.t("yes" if prov["read_only_until_approval"] else "no")))
    if project.get("baseline_digest"):
        full.append(("prov.digest", f'<code class="wrap">{_e(project["baseline_digest"])}</code>'))
    full.append(("prov.trace", f'<code class="wrap">{_e(prov["trace"])}</code>' if prov.get("trace") else r.t("prov.unavailable")))
    full.append(("prov.status", f'<code>{_e(report["status"])}</code>'))
    full.append(("prov.report_version", f'<code>{_e(report.get("report_version"))}</code>'))
    pairs = "".join(f"<div><dt>{r.t(k)}</dt><dd>{v}</dd></div>" for k, v in compact)
    more = "".join(f"<dt>{r.t(k)}</dt><dd>{v}</dd>" for k, v in full)
    return (f'<section id="provenance" class="sub" aria-labelledby="h-provenance">{_section_head(r, "provenance", "prov.title")}'
            f'{warning}<dl class="prov">{pairs}</dl><details class="more"><summary>{r.t("prov.more")}</summary><dl class="kv">{more}</dl></details></section>')


def _raw(r: _R) -> str:
    data = json.dumps(r.report, indent=2, ensure_ascii=False, default=str)
    body = f'<div class="cmd"><div class="cmd-head">{r.t("raw.summary")}{_copy(r)}</div><pre class="code raw-json">{_e(data)}</pre></div>'
    return _panel(r, "raw", "raw.title", r.t("raw.summary"), body, "raw.lead")


def _details_area(r: _R) -> str:
    return (f'<section id="details" class="area area-tech" aria-labelledby="h-details"><div class="area-head"><h2 id="h-details">{r.t("details.title")}</h2>'
            f'{r.t("details.lead", tag="p", cls="lead")}</div>{_provenance(r)}{_claim(r)}{_unknowns(r)}<div class="panels-d">{_budget(r)}{_raw(r)}</div></section>')


# --- retained evidence panels and helpers ------------------------------------------------

def _limitations(r: _R, values: list[str], title_key: str = "limits.count") -> str:
    if not values:
        return f'<p class="limits-none">{r.t("limits.none")}</p>'
    localized = [v for v in values if narrate(v)]
    raw = [v for v in values if not narrate(v)]
    body = (f'<ul class="list">{"".join("<li>" + r.p(narrate(v)) + "</li>" for v in localized)}</ul>' if localized else "")
    if raw:
        body += (f'<div class="original"><p class="original-label">{r.t("original.label")}</p>'
                 f'<ul class="list">{"".join("<li lang=" + chr(34) + "en" + chr(34) + ">" + _e(v) + "</li>" for v in raw)}</ul></div>')
    return f'<details class="limits"><summary>{r.icon("info")}{r.t(title_key, n=len(values))}</summary>{body}</details>'


def _section_head(r: _R, sid: str, title_key: str, lead_key: str | None = None, level: int = 3, count: str = "") -> str:
    lead = r.t(lead_key, tag="p", cls="lead") if lead_key else ""
    return f'<div class="sub-head"><h{level} id="h-{sid}">{r.t(title_key)}{count}</h{level}>{lead}</div>'


def _panel(r: _R, sid: str, title_key: str, summary: str, body: str, lead_key: str | None = None, open_: bool = False) -> str:
    """A collapsible evidence panel (Layer 2) with a one-line summary visible while closed."""
    lead = r.t(lead_key, tag="p", cls="lead") if lead_key else ""
    return (f'<details class="panel-d" id="{sid}"{" open" if open_ else ""}><summary><span class="pd-title">'
            f'<h3 id="h-{sid}">{r.t(title_key)}</h3><span class="pd-sum">{summary}</span></span>{r.icon("chev", "ic chev")}</summary>'
            f'<div class="pd-body">{lead}{body}</div></details>')


def _verdict(r: _R) -> tuple[str, str, Pair, Pair]:
    """(tone, icon, headline, reason) for the report status, explained from the model."""
    report = r.report
    status = report["status"]
    if report["workflow"] == "improve":
        checks = _checks(report)
        blockers = [c for c in checks if c["status"] in _BAD]
        if status == "APPLIED":
            n = len((report.get("change_set") or {}).get("applied") or [])
            return "accent", "check", pair_of("verdict.applied"), pair_of("verdict.applied.reason", n=n)
        if status == "READY_FOR_REVIEW":
            open_ = [c for c in checks if c["status"] in _OPEN]
            reason = pair_of("verdict.ready.reason.open", n=len(open_)) if open_ else pair_of("verdict.ready.reason")
            return "accent", "check", pair_of("verdict.ready"), reason
        if blockers:
            items = [pair_of("verdict.blocker", check=_lower(_label("q.", c["check"])), status=_lower(_label("st.", c["status"]))) for c in blockers]
            return "warn", "alert", pair_of("verdict.not_ready"), pair_of("verdict.blockers", n=len(blockers), list=_join(items))
        return "warn", "alert", pair_of("verdict.not_ready"), pair_of("verdict.not_ready.generic")
    counts = _severity_counts(report["findings"])
    if status == "UNKNOWN":
        return "unknown", "question", pair_of("verdict.unknown"), pair_of("verdict.unknown.reason")
    if status == "NO_FINDINGS_IN_SCOPE":
        return "neutral", "dot", pair_of("verdict.clean"), pair_of("verdict.clean.reason", n=len(report["claim_boundary"].get("not_evidenced") or []))
    parts = []
    if counts["high"]:
        parts.append(pair_of("reason.high", n=counts["high"]))
    if counts["medium"]:
        parts.append(pair_of("reason.medium_tail" if counts["high"] else "reason.medium", n=counts["medium"]))
    if parts:
        reason = _and(parts)
        if counts["info"]:
            reason = _join([reason, pair_of("reason.info_tail", n=counts["info"])], (" ", " "))
        return "warn", "alert", pair_of("verdict.review"), reason
    return "neutral", "info", pair_of("verdict.info"), pair_of("verdict.info.reason", n=counts["info"])


def _evidence_mode(r: _R) -> tuple[str, Pair]:
    report = r.report
    if report["workflow"] == "improve":
        return "solid", pair_of("evmode.improve")
    runs = (report["states"].get("current") or {}).get("runs", [])
    executed = [run for run in runs if run["mode"] != "report"]
    if executed:
        return "solid", pair_of("evmode.executed", n=sum(run["invocations"] for run in executed))
    if runs:
        return "half", pair_of("evmode.ingested")
    return "hollow", pair_of("evmode.static")


def _delta_counts(r: _R, delta: dict | None, target: str = "#delta") -> str:
    if not delta:
        return ""
    order = ("improved", "regressed", "changed", "unchanged", "unknown")
    items = "".join(
        f'<li class="dc dc-{b}{" zero" if not delta.get(b) else ""}"><a href="{target}-{b}"><span class="dc-n">{len(delta.get(b) or [])}</span>'
        f'{r.t("dc." + b, n=len(delta.get(b) or []))}</a></li>'
        for b in order
    )
    return f'<ul class="dcounts">{items}</ul>'


_COUNT_KEYS = ("count", "smoke_like", "total")


def _affected(evidence: dict) -> tuple[Pair | None, list[str]]:
    listed: list[str] = []
    for value in evidence.values():
        if isinstance(value, list) and all(isinstance(v, (str, int, float)) for v in value):
            listed = [str(v) for v in value]
            break
    if isinstance(evidence.get("smoke_like"), int) and isinstance(evidence.get("total"), int):
        return pair_of("finding.of", a=evidence["smoke_like"], b=evidence["total"]), listed
    if isinstance(evidence.get("count"), int):
        return pair_of("finding.count", n=evidence["count"]), listed
    if listed:
        return pair_of("finding.count", n=len(listed)), listed
    return None, listed


def _metric_name(r: _R, name: str) -> str:
    entry = METRICS.get(name)
    return r.p(entry, cls="m-name") if entry else f'<span class="m-name">{_e(_humanize(name))}</span>'


def _value(r: _R, state: dict | None, name: str) -> str:
    metric = ((state or {}).get("metrics") or {}).get(name)
    if not metric or metric.get("value") is None:
        return "—"
    return r.p(_num(metric["value"], metric.get("unit"), 1 if metric.get("unit") == "%" else 2))


def _delta_state(report: dict, name: str) -> str | None:
    for bucket, items in (report.get("evidence_delta") or {}).items():
        if any(d["name"] == name for d in items):
            return bucket
    return None


def _metrics_tables(r: _R) -> str:
    report = r.report
    states = _states(report)
    order = {name: i for i, name in enumerate(METRICS)}
    names = sorted({name for _, s in states for name in s["metrics"]}, key=lambda n: (order.get(n, len(order)), n))
    if not names:
        return r.t("metrics.none", tag="p", cls="empty")
    delta = {d["name"]: bucket for bucket, items in (report.get("evidence_delta") or {}).items() for d in items}
    notes = {d["name"]: d.get("note") for items in (report.get("evidence_delta") or {}).values() for d in items}
    show_delta = bool(report.get("evidence_delta"))
    groups: dict[str, list[str]] = {}
    for name in names:
        group = METRIC_GROUPS.get(name) or ("coverage" if "coverage" in name or name.endswith(("_covered", "_total")) else "other")
        groups.setdefault(group, []).append(name)
    head = "".join(f'<th scope="col" class="num-col">{r.state(k)}</th>' for k, _ in states)
    tables = []
    for group in ("execution", "coverage", "static", "negative", "fault", "artifact", "other"):
        if group not in groups:
            continue
        rows = []
        for name in groups[group]:
            first = next(s["metrics"][name] for _, s in states if name in s["metrics"])
            cells = "".join(f'<td class="num-col" {r.label_attr("state." + k)}>{_value(r, s, name)}</td>' for k, s in states)
            direction = first.get("direction") or ""
            dir_html = r.t("dir." + direction) if "dir." + direction in UI else _e(direction)
            delta_cell = ""
            if show_delta:
                bucket = delta.get(name, "")
                note = r.narr(notes[name], cls="th-note") if notes.get(name) else ""
                delta_cell = f'<td {r.label_attr("metrics.delta")}>{r.pill(bucket) if bucket else ""}{note}</td>'
            rows.append(f'<tr><th scope="row">{_metric_name(r, name)}<code class="m-id">{_e(name)}</code></th>{cells}'
                        f'<td {r.label_attr("metrics.direction")}><span class="dir">{dir_html}</span> {r.tier(first.get("evidence_tier"))}</td>{delta_cell}</tr>')
        delta_head = f'<th scope="col">{r.t("metrics.delta")}</th>' if show_delta else ""
        tables.append(f'<div class="table-wrap"><table class="metrics responsive"><caption>{r.t("metrics.group." + group)}</caption>'
                      f'<thead><tr><th scope="col">{r.t("metrics.metric")}</th>{head}<th scope="col">{r.t("metrics.direction")}</th>{delta_head}</tr></thead>'
                      f'<tbody>{"".join(rows)}</tbody></table></div>')
    sources = [
        f'<li>{r.state(k)}: <code>{_e(c.get("tool") or "unknown tool")}</code>'
        + (f' <span class="raw-text" lang="en">({_e(c["scope"])})</span>' if c.get("scope") else "")
        + (f' <span class="raw-text" lang="en">— {_e(c["error"])}</span>' if c.get("error") else "")
        + "".join(f" · {r.narr(lim)}" for lim in c.get("limitations") or ()) + "</li>"
        for k, s in states for c in s.get("coverage") or []
    ]
    coverage = f'<div class="sources"><p class="tech-label">{r.t("metrics.coverage_sources")}</p><ul class="list">{"".join(sources)}</ul></div>' if sources else ""
    return "".join(tables) + coverage


def _metrics_panel(r: _R) -> str:
    states = _states(r.report)
    total = len({name for _, s in states for name in s["metrics"]})
    return _panel(r, "metrics", "metrics.title", r.t("metrics.summary", n=total), _metrics_tables(r), "metrics.lead")


def _surface(r: _R) -> str:
    checks = r.report.get("verification_surface") or []
    if not checks:
        return _panel(r, "surface-section", "surface.title", r.t("surface.summary.none"), r.t("surface.none", tag="p", cls="empty"))
    origins: dict[str, list[dict]] = {}
    for c in checks:
        origins.setdefault(c["origin"], []).append(c)
    order = ["LOCAL", "HOOK", "CI", "BUILD", "PACKAGE", "DEPLOY", "DECLARED", "UNKNOWN"]
    groups = []
    for origin in sorted(origins, key=lambda o: order.index(o) if o in order else len(order)):
        rows = []
        for c in origins[origin]:
            meta = c.get("metadata") or {}
            name = c.get("tool") or (c.get("command") or c["check_id"]).split("\n")[0][:60]
            where = " · ".join(str(v) for v in (meta.get("job"), meta.get("step"), meta.get("script")) if v)
            kind = r.t("kind." + c["kind"]) if "kind." + c["kind"] in UI else _e(_humanize(c["kind"]))
            gate = r.t("gate." + c["gate"]) if "gate." + c["gate"] in UI else _e(c["gate"])
            detail = []
            if c.get("command"):
                detail.append(f'<div class="cmd"><div class="cmd-head">{r.t("surface.command")}{_copy(r)}</div><pre class="code"><code>{_e(c["command"])}</code></pre></div>')
            detail.append(f'<dl class="kv"><dt>{r.t("surface.check")}</dt><dd><code>{_e(c["check_id"])}</code></dd>'
                          + (f'<dt>{r.t("surface.source")}</dt><dd><code>{_e(c["source"])}</code></dd>' if c.get("source") else "")
                          + f'<dt>{r.t("surface.gate")}</dt><dd><code>{_e(c["gate"])}</code></dd><dt>{r.t("surface.tier")}</dt><dd>{r.tier(c.get("evidence_tier"))}</dd></dl>')
            if c.get("limitations"):
                detail.append(f'<p class="tech-label">{r.t("surface.limitations")}</p>{r.items(list(c["limitations"]))}')
            rows.append(
                f'<li class="check" data-kind="{_e(c["kind"])}"><details><summary><span class="kind kind-{_e(c["kind"].lower())}">{kind}</span>'
                f'<span class="check-title"><span class="check-name">{_e(name)}</span>' + (f'<span class="check-where">{_e(where)}</span>' if where else "")
                + f'</span><span class="gate gate-{_e(c["gate"].lower())}">{gate}</span>{r.icon("chev", "ic chev")}</summary>'
                f'<div class="check-body">{"".join(detail)}</div></details></li>'
            )
        label = r.t("origin." + origin) if "origin." + origin in UI else _e(origin)
        groups.append(f'<section class="origin" aria-label="{_e(origin)}"><h4 class="origin-head">{label}<span class="count">{r.t("surface.checks", n=len(origins[origin]))}</span></h4>'
                      f'<ul class="check-list">{"".join(rows)}</ul></section>')
    kinds = sorted({c["kind"] for c in checks})
    options = "".join(f'<option value="{_e(k)}"{r.attr_text("kind." + k) if "kind." + k in UI else ""}>{_e(r.s("kind." + k) if "kind." + k in UI else k)}</option>' for k in kinds)
    body = (f'<div class="filters"><label for="kind">{r.t("surface.filter.kind")}</label><select id="kind" class="select">'
            f'<option value=""{r.attr_text("surface.filter.all")}>{_e(r.s("surface.filter.all"))}</option>{options}</select></div>'
            f'<div class="origins">{"".join(groups)}</div>')
    return _panel(r, "surface-section", "surface.title", r.t("surface.summary", n=len(checks), m=len(origins)), body, "surface.lead")


def _copy(r: _R) -> str:
    return f'<button type="button" class="copy" {r.attr("aria-label", "copy.label")}>{r.icon("copy")}{r.t("copy")}</button>'


def _runs(r: _R) -> str:
    rows = []
    total = 0
    for key, state in _states(r.report):
        for run in state.get("runs", []):
            total += 1
            how = r.t("runs.ingested") if run["mode"] == "report" else r.t("runs.executed")
            command = " ".join(run["command"]) if isinstance(run["command"], list) else str(run["command"] or "")
            matrix = "".join(f'<li><code>{_e(n)}</code> <code class="raw">{_e(v)}</code></li>' for n, v in (run.get("matrix") or {}).items())
            rows.append(
                f'<li class="run"><div class="run-head"><span class="run-title"><code>{_e(run["adapter"])}</code> {r.state(key)}</span>{r.pill(run["status"])}</div>'
                f'<p class="run-how">{how} · {r.t("runs.invocations", n=run["invocations"])}'
                + (f' · {r.t("runs.exit")} <code>{_e(run["exit_code"])}</code>' if run.get("exit_code") is not None else "") + "</p>"
                + (f'<p class="tech-label">{r.t("runs.matrix")}</p><ul class="matrix">{matrix}</ul>' if matrix else "")
                + (f'<div class="cmd"><div class="cmd-head">{r.t("surface.command")}{_copy(r)}</div><pre class="code"><code>{_e(command)}</code></pre></div>' if command else "")
                + (f'<p class="tech-label">{r.t("surface.limitations")}</p>{r.items(run["limitations"])}' if run.get("limitations") else "")
                + "</li>"
            )
    body = f'<ul class="runs">{"".join(rows)}</ul>' if rows else r.t("runs.none", tag="p", cls="empty")
    return _panel(r, "runs", "runs.title", r.t("runs.summary", n=total) if total else r.t("runs.summary.none"), body)


def _negative(r: _R) -> str:
    states = [(k, s) for k, s in _states(r.report) if s.get("negative_paths")]
    if not states:
        return ""
    tests = sorted({t for _, s in states for t in s["negative_paths"]})
    head = "".join(f'<th scope="col">{r.state(k)}</th>' for k, _ in states)
    any_html = r.t("neg.any", cls="muted")
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(t)}</code></th>'
        + "".join(f'<td {r.label_attr("state." + k)}>'
                  + ((" ".join(f'<span class="tag">{_e(d)}</span>' for d in s["negative_paths"][t]) or any_html) if t in s["negative_paths"] else "—")
                  + "</td>" for k, s in states)
        + "</tr>" for t in tests
    )
    table = (f'<div class="table-wrap"><table class="responsive"><caption>{r.t("neg.caption")}</caption><thead><tr><th scope="col">{r.t("neg.test")}</th>{head}</tr></thead>'
             f"<tbody>{rows}</tbody></table></div>")
    return _panel(r, "negative-paths", "neg.title", r.t("neg.summary", n=len(tests)), table, "neg.lead")


def _mutation(r: _R) -> str:
    rows = []
    for key, state in _states(r.report):
        for run in state.get("mutation", []):
            counts = ", ".join(f"{k.lower()}: {v}" for k, v in sorted(run["counts"].items())) or "—"
            status = (f'{r.t("mut.unreadable")}: <span class="raw-text" lang="en">{_e(run["error"])}</span>' if run["error"]
                      else r.t("mut.mismatch") if run["matches_state"] is False else f"<code>{_e(counts)}</code>")
            survivors = (r.items(run["survivors"], kind="code") if run["survivors"]
                         else r.t("mut.none_listed" if run["per_mutant"] else "mut.no_identity", tag="p", cls="muted"))
            rows.append(f'<tr><th scope="row">{r.state(key)}</th><td {r.label_attr("mut.tool")}><code>{_e(run["tool"] or "unknown")}</code></td>'
                        f'<td {r.label_attr("mut.result")}>{status}</td><td {r.label_attr("mut.survivors")}>{survivors}</td>'
                        f'<td {r.label_attr("surface.limitations")}>{r.items(run["limitations"])}</td></tr>')
    if not rows:
        return ""
    table = (f'<div class="table-wrap"><table class="responsive"><caption>{r.t("mut.caption")}</caption><thead><tr><th scope="col">{r.t("prov.state.label")}</th>'
             f'<th scope="col">{r.t("mut.tool")}</th><th scope="col">{r.t("mut.result")}</th><th scope="col">{r.t("mut.survivors")}</th>'
             f'<th scope="col">{r.t("surface.limitations")}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')
    return _panel(r, "mutation-evidence", "mut.title", r.t("mut.summary", n=len(rows)), table, "mut.lead")


def _artifacts(r: _R) -> str:
    cards = []
    for key, state in _states(r.report):
        for a in state.get("artifacts", []):
            checks = "".join(f'<li>{r.pill(c["status"])}<code>{_e(c["name"])}</code> <span class="raw-text" lang="en">{_e(c["detail"])}</span></li>' for c in a["checks"])
            built = f'<code>{_e(a["artifact"])}</code>' if a["artifact"] else r.t("art.not_built")
            omitted = (f'<p class="muted">{r.t("art.missing")}: <code>{_e(", ".join(a["omitted_files"][:10]))}</code></p>' if a["omitted_files"] else "")
            fidelity = "".join(f'<li>{r.pill(v)}<code>{_e(k.lower().replace("_", " "))} {_e(v)}</code></li>' for k, v in (a.get("fidelity") or {}).items())
            fidelity = (f'<p class="tech-label">{r.t("art.proves")}</p><ul class="checks-list">{fidelity}</ul>' if fidelity else "")
            cards.append(
                f'<li class="artifact"><div class="run-head"><span class="run-title"><code>{_e(a["kind"])}</code> {built} {r.state(key)}</span>{r.pill(a["status"])}</div>'
                f'<p class="muted">sha256 <code>{_e((a["sha256"] or "—")[:16])}</code></p><ul class="checks-list">{checks}</ul>{fidelity}'
                + (f'<p class="tech-label">{r.t("surface.limitations")}</p>{r.items(a["limitations"])}' if a["limitations"] else "") + f"{omitted}</li>"
            )
    if not cards:
        return ""
    return _panel(r, "artifact-evidence", "art.title", r.t("art.summary", n=len(cards)), f'<ul class="runs">{"".join(cards)}</ul>', "art.lead")


def _delivery(r: _R) -> str:
    report = r.report
    delivery = report.get("delivery")
    review = report.get("review_candidates") or []
    if not delivery and not review:
        return ""
    matrix = (delivery or {}).get("matrix") or {}
    declared = [f'{dim}: {", ".join(info["values"])} ({info["source"]})' for dim, info in sorted((matrix.get("declared") or {}).items())]
    ci = [f'{dim}: {", ".join(values)}' for dim, values in sorted((matrix.get("ci") or {}).items())]
    lineage = [f'{item["artifact"]} sha256 {(item["sha256"] or "?")[:12]} · tested {item["tested"]}' for item in (delivery or {}).get("artifact_lineage") or []]
    candidates = [f'{c["kind"]}: {c["subject"]} ({c["tests"]})' for c in review]
    body = (
        '<div class="cols">'
        f'<div><h4>{r.t("delivery.declared")}</h4>{r.items(declared, "delivery.declared.none", kind="code")}</div>'
        f'<div><h4>{r.t("delivery.ci")}</h4>{r.items(ci, "delivery.ci.none", kind="code")}</div>'
        f'<div><h4>{r.t("delivery.lineage")}</h4>{r.items(lineage, "delivery.lineage.none", kind="code")}</div>'
        f'<div><h4>{r.t("delivery.review")}</h4>{r.t("delivery.review.note", tag="p", cls="muted")}{r.items(candidates, kind="code")}</div>'
        "</div>"
    )
    return _panel(r, "delivery", "delivery.title", r.t("delivery.summary"), body)


def _selection(r: _R) -> str:
    selection = r.report.get("test_selection")
    if not selection:
        return ""
    counts = selection["counts"]
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(test)}</code></th><td {r.label_attr("sel.reason")} class="raw-text" lang="en">{_e(reasons[0]["reason"])}</td>'
        f'<td {r.label_attr("sel.tier")}><code>{_e(reasons[0]["tier"] or reasons[0]["trigger"] or "")}</code></td>'
        f'<td {r.label_attr("sel.path")}><code>{_e(" → ".join(reasons[0]["path"]))}</code></td></tr>'
        for test, reasons in sorted(selection["selected"].items())[:200]
    )
    widening = [f'{w["trigger"]}{" (full suite)" if w["full"] else ""}: {w["path"] or ""} {w["reason"]}'.strip() for w in selection["widening"]]
    unknowns = [f'{u["node"]}: {u["reason"]}' for u in selection["unknown_dependencies"]]
    affected = sorted((selection.get("affected_components") or {}).items())
    components = (f'<h4>{r.t("sel.components")}</h4>' + r.items([f"{n}: {why}" for n, why in affected], kind="code")) if affected else ""
    body = (
        f'<p class="meta-row"><span>{r.t("sel.base")} <code>{_e(selection["base"] or "none")}</code></span>'
        f'<span>{r.t("sel.changed", n=len(selection["changes"]))}</span><span>{r.t("sel.confidence")} {r.pill(selection["confidence"])}</span></p>'
        f'{components}<div class="cols"><div><h4>{r.t("sel.widening")}</h4>{r.items(widening, "sel.widening.none", kind="code")}</div>'
        f'<div><h4>{r.t("sel.unknowns")}</h4>{r.items(unknowns, "sel.unknowns.none", kind="code")}</div></div>'
        f'<div class="table-wrap"><table class="responsive"><caption>{r.t("sel.caption")}</caption><thead><tr><th scope="col">{r.t("neg.test")}</th>'
        f'<th scope="col">{r.t("sel.reason")}</th><th scope="col">{r.t("sel.tier")}</th><th scope="col">{r.t("sel.path")}</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>" + (r.items(selection["limitations"]) if selection["limitations"] else "")
    )
    return _panel(r, "selection", "sel.title", r.t("sel.selected", a=counts["selected"], b=counts["mapped"]), body)


def _history(r: _R) -> str:
    history = r.report.get("history")
    if not history:
        return ""
    if not history.get("enabled"):
        return _panel(r, "history", "hist.title", r.t("hist.unused"), r.items(history.get("limitations") or [], "hist.unused"))
    rows = "".join(
        f'<tr><th scope="row"><code>{_e(e["invocation_id"])}</code></th><td {r.label_attr("hist.stability")}>{r.pill(e["stability"])}</td>'
        f'<td {r.label_attr("finding.evidence")} class="raw-text" lang="en">{_e(e["note"])}</td>'
        f'<td {r.label_attr("hist.signature")}><code>{_e(e["failure_signature"] or "")}</code></td></tr>'
        for e in history["invocations"]
    )
    table = (f'<div class="table-wrap"><table class="responsive"><caption>{r.t("hist.caption")}</caption><thead><tr><th scope="col">{r.t("hist.invocation")}</th>'
             f'<th scope="col">{r.t("hist.stability")}</th><th scope="col">{r.t("finding.evidence")}</th><th scope="col">{r.t("hist.signature")}</th>'
             f'</tr></thead><tbody>{rows}</tbody></table></div>') if rows else r.t("hist.none", tag="p", cls="empty")
    timings = [f'{t["invocation_id"]}: p50 {t["p50"]}s' + (f', p95 {t["p95"]}s' if t["p95"] is not None else "") + f' ({t["samples"]})' for t in history["durations"]]
    body = (f'{table}<div class="cols"><div><h4>{r.t("hist.durations")}</h4>{r.items(timings, "hist.durations.none", kind="code")}</div></div>'
            + (r.items(history["limitations"]) if history["limitations"] else ""))
    return _panel(r, "history", "hist.title", r.t("hist.states", n=history["states_recorded"]), body)


def _artifact_summary(report: dict) -> Pair | None:
    artifacts = (report["states"].get("candidate") or {}).get("artifacts") or []
    parts = [pair_of("conf.artifact" if a["status"] == "PASS" else "short.artifact_kind", kind=a["kind"]) for a in artifacts]
    return _join(parts) if parts else None


def _changes(r: _R) -> str:
    cs = r.report.get("change_set")
    if not cs:
        return ""
    applied = set(cs.get("applied") or [])
    items = "".join(
        f'<li class="change"><details><summary>{r.pill(c["kind"])}<code class="path">{_e(c["path"])}</code>'
        f'{r.pill("APPLIED") if c["change_id"] in applied else r.t("changes.not_applied", cls="pill tone-not_run")}{r.icon("chev", "ic chev")}</summary>'
        f'<div class="change-body">{r.narr(c["reason"], tag="p")}'
        f'<p class="muted">{r.t("changes.fingerprints")} <code>{_e((c["original_fingerprint"] or "none")[:12])}</code> → <code>{_e((c["candidate_fingerprint"] or "none")[:12])}</code></p>'
        f'<pre class="code diff">{_e(c["diff"])}</pre></div></details></li>'
        for c in cs["changes"]
    )
    return (f'<section id="changes" class="sub" aria-labelledby="h-changes">{_section_head(r, "changes", "changes.title", "changes.lead")}'
            + (f'<ul class="changes">{items}</ul>' if items else r.t("changes.none", tag="p", cls="empty")) + "</section>")


_DELTA_GLYPH = {"improved": "+", "regressed": "−", "changed": "~", "unknown": "?", "unchanged": "="}


def _delta_rows(r: _R, items: list[dict], bucket: str, before: str, after: str) -> str:
    rows = []
    for d in items:
        unit = d.get("unit")
        digits = 1 if unit == "%" else 2
        values = f'{r.p(_num(d.get(before), unit, digits))}<span class="arrow" aria-hidden="true">→</span>{r.p(_num(d.get(after), unit, digits))}'
        note = r.narr(d["note"], tag="p", cls="d-note") if d.get("note") else ""
        rows.append(f'<li class="drow d-{bucket}"><span class="d-glyph" aria-hidden="true">{_DELTA_GLYPH[bucket]}</span>'
                    f'<span class="d-name">{_metric_name(r, d["name"])}</span><span class="d-vals">{values}</span>{note}</li>')
    return f'<ul class="drows">{"".join(rows)}</ul>'


def _delta_block(r: _R, delta: dict, prefix: str, after: str) -> str:
    out = [_delta_counts(r, delta, "#" + prefix)]
    for bucket in ("regressed", "improved", "changed", "unknown"):
        items = delta.get(bucket) or []
        if not items:
            continue
        out.append(f'<section class="dgroup dg-{bucket}" id="{prefix}-{bucket}" aria-labelledby="h-{prefix}-{bucket}">'
                   f'<h3 id="h-{prefix}-{bucket}">{r.t("dg." + bucket)}<span class="count">{len(items)}</span></h3>'
                   f'{r.t("dg." + bucket + ".lead", tag="p", cls="dg-lead")}{_delta_rows(r, items, bucket, "baseline", after)}</section>')
    unchanged = delta.get("unchanged") or []
    if unchanged:
        out.append(f'<details class="dgroup dg-unchanged" id="{prefix}-unchanged"><summary>{r.t("dg.unchanged", n=len(unchanged))}{r.icon("chev", "ic chev")}</summary>'
                   f'{_delta_rows(r, unchanged, "unchanged", "baseline", after)}</details>')
    return "".join(out)


def _delta_area(r: _R) -> str:
    report = r.report
    delta = report.get("evidence_delta")
    head = f'<div class="area-head"><h2 id="h-delta">{r.t("delta.title")}</h2>{r.t("delta.lead", tag="p", cls="lead")}</div>'
    body = _delta_block(r, delta, "delta", "candidate") if delta else r.t("delta.none", tag="p", cls="empty")
    applied = report.get("applied_delta")
    if applied:
        body += (f'<section class="sub" id="applied-delta" aria-labelledby="h-applied-delta">{_section_head(r, "applied-delta", "delta.applied", "delta.applied.lead")}'
                 f'{_delta_block(r, applied, "adelta", "candidate")}</section>')
    return f'<section id="delta" class="area" data-layer="decision" aria-labelledby="h-delta">{head}{body}</section>'


def _unknowns(r: _R) -> str:
    report = r.report
    unknowns = report.get("remaining_unknowns") or []
    shown = set(report["claim_boundary"].get("not_evidenced") or [])
    extra = [u for u in unknowns if u not in shown]
    same = len(unknowns) - len(extra)
    note = r.t("unknowns.dedup", tag="p", cls="muted", n=same) if same else ""
    body = (r.items(extra, limit=50) if extra else "") + note
    return (f'<section id="unknowns" class="sub" aria-labelledby="h-unknowns">{_section_head(r, "unknowns", "unknowns.title")}'
            f'{body or r.t("unknowns.none", tag="p", cls="empty")}</section>')


def _budget(r: _R) -> str:
    budget = r.report.get("execution_budget")
    if not budget:
        return ""
    rows = "".join(f'<li class="budget-row">{r.pill(d["decision"])}<code class="budget-stage">{_e(d["stage"])}</code>'
                   f'<span class="budget-reason raw-text" lang="en">{_e(d["reason"])}</span></li>' for d in budget["decisions"])
    body = (f'<p class="meta-row">{r.t("budget.level", l=budget["level"], d=budget["depth"], m=budget["max_depth"])}</p><ul class="budget">{rows}</ul>')
    return _panel(r, "budget", "budget.title", r.t("budget.summary", n=len(budget["decisions"])), body, "budget.lead")


def _nav(r: _R) -> str:
    report = r.report
    if report["workflow"] == "improve":
        areas = [("overview", "nav.overview", [("green", "green.title")], ""),
                 ("candidate", "nav.candidate", [("changes", "changes.title")], ""),
                 ("delta", "nav.delta", [], ""),
                 ("evidence", "nav.evidence", [("domains", "dom.title"), ("metrics", "metrics.title"), ("surface-section", "surface.title")], ""),
                 ("details", "nav.details", [("provenance", "prov.title"), ("claim", "claim.title"), ("raw", "raw.title")], "")]
    else:
        recs = len(report.get("recommendations") or [])
        areas = [("overview", "nav.overview", [("green", "green.title")], ""),
                 ("findings", "nav.findings", [], str(len(report["findings"])) if report["findings"] else ""),
                 ("improvements", "nav.improvements", [], str(recs) if recs else ""),
                 ("evidence", "nav.evidence", [("domains", "dom.title"), ("metrics", "metrics.title"), ("surface-section", "surface.title"), ("runs", "runs.title")], ""),
                 ("details", "nav.details", [("provenance", "prov.title"), ("claim", "claim.title"), ("raw", "raw.title")], "")]
    items = "".join(
        f'<li data-area="{aid}"><a class="nav-area" href="#{aid}">{r.t(key)}' + (f'<span class="badge">{badge}</span>' if badge else "") + "</a>"
        + ('<ul class="nav-sub">' + "".join(f'<li><a href="#{sid}">{r.t(skey)}</a></li>' for sid, skey in subs) + "</ul>" if subs else "")
        + "</li>"
        for aid, key, subs, badge in areas
    )
    return f'<nav class="sidenav" {r.attr("aria-label", "nav.label")}><ul>{items}</ul></nav>'


def _sprite() -> str:
    symbols = "".join(f'<symbol id="i-{name}" viewBox="0 0 16 16">{body}</symbol>' for name, body in _ICONS.items())
    return f'<svg class="sprite" aria-hidden="true" focusable="false">{symbols}</svg>'


_LOGO = ('<svg class="logo" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="1" y="1" width="22" height="22" rx="6" fill="var(--ink)"/>'
         '<path d="M7 16.5L12 6l5 10.5M9.2 12.4h5.6" fill="none" stroke="var(--bg)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


_ICONS = {
    "check": '<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    "checkc": '<circle cx="8" cy="8" r="7" fill="currentColor"/><path d="M4.8 8.3l2.2 2.2 4.2-4.8" fill="none" stroke="var(--on-tone)" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    "cross": '<path d="M4.5 4.5l7 7M11.5 4.5l-7 7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "crossc": '<circle cx="8" cy="8" r="7" fill="currentColor"/><path d="M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8" fill="none" stroke="var(--on-tone)" stroke-width="1.7" stroke-linecap="round"/>',
    "half": '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 1.8a6.2 6.2 0 010 12.4z" fill="currentColor"/>',
    "ring": '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.6"/>',
    "alert": '<path d="M8 2.5l6 11H2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M8 6.5v3.2M8 11.6v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "question": '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.5" stroke-dasharray="2.2 1.8"/><path d="M6.4 6.3a1.7 1.7 0 113 1.1c-.6.4-1.4.8-1.4 1.6M8 11.3v.1" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
    "block": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M4 12L12 4" stroke="currentColor" stroke-width="1.5"/>',
    "dash": '<path d="M4 8h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "dot": '<circle cx="8" cy="8" r="3" fill="currentColor"/>',
    "diamond": '<path d="M8 1.8L14.2 8 8 14.2 1.8 8z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>',
    "info": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 7.3v4M8 4.8v.1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "arrow": '<path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    "chev": '<path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "copy": '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M3.5 10.5v-7a1 1 0 011-1h7" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "moon": '<path d="M13 9.5A5.5 5.5 0 016.5 3a5.5 5.5 0 106.5 6.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>',
    "globe": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2 8h12M8 2c1.8 1.7 2.6 3.7 2.6 6S9.8 12.3 8 14C6.2 12.3 5.4 10.3 5.4 8S6.2 3.7 8 2z" fill="none" stroke="currentColor" stroke-width="1.2"/>',
}

_JS_STRINGS = {
    "en": {"copied": "Copied", "show_full": "Show complete", "collapse": "Collapse", "count": "{a} of {b} findings", "local": "local time"},
    "pt-BR": {"copied": "Copiado", "show_full": "Mostrar completo", "collapse": "Recolher", "count": "{a} de {b} achados", "local": "horário local"},
}


def render_html(report: dict, lang: str = "en") -> str:
    from . import __version__ as rendered_by
    from .report import REPORT_VERSION  # the model module owns the report format version

    lang = lang if lang in ("en", "pt-BR") else "en"
    r = _R(report, lang)
    project = report["project"]
    improve = report["workflow"] == "improve"
    areas = ([_candidate_area(r), _delta_area(r)] if improve else [_findings_area(r), _improvements_area(r)])
    main = _overview(r) + "".join(areas) + _evidence_area(r) + _details_area(r)
    title = r.t("page.title", tag="title", workflow=pair_of("wf." + report["workflow"]), name=project.get("name") or "project")
    selected = (" selected", "") if lang == "pt-BR" else ("", " selected")
    header = (
        f'<header class="topbar"><div class="topbar-inner"><a class="brand" href="#overview">{_LOGO}'
        f'<span class="brand-name">Assertiva</span><span class="brand-product">{r.t("brand.product")}</span></a>'
        f'<span class="topbar-context" aria-hidden="true"><code>{_e(project.get("name") or "")}</code>'
        f'<span class="tc-status">{r.p(_verdict(r)[2])}</span></span>'
        f'<div class="controls"><label class="lang">{r.icon("globe")}<span class="sr-only">{r.t("lang.label")}</span>'
        f'<select id="lang" class="select" {r.attr("aria-label", "lang.label")}><option value="en" lang="en"{selected[1]}>English</option>'
        f'<option value="pt-BR" lang="pt-BR"{selected[0]}>Português (Brasil)</option></select></label>'
        f'<button id="theme" type="button" class="toggle" aria-pressed="false" {r.attr("aria-label", "theme.label")}>'
        f'{r.icon("moon")}<span class="toggle-text">{r.t("theme.toggle")}</span></button></div></div></header>'
    )
    nav = _nav(r)
    skip = r.t("skip", tag="a", cls="skip", attrs=' href="#main"')
    footer = f'<footer class="footer">{r.t("footer", tag="p", v=REPORT_VERSION, a=rendered_by)}</footer>'
    data = json.dumps({"pt-BR": dict(sorted(r.used.items())), "js": _JS_STRINGS}, ensure_ascii=False).replace("</", "<\\/")
    return (
        f'<!doctype html>\n<html lang="{lang}" data-rendered="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">'
        f'<meta name="generator" content="Assertiva {_e(rendered_by)}">'
        f"{title}<style>{_CSS}</style></head>\n<body>\n{skip}\n{_sprite()}\n{header}\n"
        f'<div class="shell">{nav}<main id="main" tabindex="-1">{main}</main></div>\n{footer}\n'
        '<div id="live" class="sr-only" aria-live="polite"></div>\n'
        f'<script type="application/json" id="i18n">{data}</script>\n<script>{_JS}</script>\n</body></html>\n'
    )


_CSS = """
:root{color-scheme:light;
--bg:#f4f4f2;--surface:#ffffff;--raised:#ffffff;--sunk:#eeeeeb;--rule:#e3e3df;--rule-strong:#cdcdc7;
--ink:#121417;--ink-2:#363940;--muted:#5d6068;--faint:#878a91;
--accent:#2b46c8;--accent-soft:#e8ebfb;--on-tone:#ffffff;
--pass:#17713b;--fail:#b8292b;--warn:#8d5600;--unknown:#646872;--info:#245e9e;
--pass-soft:#e5f1e9;--fail-soft:#fbeceb;--warn-soft:#f8efdf;--info-soft:#e7eef8;
--shadow:0 1px 2px rgba(18,20,23,.05);--lift:0 12px 32px -20px rgba(18,20,23,.4);
--r-sm:6px;--r:10px;--r-lg:14px;
--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI Variable Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,"SF Mono","Cascadia Mono",Menlo,Consolas,"Liberation Mono",monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#0d0e10;--surface:#15161a;--raised:#1a1b20;--sunk:#1d1e23;--rule:#26272d;--rule-strong:#393a42;
--ink:#eeeff1;--ink-2:#c8c9cf;--muted:#a1a3ab;--faint:#787b83;
--accent:#9eacff;--accent-soft:#1d2140;--on-tone:#0d0e10;
--pass:#5fcb86;--fail:#ff8b86;--warn:#e8b65c;--unknown:#a6a9b1;--info:#82b7ff;
--pass-soft:#132619;--fail-soft:#2c1615;--warn-soft:#2a2111;--info-soft:#15202d;
--shadow:0 1px 2px rgba(0,0,0,.4);--lift:0 16px 36px -20px rgba(0,0,0,.85)}}
:root[data-theme="dark"]{color-scheme:dark;
--bg:#0d0e10;--surface:#15161a;--raised:#1a1b20;--sunk:#1d1e23;--rule:#26272d;--rule-strong:#393a42;
--ink:#eeeff1;--ink-2:#c8c9cf;--muted:#a1a3ab;--faint:#787b83;
--accent:#9eacff;--accent-soft:#1d2140;--on-tone:#0d0e10;
--pass:#5fcb86;--fail:#ff8b86;--warn:#e8b65c;--unknown:#a6a9b1;--info:#82b7ff;
--pass-soft:#132619;--fail-soft:#2c1615;--warn-soft:#2a2111;--info-soft:#15202d;
--shadow:0 1px 2px rgba(0,0,0,.4);--lift:0 16px 36px -20px rgba(0,0,0,.85)}
*,*::before,*::after{box-sizing:border-box}
html{scroll-padding-top:84px;-webkit-text-size-adjust:100%}
@media (prefers-reduced-motion: no-preference){html{scroll-behavior:smooth}}
body{margin:0;background:var(--bg);color:var(--ink);font:15.5px/1.55 var(--sans);-webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 0}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}
code,pre{font-family:var(--mono);font-size:.84em}
code{overflow-wrap:anywhere;word-break:break-word}
p{margin:0}
abbr[title]{text-decoration:none;cursor:help}
[hidden]{display:none!important}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.sprite{display:none}
.ic{width:16px;height:16px;flex:none;vertical-align:-3px}
.lv{color:var(--tone,var(--muted))}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:4px}
.skip{position:absolute;left:16px;top:-60px;background:var(--surface);color:var(--ink);padding:8px 14px;border-radius:var(--r-sm);z-index:30;box-shadow:var(--lift)}
.skip:focus{top:10px}
.quiet,.muted{color:var(--muted)}
.empty{color:var(--muted);margin:6px 0}
.tone-pass{--tone:var(--pass)}.tone-fail{--tone:var(--fail)}.tone-warn{--tone:var(--warn)}.tone-blocked{--tone:var(--warn)}
.tone-unknown{--tone:var(--unknown)}.tone-not_run{--tone:var(--faint)}.tone-neutral{--tone:var(--muted)}.tone-accent{--tone:var(--accent)}
.tone-info{--tone:var(--info)}.tone-muted{--tone:var(--faint)}
/* top bar */
.topbar{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:saturate(1.2) blur(10px);border-bottom:1px solid var(--rule)}
.topbar-inner{max-width:1440px;margin:0 auto;padding:0 28px;height:56px;display:flex;align-items:center;gap:18px}
.brand{display:flex;align-items:center;gap:11px;color:var(--ink);text-decoration:none;flex:none}
.logo{width:22px;height:22px;flex:none}
.brand-name{font-weight:680;letter-spacing:-.015em}
.brand-product{color:var(--muted);font-size:.875rem;padding-left:11px;border-left:1px solid var(--rule-strong);white-space:nowrap}
.topbar-context{display:flex;align-items:center;gap:10px;min-width:0;color:var(--muted);font-size:.875rem;opacity:0;transform:translateY(4px);transition:opacity .2s ease,transform .2s ease;overflow:hidden;white-space:nowrap}
.topbar-context.show{opacity:1;transform:none}
.tc-status{color:var(--ink-2);font-weight:550;overflow:hidden;text-overflow:ellipsis}
.controls{display:flex;align-items:center;gap:8px;margin-left:auto}
.lang{display:flex;align-items:center;gap:6px;color:var(--muted)}
.select,.search{font:inherit;font-size:.875rem;color:var(--ink);background:var(--surface);border:1px solid var(--rule-strong);border-radius:var(--r-sm);padding:6px 10px;min-height:34px}
.select{appearance:none;padding-right:30px;background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%);background-position:calc(100% - 15px) 52%,calc(100% - 10px) 52%;background-size:5px 5px;background-repeat:no-repeat}
.select:hover,.search:hover,.toggle:hover{border-color:var(--faint)}
.toggle{font:inherit;font-size:.875rem;display:inline-flex;align-items:center;gap:8px;color:var(--ink);background:var(--surface);border:1px solid var(--rule-strong);border-radius:999px;padding:5px 13px;min-height:34px;cursor:pointer}
.toggle[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
/* shell and navigation */
.shell{max-width:1440px;margin:0 auto;padding:0 28px;display:grid;grid-template-columns:184px minmax(0,1fr);gap:48px}
.sidenav{position:sticky;top:56px;align-self:start;max-height:calc(100vh - 56px);overflow:auto;padding:28px 0 24px}
.sidenav ul{list-style:none;margin:0;padding:0}
.sidenav>ul>li{margin:0 0 2px}
.nav-area{display:flex;align-items:center;justify-content:space-between;gap:8px;color:var(--muted);text-decoration:none;padding:7px 10px 7px 12px;border-radius:var(--r-sm);font-size:.9rem;font-weight:550;position:relative;transition:color .15s ease,background .15s ease}
.nav-area::before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:2px;border-radius:2px;background:transparent;transition:background .15s ease}
.nav-area:hover{color:var(--ink);background:var(--sunk)}
li.active>.nav-area{color:var(--ink);background:var(--surface);box-shadow:var(--shadow)}
li.active>.nav-area::before{background:var(--accent)}
.badge{font-size:.75rem;font-weight:650;color:var(--muted);background:var(--sunk);border-radius:999px;padding:0 7px;line-height:1.6;font-variant-numeric:tabular-nums}
li.active .badge{background:var(--accent-soft);color:var(--accent)}
.nav-sub{display:none;margin:2px 0 8px 12px!important;border-left:1px solid var(--rule)}
li.active>.nav-sub{display:block}
.nav-sub a{display:block;color:var(--muted);text-decoration:none;font-size:.84rem;padding:3px 10px}
.nav-sub a:hover{color:var(--ink)}
main{min-width:0;padding:0 0 96px}
main:focus{outline:none}
/* identity */
.area.area-overview{padding-top:28px;margin-top:0}
.ident{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 32px;margin-bottom:18px}
.eyebrow{flex-basis:100%;font-size:.8125rem;font-weight:600;color:var(--accent);margin-bottom:-4px}
h1{font-size:clamp(1.75rem,2.6vw,2.25rem);line-height:1.1;letter-spacing:-.025em;margin:0;font-weight:700;overflow-wrap:anywhere}
.idline{display:flex;flex-wrap:wrap;gap:4px 24px;margin:0;font-size:.875rem}
.idline div{display:flex;gap:6px;align-items:baseline}
.idline dt{color:var(--faint)}
.idline dd{margin:0;color:var(--ink-2)}
.ws.dirty{color:var(--warn)}
.arrow{color:var(--faint);margin:0 6px;font-weight:400}
/* decision surface */
.decision{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,380px);grid-template-rows:auto 1fr auto;grid-template-areas:"main rail" "extra rail" "facts facts";background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-lg);box-shadow:var(--lift);overflow:hidden;position:relative}
.decision::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--tone,var(--muted))}
.d-main{grid-area:main;padding:26px 30px 0 34px;min-width:0}
.d-extra{grid-area:extra;padding:0 30px 24px 34px;min-width:0}
.c-label{font-size:.8125rem;color:var(--muted);font-weight:550;margin-bottom:6px}
.c-headline{display:flex;align-items:center;gap:12px;font-size:clamp(1.6rem,2.4vw,2.05rem);line-height:1.15;font-weight:680;letter-spacing:-.022em}
.c-ic{width:.8em;height:.8em;color:var(--tone)}
.c-reason{font-size:1.0625rem;color:var(--ink-2);margin-top:10px;max-width:60ch}
.c-chips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px}
.c-total{font-size:1.0625rem;font-weight:650;margin-right:4px}
.c-more{font-size:.875rem;font-weight:550;margin-left:4px}
.chip{display:inline-flex;align-items:baseline;gap:5px;font-size:.875rem;padding:3px 10px;border-radius:999px;background:var(--sunk);color:var(--ink-2);border:1px solid var(--rule)}
.chip b{font-variant-numeric:tabular-nums;font-weight:700;color:var(--ink)}
.chip.sev-high{background:var(--fail-soft);border-color:color-mix(in srgb,var(--fail) 30%,transparent)}.chip.sev-high b{color:var(--fail)}
.chip.sev-medium{background:var(--warn-soft);border-color:color-mix(in srgb,var(--warn) 30%,transparent)}.chip.sev-medium b{color:var(--warn)}
.chip.sev-pass{background:var(--pass-soft);border-color:color-mix(in srgb,var(--pass) 30%,transparent)}.chip.sev-pass b{color:var(--pass)}
.chip.zero b{color:var(--faint)}
.c-scope{display:flex;align-items:center;gap:8px;margin-top:16px;font-size:.9375rem;color:var(--ink-2)}
.c-scope .ic{color:var(--ink-2)}
.rail{grid-area:rail;padding:24px 26px;border-left:1px solid var(--rule);background:color-mix(in srgb,var(--accent-soft) 45%,var(--surface));min-width:0;display:flex;flex-direction:column;align-items:flex-start}
.rail-label{display:flex;align-items:center;gap:7px;font-size:.8125rem;font-weight:650;color:var(--accent);margin:0 0 10px;letter-spacing:.01em}
.rail-act{font-size:1.1875rem;line-height:1.35;font-weight:650;letter-spacing:-.012em}
.rail-act.quiet{font-size:1rem;font-weight:500;color:var(--ink-2)}
.rail-dl{margin:14px 0 0;display:grid;gap:10px;font-size:.9rem}
.rail-dl dt{font-size:.78rem;color:var(--muted);font-weight:600}
.rail-dl dd{margin:2px 0 0;color:var(--ink-2)}
.rail-dl a{color:var(--ink);font-weight:550;margin-right:6px}
.rail-list{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:6px;font-size:.9375rem}
.rail-list li{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rail-list a{color:var(--ink);font-weight:550}
.rail-note{font-size:.875rem;color:var(--muted);margin-top:10px}
.rail-foot{font-size:.78rem;color:var(--muted);margin-top:auto;padding-top:14px}
.btn{display:inline-flex;align-items:center;gap:7px;margin-top:16px;font-size:.875rem;font-weight:600;color:var(--on-tone);background:var(--accent);border-radius:var(--r-sm);padding:7px 13px;text-decoration:none;border:1px solid var(--accent);font-family:inherit;cursor:pointer}
.btn .ic{width:14px;height:14px;transition:transform .15s ease}
.btn:hover .ic{transform:translateX(2px)}
.btn.ghost{background:transparent;color:var(--accent)}
.btn.small{margin-top:0;padding:4px 10px;font-size:.8125rem}
.facts{grid-area:facts;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--rule)}
.fact{padding:18px 24px 20px 34px;min-width:0}
.fact+.fact{border-left:1px solid var(--rule);padding-left:24px}
.fact h3{display:flex;align-items:center;gap:8px;font-size:.875rem;font-weight:600;margin:0 0 6px;color:var(--ink-2)}
.fact h3 .ic{color:var(--tone)}
.d-conf{--tone:var(--pass)}.d-att{--tone:var(--warn)}.d-unk{--tone:var(--unknown)}
.f-fig{font-size:1.25rem;font-weight:680;letter-spacing:-.015em;margin-bottom:8px;font-variant-numeric:tabular-nums}
.f-fig .quiet{font-size:1rem;font-weight:500}
.f-chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.fnote{font-size:.84rem;color:var(--muted);margin-top:6px}
.flist{list-style:none;margin:0;padding:0;display:grid;gap:4px;font-size:.9rem;color:var(--ink-2)}
.flist li{padding-left:14px;position:relative;overflow-wrap:anywhere}
.flist li::before{content:"";position:absolute;left:1px;top:.6em;width:5px;height:5px;border-radius:50%;background:var(--tone)}
.flist.links a{color:var(--ink-2);text-decoration-color:var(--rule-strong)}
.flist .more-n{color:var(--muted)}.flist .more-n::before{display:none}
.signal{display:flex;align-items:baseline;gap:6px;flex-wrap:wrap;margin-top:10px;padding-top:8px;border-top:1px dashed var(--rule-strong);font-size:.84rem;color:var(--muted)}
.signal .ic{width:12px;height:12px;color:var(--info);transform:translateY(1px)}
.signal>span:first-of-type{color:var(--info);font-weight:600}
.tier-code{font-family:var(--mono);font-size:.72rem;color:var(--faint);border:1px solid var(--rule-strong);border-radius:4px;padding:0 4px;margin-left:2px}
.fact .link{margin-top:10px}
.link{display:inline-flex;align-items:center;gap:6px;font-size:.875rem;font-weight:600;text-decoration:none}
.link:hover{text-decoration:underline}
.link .ic{width:13px;height:13px}
/* in-panel scope strip and lifecycle */
.mini-label{font-size:.78rem;font-weight:600;color:var(--muted);margin:0 0 8px}
.scope-strip,.life{margin-top:20px;padding-top:16px;border-top:1px dashed var(--rule)}
.scope-strip ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:2px 18px}
.scope-strip a{display:grid;grid-template-columns:18px minmax(0,1fr) auto;gap:8px;align-items:center;padding:4px 0;color:var(--ink-2);text-decoration:none;font-size:.875rem;border-bottom:1px solid transparent}
.scope-strip a:hover{border-bottom-color:var(--rule-strong)}
.scope-strip .lv{width:15px;height:15px}
.ss-level{font-size:.78rem;color:var(--tone);font-weight:600;white-space:nowrap}
.steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 18px;counter-reset:step}
.step{display:grid;grid-template-columns:18px minmax(0,1fr);gap:1px 8px;align-items:center;counter-increment:step}
.step .lv{width:17px;height:17px}
.step-name{font-weight:600;font-size:.9rem}
.step-name::before{content:counter(step) ". ";color:var(--faint);font-weight:500}
.step-state{grid-column:2;font-size:.8125rem;color:var(--tone,var(--muted))}
.step.st-todo .step-name{color:var(--muted)}
/* ledger */
.sub{margin-top:44px}
.sub-head{margin-bottom:14px;max-width:76ch}
.sub-head h2,.area-head h2{font-size:1.375rem;font-weight:680;letter-spacing:-.018em;line-height:1.25;margin:0}
.sub-head h3{font-size:1.125rem;letter-spacing:-.01em;margin:0}
.lead{color:var(--muted);margin-top:6px;font-size:.9375rem;max-width:72ch}
.ledger{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r)}
.lrow{display:grid;grid-template-columns:minmax(150px,210px) minmax(150px,190px) minmax(0,1fr) 24px;gap:18px;align-items:center;padding:11px 16px;border-top:1px solid var(--rule)}
.lrow:first-child{border-top:0}
.lrow:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.l-area{font-weight:600}
.l-level{display:flex;align-items:center;gap:8px;font-size:.9rem;color:var(--tone);font-weight:600}
.l-level .lv{width:17px;height:17px}
.l-detail{color:var(--ink-2);font-size:.9375rem;min-width:0}
.l-go{color:var(--faint);display:flex;justify-content:center}
.l-go:hover{color:var(--accent)}
.lvl-not_evidenced .l-area,.lvl-declared .l-area{color:var(--ink-2);font-weight:500}
.lvl-failed{background:var(--fail-soft)}
.ledger-foot{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:flex-start;justify-content:space-between;margin-top:12px}
.legend{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.8125rem;color:var(--muted)}
.legend li{display:flex;align-items:center;gap:5px}
.legend .lv{width:13px;height:13px}
.limits{font-size:.9rem;color:var(--ink-2);max-width:64ch}
.limits>summary{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2);font-weight:550}
.limits[open]>summary{margin-bottom:8px}
.limits-none{font-size:.875rem;color:var(--muted)}
.original{margin-top:10px;padding:10px 12px;background:var(--sunk);border-radius:var(--r-sm)}
.original-label,.tech-label{font-size:.8125rem;color:var(--muted);font-weight:600;margin:12px 0 4px}
.original .original-label{margin-top:0}
.raw-text{color:var(--ink-2)}
summary{cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
.chev{transition:transform .18s ease;color:var(--muted)}
details[open]>summary .chev{transform:rotate(180deg)}
@media (prefers-reduced-motion: no-preference){details[open]>summary~*{animation:reveal .18s ease}}
@keyframes reveal{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:none}}
:target{animation:flash 1.4s ease}
@keyframes flash{0%{box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 45%,transparent)}100%{box-shadow:0 0 0 3px transparent}}
@media (prefers-reduced-motion: reduce){:target{animation:none;outline:2px solid var(--accent)}}
/* areas */
.area{padding-top:56px;margin-top:8px}
.area-head{margin-bottom:20px;max-width:80ch;display:flex;flex-direction:column}
.area-head .lead{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.chips{display:inline-flex;flex-wrap:wrap;gap:6px}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:.8rem;font-weight:600;line-height:1.2;padding:3px 9px 3px 7px;border-radius:999px;color:var(--tone,var(--unknown));background:color-mix(in srgb,var(--tone,var(--unknown)) 12%,transparent);border:1px solid color-mix(in srgb,var(--tone,var(--unknown)) 30%,transparent);white-space:nowrap;vertical-align:middle}
.pill .ic{width:12px;height:12px}
.pill.tone-blocked{border-style:double;border-width:3px;padding:1px 7px 1px 5px}
.pill.tone-unknown{border-style:dotted}
.pill.tone-not_run{border-style:dashed}
.tier,.basis{font-size:.8125rem;color:var(--muted);white-space:nowrap}
.tag{display:inline-block;font-family:var(--mono);font-size:.78rem;background:var(--sunk);border-radius:5px;padding:1px 6px;margin:1px 4px 1px 0}
.dot-sep{color:var(--faint);margin:0 2px}
/* findings */
.filters{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;margin:0 0 14px;padding:10px 12px;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r)}
.filters label{font-size:.84rem;color:var(--muted)}
.search{flex:1 1 220px;min-width:0}
#findings-count{margin-left:auto;font-size:.84rem;font-variant-numeric:tabular-nums}
.finding-list{display:grid;gap:8px}
.finding{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);position:relative;overflow:hidden;transition:border-color .15s ease,box-shadow .15s ease}
.finding::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--rule-strong)}
.finding.sev-high::before{background:var(--fail)}.finding.sev-medium::before{background:var(--warn)}
.finding:hover{border-color:var(--rule-strong)}
.finding[open]{box-shadow:var(--lift);border-color:var(--rule-strong)}
.f-row{display:grid;grid-template-columns:100px minmax(0,1fr) 20px;grid-template-areas:"sev title chev" ". why ." ". meta .";gap:3px 16px;padding:15px 18px 14px 20px;align-items:start}
.f-row>.f-sev{grid-area:sev}.f-row>.f-title{grid-area:title;margin:0}.f-row>.f-why{grid-area:why}.f-row>.f-meta{grid-area:meta}.f-row>.chev{grid-area:chev}
.f-row:hover .f-title{text-decoration:underline;text-decoration-color:var(--rule-strong);text-underline-offset:4px}
.f-sev{padding-top:1px}
.f-title{font-size:1.04rem;line-height:1.35;font-weight:640;letter-spacing:-.005em}
.f-why{display:block;color:var(--ink-2);font-size:.9375rem;max-width:80ch}
.f-meta{display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;font-size:.84rem;color:var(--muted)}
.finding .chev{margin-top:4px}
.finding.compact .f-row{padding-top:11px;padding-bottom:10px}
.finding.compact .f-title{font-size:.96rem;font-weight:580}
.f-body{padding:4px 22px 22px 136px;display:grid;gap:16px;max-width:1020px;border-top:1px solid var(--rule);padding-top:16px}
.f-block h4{font-size:.875rem;margin:0 0 4px;display:flex;align-items:center;gap:10px;color:var(--ink-2)}
.f-fix p{font-weight:550}
.affected{font-weight:600;margin-bottom:4px}
.tech>summary,.more>summary{display:inline-flex;align-items:center;gap:6px;font-size:.84rem;color:var(--accent);font-weight:600}
.tech>summary::before,.more>summary::before{content:"";width:6px;height:6px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(-45deg);transition:transform .15s ease}
.tech[open]>summary::before,.more[open]>summary::before{transform:rotate(45deg)}
.kv{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:5px 16px;margin:8px 0;font-size:.84rem}
.kv dt{color:var(--muted)}
.kv dd{margin:0;min-width:0;overflow-wrap:anywhere}
pre.code{margin:6px 0 0;padding:12px 14px;background:var(--sunk);border-radius:var(--r-sm);white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;max-height:420px;overflow:auto;font-size:.79rem;line-height:1.55;position:relative}
pre.code.clamped{max-height:13.5em;overflow:hidden;-webkit-mask-image:linear-gradient(#000 70%,transparent);mask-image:linear-gradient(#000 70%,transparent)}
pre.code.full{max-height:none}
.expand{margin-top:6px;font:inherit;font-size:.8125rem;font-weight:600;color:var(--accent);background:none;border:0;padding:2px 0;cursor:pointer}
pre.diff{white-space:pre;overflow-x:auto}
.list{margin:4px 0;padding-left:1.15em}
.list li{margin:3px 0;overflow-wrap:anywhere}
.list li::marker{color:var(--faint)}
/* improvements: plan */
.rec-group{margin-top:24px}
.rec-group>h3{display:flex;align-items:center;gap:10px;font-size:1rem;margin:0 0 10px}
.count{font-size:.78rem;font-weight:650;color:var(--muted);background:var(--sunk);border-radius:999px;padding:0 8px;line-height:1.7;font-variant-numeric:tabular-nums}
.g-first>h3{color:var(--accent)}
.group-note{color:var(--muted);font-size:.9rem;margin:-4px 0 10px}
.rec-list{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);overflow:hidden}
.g-first .rec-list{border-color:color-mix(in srgb,var(--accent) 40%,var(--rule));box-shadow:var(--lift)}
.rec+.rec{border-top:1px solid var(--rule)}
.rec summary{display:grid;grid-template-columns:34px minmax(0,1fr) auto 20px;gap:6px 14px;align-items:start;padding:13px 16px}
.rec summary:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.rec-n{font-family:var(--mono);font-size:.8rem;color:var(--faint);padding-top:3px}
.g-first .rec-n{color:var(--accent);font-weight:700}
.rec-main{display:flex;flex-direction:column;gap:2px;min-width:0}
.rec-act{font-weight:640;font-size:1rem}
.rec-why{color:var(--muted);font-size:.9rem}
.rec-side{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.rec-body{padding:0 16px 16px 64px}
.rec-text{color:var(--ink-2);max-width:80ch}
.rec-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px 24px;margin:12px 0 0;font-size:.875rem}
.rec-meta dt{color:var(--muted);font-size:.78rem;font-weight:600}
.rec-meta dd{margin:2px 0 0;color:var(--ink-2)}
.rec-meta a{color:var(--ink)}
.rec-states{list-style:none;margin:0;padding:0;display:flex;gap:4px;flex-wrap:wrap}
.rec-states li{font-size:.78rem;padding:1px 8px;border-radius:999px;border:1px dashed var(--rule-strong);color:var(--faint)}
.rec-states li.on{border-style:solid;border-color:var(--accent);color:var(--accent);font-weight:600}
/* evidence snapshot */
.tiles{display:flex;flex-wrap:wrap;gap:1px;background:var(--rule);border:1px solid var(--rule);border-radius:var(--r);overflow:hidden}
.tile{background:var(--surface);padding:16px 18px 18px;min-width:0;flex:1 1 190px}
.t-domain{display:flex;align-items:center;gap:7px;font-size:.8125rem;font-weight:600;color:var(--muted);margin-bottom:10px}
.t-domain .lv{width:14px;height:14px}
.t-value{font-size:1.75rem;font-weight:700;letter-spacing:-.025em;line-height:1.1;font-variant-numeric:tabular-nums;color:var(--ink)}
.tile.tone-fail .t-value{color:var(--fail)}
.t-label{font-size:.875rem;color:var(--ink-2);margin-top:3px}
.t-sub{font-size:.84rem;color:var(--muted);margin-top:6px}
.t-sub.bad{color:var(--fail);font-weight:600}
.t-note{font-size:.78rem;color:var(--warn);margin-top:4px}
.t-change{font-size:.8rem;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px dashed var(--rule)}
.of{color:var(--faint);margin:0 1px;font-weight:400}
.dmark{font-size:.75rem;font-weight:650;padding:0 6px;border-radius:4px}
.dm-improved{color:var(--pass);background:var(--pass-soft)}.dm-regressed{color:var(--fail);background:var(--fail-soft)}
.dm-changed{color:var(--muted);background:var(--sunk)}.dm-unknown{color:var(--unknown);background:var(--sunk)}
.t-change.dm-improved,.t-change.dm-regressed,.t-change.dm-changed,.t-change.dm-unknown{background:none}
/* disclosure panels (auditability, denser) */
.panels-d{margin-top:22px;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);overflow:hidden}
.panel-d+.panel-d{border-top:1px solid var(--rule)}
.panel-d>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 16px}
.panel-d>summary:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.pd-title{display:flex;align-items:baseline;flex-wrap:wrap;gap:2px 14px;min-width:0}
.pd-title h3{font-size:.98rem;margin:0;font-weight:620}
.pd-sum{color:var(--muted);font-size:.84rem}
.pd-body{padding:2px 16px 20px;font-size:.92rem}
.pd-body>.lead{margin:0 0 12px;font-size:.875rem}
.table-wrap{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-sm);overflow:hidden;margin:0 0 12px}
table{border-collapse:collapse;width:100%;font-size:.84rem}
caption{text-align:left;font-size:.84rem;font-weight:650;color:var(--ink-2);padding:10px 14px 6px}
th,td{text-align:left;vertical-align:top;padding:7px 14px;border-top:1px solid var(--rule)}
thead th{font-size:.78rem;font-weight:650;color:var(--muted);background:var(--sunk)}
tbody th{font-weight:500}
.num-col{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.m-name{display:block}
.m-id{display:block;font-size:.72rem;color:var(--faint)}
.th-note{display:block;font-size:.78rem;color:var(--muted);margin-top:3px;white-space:normal}
.dir{color:var(--muted)}
.origins{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:12px;margin-top:10px}
.origin{border:1px solid var(--rule);border-radius:var(--r-sm);min-width:0}
.origin-head{display:flex;justify-content:space-between;align-items:center;margin:0;padding:9px 14px;border-bottom:1px solid var(--rule);font-size:.9rem;background:var(--sunk)}
.origin-head .count{background:none;padding:0}
.check-list{list-style:none;margin:0;padding:0}
.check{border-top:1px solid var(--rule)}
.check:first-child{border-top:0}
.check summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:8px 14px}
.check summary:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.kind{font-size:.75rem;font-weight:650;padding:1px 7px;border-radius:var(--r-sm);background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.kind-unknown,.kind-custom{background:var(--sunk);color:var(--muted)}
.check-title{display:flex;flex-direction:column;min-width:0}
.check-name{font-weight:560;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.check-where{font-size:.8rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gate{font-size:.8rem;color:var(--muted);white-space:nowrap}
.gate-blocking{color:var(--ink);font-weight:600}
.check-body{padding:2px 14px 12px}
.cmd{margin-top:8px}
.cmd-head{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:.8rem;color:var(--muted);font-weight:600}
.copy{font:inherit;font-size:.78rem;display:inline-flex;gap:5px;align-items:center;color:var(--muted);background:var(--surface);border:1px solid var(--rule-strong);border-radius:var(--r-sm);padding:2px 8px;cursor:pointer;transition:color .15s ease,border-color .15s ease}
.copy:hover{color:var(--ink)}
.copy.done{color:var(--pass);border-color:var(--pass)}
.copy .ic{width:13px;height:13px}
code.wrap{white-space:pre-wrap}
.runs{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.run,.artifact{border:1px solid var(--rule);border-radius:var(--r-sm);padding:12px 14px}
.run-head{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
.run-title{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.run-how{color:var(--muted);font-size:.875rem;margin-top:4px}
.matrix{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.checks-list{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:5px;font-size:.84rem}
.checks-list li{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:14px 24px;margin-bottom:12px}
.cols h4{font-size:.875rem;margin:0 0 4px}
.meta-row{display:flex;flex-wrap:wrap;gap:6px 18px;color:var(--muted);font-size:.875rem;margin-bottom:10px;align-items:center}
/* candidate pillars */
.pillars{display:grid;gap:8px}
.pillar{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);overflow:hidden;position:relative}
.pillar::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--rule-strong)}
.pillar.st-fail,.pillar.st-blocked{border-color:color-mix(in srgb,var(--fail) 40%,var(--rule));box-shadow:var(--lift)}
.pillar.st-fail::before,.pillar.st-blocked::before{background:var(--fail)}
.pillar.st-pass::before{background:var(--pass)}
.pillar.st-unknown::before,.pillar.st-not_run::before{background:var(--unknown)}
.pillar>summary{display:grid;grid-template-columns:118px minmax(0,1fr) auto 20px;gap:14px;align-items:center;padding:13px 18px 13px 20px}
.pillar>summary:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.p-main{display:flex;flex-direction:column;gap:2px;min-width:0}
.p-name{font-size:1rem;margin:0;font-weight:640}
.p-reason{font-size:.9rem;color:var(--ink-2)}
.p-check{font-weight:600}
.pillar.st-pass .p-reason{color:var(--muted)}
.p-count{font-family:var(--mono);font-size:.8rem;color:var(--muted)}
.qlist{list-style:none;margin:0;padding:12px 20px 18px 152px;display:grid;gap:12px;border-top:1px solid var(--rule)}
.qrow{display:grid;grid-template-columns:110px minmax(0,1fr);gap:10px;align-items:start;margin-left:-118px}
.q-name{font-weight:600}
.q-sum{color:var(--ink-2);font-size:.92rem;margin-top:1px}
.q-main .tech{margin-top:4px}
.qrow.st-fail .q-name,.qrow.st-blocked .q-name{color:var(--fail)}
.changes{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);overflow:hidden}
.change+.change{border-top:1px solid var(--rule)}
.change summary{display:flex;align-items:center;gap:8px;padding:11px 16px;flex-wrap:wrap}
.change summary .chev{margin-left:auto}
.path{font-weight:600}
.change-body{padding:0 16px 16px}
/* delta */
.dcounts{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);overflow:hidden}
.dc{flex:1 1 140px;min-width:0}
.dc+.dc{border-left:1px solid var(--rule)}
.dc a{display:flex;flex-direction:column;gap:1px;padding:12px 16px;color:var(--ink-2);text-decoration:none;font-size:.84rem}
.dc a:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.dc-n{font-size:1.6rem;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:var(--ink);font-variant-numeric:tabular-nums}
.dc-improved .dc-n{color:var(--pass)}.dc-regressed .dc-n{color:var(--fail)}
.dc.zero .dc-n{color:var(--faint)}
.dc-regressed:not(.zero),.dc-unknown:not(.zero){background:var(--fail-soft)}
.dc-unknown:not(.zero){background:var(--sunk)}
.dgroup{margin-top:22px}
.dgroup>h3{display:flex;align-items:center;gap:10px;font-size:1rem;margin:0}
.dg-lead{color:var(--muted);font-size:.875rem;margin:2px 0 8px}
.dg-regressed>h3{color:var(--fail)}.dg-improved>h3{color:var(--pass)}
.drows{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r);overflow:hidden}
.drow{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:2px 14px;align-items:baseline;padding:9px 16px;border-top:1px solid var(--rule)}
.drow:first-child{border-top:0}
.d-glyph{font-family:var(--mono);font-weight:700;text-align:center;color:var(--muted)}
.d-improved .d-glyph{color:var(--pass)}.d-regressed .d-glyph{color:var(--fail)}
.d-regressed{background:var(--fail-soft)}
.d-name .m-name{font-weight:560}
.d-vals{font-variant-numeric:tabular-nums;font-weight:650;white-space:nowrap}
.d-note{grid-column:2/-1;font-size:.84rem;color:var(--muted)}
.dg-unchanged>summary{display:flex;align-items:center;justify-content:space-between;padding:11px 16px;color:var(--ink-2);font-weight:560;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r)}
.dg-unchanged[open]>summary{border-radius:var(--r) var(--r) 0 0}
.dg-unchanged .drows{border-top:0;border-radius:0 0 var(--r) var(--r)}
.dg-unchanged .drow{color:var(--muted)}
/* technical details */
.area-tech{font-size:.94rem}
.prov{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px 24px;margin:0 0 10px;padding:14px 16px;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r)}
.prov div{min-width:0}
.prov dt{font-size:.78rem;color:var(--muted);font-weight:600}
.prov dd{margin:2px 0 0;font-size:.9rem;overflow-wrap:anywhere}
.prov-warn{margin:0 0 10px;padding:10px 14px;border-radius:var(--r-sm);background:var(--warn-soft);color:var(--ink);border:1px solid color-mix(in srgb,var(--warn) 35%,transparent);font-size:.9rem}
.claim-groups{display:grid;gap:8px}
.claim-g{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r)}
.claim-g>summary{display:grid;grid-template-columns:minmax(160px,auto) minmax(0,1fr) 20px;gap:12px;align-items:center;padding:11px 16px}
.cg-title{display:flex;align-items:center;gap:8px;font-weight:620}
.cd-index{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.84rem;color:var(--muted)}
.cd-index li{display:flex;gap:5px;align-items:center}
.cd-index a{color:var(--ink-2);text-decoration:none}
.cd-index .count{background:none;padding:0}
.cg-body{padding:4px 16px 14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:4px 28px;border-top:1px solid var(--rule)}
.cd{padding-top:10px}
.cd-head{display:flex;align-items:center;gap:8px;font-size:.84rem;font-weight:650;color:var(--ink-2)}
.cd .list{font-size:.875rem}
.budget{list-style:none;margin:0;padding:0}
.budget-row{display:grid;grid-template-columns:auto minmax(110px,220px) minmax(0,1fr);gap:12px;align-items:baseline;padding:8px 0;border-top:1px solid var(--rule);font-size:.84rem}
.budget-reason{color:var(--muted)}
.more{margin:8px 0}
.footer{max-width:1440px;margin:0 auto;padding:24px 28px;color:var(--muted);font-size:.8rem;border-top:1px solid var(--rule)}
/* responsive */
@media (max-width:1180px){.shell{grid-template-columns:minmax(0,1fr);gap:0}
.sidenav{position:sticky;top:56px;z-index:15;max-height:none;margin:0 -28px;padding:8px 28px;background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--rule);overflow-x:auto;scrollbar-width:none}
.sidenav>ul{display:flex;gap:6px;width:max-content}.sidenav>ul>li{margin:0}.nav-sub,li.active>.nav-sub{display:none}
.nav-area{border:1px solid var(--rule);border-radius:999px;padding:5px 13px;white-space:nowrap;font-size:.875rem}
.nav-area::before{display:none}
li.active>.nav-area{border-color:var(--ink);background:var(--ink);color:var(--bg)}
li.active .badge{background:color-mix(in srgb,var(--bg) 22%,transparent);color:var(--bg)}
html{scroll-padding-top:120px}
.area.area-overview{padding-top:22px}
.topbar-context{display:none}
}
@media (max-width:900px){.decision{grid-template-columns:minmax(0,1fr);grid-template-rows:auto;grid-template-areas:"main" "rail" "extra" "facts"}
.d-main{padding-bottom:20px}.d-extra{border-top:1px solid var(--rule)}.d-extra>div{margin-top:0;border-top:0}
.rail{border-left:0;border-top:1px solid var(--rule)}
.facts{grid-template-columns:minmax(0,1fr)}.fact+.fact{border-left:0;border-top:1px solid var(--rule);padding-left:34px}
.lrow{grid-template-columns:minmax(0,1fr) auto;gap:4px 12px}.l-detail{grid-column:1/-1}.l-go{display:none}
.f-body{padding-left:22px}
.qlist{padding-left:20px}.qrow{margin-left:0}
.pillar>summary{grid-template-columns:minmax(0,1fr) auto 20px}.pillar>summary>.pill{grid-column:1/-1;justify-self:start}
.rec-body{padding-left:16px}}
@media (max-width:640px){body{font-size:15px}.topbar-inner,.shell{padding:0 16px}.sidenav{margin:0 -16px;padding:8px 16px}
.brand-product,.toggle-text{display:none}.lang .ic{display:none}.lang .select{max-width:140px}
.ident{margin-bottom:14px}.d-main{padding:20px 18px 18px 22px}.d-extra{padding:0 18px 18px 22px}.rail{padding:18px 18px 18px 22px}.fact,.fact+.fact{padding:14px 18px 16px 22px}
.steps{grid-template-columns:repeat(2,minmax(0,1fr))}
.f-row{grid-template-columns:minmax(0,1fr) 20px;grid-template-areas:"sev chev" "title title" "why why" "meta meta";padding:13px 14px 12px 18px}
.rec summary{grid-template-columns:26px minmax(0,1fr) 20px}.rec-side{grid-column:2;justify-content:flex-start}
.dcounts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.dc+.dc{border-left:0}.dc{border-top:1px solid var(--rule)}.dc:nth-child(-n+2){border-top:0}.dc:nth-child(even){border-left:1px solid var(--rule)}
.claim-g>summary{grid-template-columns:minmax(0,1fr) 20px}.cd-index{grid-column:1/-1;grid-row:2}
table.responsive thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
table.responsive tr{display:block;border-top:1px solid var(--rule);padding:6px 0}
table.responsive th,table.responsive td{display:block;border:0;padding:3px 12px;text-align:left}
table.responsive td[data-label]::before{content:attr(data-label);display:block;font-size:.75rem;color:var(--muted)}
.num-col{text-align:left}
.check summary{grid-template-columns:minmax(0,1fr) auto}.check summary .kind{grid-column:1/-1;justify-self:start}
.budget-row{grid-template-columns:minmax(0,1fr)}.kv{grid-template-columns:minmax(0,1fr)}.kv dt{margin-top:6px}
.drow{grid-template-columns:20px minmax(0,1fr)}.d-vals{grid-column:2}
.qrow{grid-template-columns:minmax(0,1fr)}}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
.no-anim *{transition:none!important}
@media print{
@page{margin:14mm}
body{background:#fff;color:#000;font-size:11pt}
.topbar,.sidenav,.filters,.copy,.skip,.expand,.l-go,.btn,.chev{display:none!important}
.shell{display:block;padding:0}
.decision,.ledger,.finding,.pillar,.tile,.rec,.panels-d,.claim-g,.prov{box-shadow:none;break-inside:avoid}
.area{padding-top:18px;break-before:auto}
pre.code,pre.code.clamped{max-height:none;-webkit-mask-image:none;mask-image:none;overflow:visible}
a{color:inherit;text-decoration:none}
.footer{border:0}}
"""

_JS = r"""
(function(){
var root=document.documentElement,data={};
try{data=JSON.parse(document.getElementById('i18n').textContent)||{};}catch(e){}
var dict={'pt-BR':data['pt-BR']||{}},S=data.js||{};
function load(k){try{return localStorage.getItem(k);}catch(e){return null;}}
function save(k,v){try{localStorage.setItem(k,v);}catch(e){}}
var lang=root.getAttribute('data-rendered')||'en';
function str(k){return ((S[lang]||S.en||{})[k])||((S.en||{})[k])||k;}
var ATTRS=['aria-label','placeholder','title','data-label'];
function apply(next){lang=next;root.setAttribute('lang',lang);var d=dict[lang]||{};
 document.querySelectorAll('[data-i18n]').forEach(function(el){
  if(el.dataset.en===undefined)el.dataset.en=el.textContent;
  var t=lang==='en'?el.dataset.en:(d[el.dataset.i18n]||el.dataset.en);
  if(el.textContent!==t)el.textContent=t;});
 ATTRS.forEach(function(a){var store='en'+a.replace(/-/g,'');
  document.querySelectorAll('[data-i18n-'+a+']').forEach(function(el){
   if(el.dataset[store]===undefined)el.dataset[store]=el.getAttribute(a)||'';
   var key=el.getAttribute('data-i18n-'+a);el.setAttribute(a,lang==='en'?el.dataset[store]:(d[key]||el.dataset[store]));});});
 var s=document.getElementById('lang');if(s)s.value=lang;localTimes();counts();expanders();}
function localTimes(){document.querySelectorAll('time[data-local]').forEach(function(t){
 var dt=new Date(t.getAttribute('datetime'));if(isNaN(dt))return;
 try{t.textContent=new Intl.DateTimeFormat(lang,{dateStyle:'medium',timeStyle:'short'}).format(dt)+' ('+str('local')+')';}catch(e){return;}
 t.title=t.getAttribute('datetime');});}
var saved=load('assertiva.lang'),nav=(navigator.language||'').toLowerCase();
var initial=saved==='pt-BR'||saved==='en'?saved:(nav.indexOf('pt')===0?'pt-BR':lang);
var sel=document.getElementById('lang');
if(sel)sel.addEventListener('change',function(){save('assertiva.lang',sel.value);apply(sel.value);});
var btn=document.getElementById('theme');
function dark(){var t=root.getAttribute('data-theme');return t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches;}
function sync(){if(btn)btn.setAttribute('aria-pressed',String(dark()));}
var savedTheme=load('assertiva.theme');if(savedTheme==='dark'||savedTheme==='light')root.setAttribute('data-theme',savedTheme);
if(btn)btn.addEventListener('click',function(){var next=dark()?'light':'dark';root.setAttribute('data-theme',next);save('assertiva.theme',next);sync();});
sync();
/* findings filters, mirrored in the URL */
var F={sev:document.getElementById('sev'),cat:document.getElementById('cat'),q:document.getElementById('q')},clear=document.getElementById('clear-filters');
function counts(){var c=document.getElementById('findings-count');if(!c)return;var shown=document.querySelectorAll('.finding:not([hidden])').length,all=document.querySelectorAll('.finding').length;
 c.textContent=str('count').replace('{a}',shown).replace('{b}',all);var em=document.getElementById('findings-empty');if(em)em.hidden=shown>0;}
function filter(push){var s=(F.sev||{}).value||'',c=(F.cat||{}).value||'',q=((F.q||{}).value||'').toLowerCase();
 document.querySelectorAll('.finding').forEach(function(e){e.hidden=!!((s&&e.dataset.severity!==s)||(c&&e.dataset.category!==c)||(q&&e.textContent.toLowerCase().indexOf(q)<0));});
 if(clear)clear.hidden=!(s||c||q);counts();
 if(push){try{var p=new URLSearchParams();if(s)p.set('sev',s);if(c)p.set('cat',c);if(q)p.set('q',q);var qs=p.toString();history.replaceState(null,'',(qs?'?'+qs:location.pathname)+location.hash);}catch(e){}}}
['sev','cat','q'].forEach(function(i){F[i]&&F[i].addEventListener('input',function(){filter(true);});});
if(clear)clear.addEventListener('click',function(){['sev','cat','q'].forEach(function(i){if(F[i])F[i].value='';});filter(true);F.q&&F.q.focus();});
try{var P=new URLSearchParams(location.search);['sev','cat','q'].forEach(function(i){if(F[i]&&P.get(i))F[i].value=P.get(i);});if(P.toString())filter(false);}catch(e){}
var k=document.getElementById('kind');k&&k.addEventListener('input',function(){
 document.querySelectorAll('.check[data-kind]').forEach(function(t){t.hidden=!!k.value&&t.dataset.kind!==k.value;});
 document.querySelectorAll('.origin').forEach(function(o){o.hidden=!o.querySelector('.check:not([hidden])');});});
/* deep links open the collapsed detail they point to */
function reveal(){var id=decodeURIComponent(location.hash.slice(1));if(!id)return;var el=document.getElementById(id);if(!el)return;
 var opened=false;for(var n=el;n;n=n.parentElement){if(n.tagName==='DETAILS'&&!n.open){n.open=true;opened=true;}}
 if(opened&&el.scrollIntoView)el.scrollIntoView({block:'start'});}
window.addEventListener('hashchange',reveal);reveal();
/* bounded raw blocks */
function expanders(){document.querySelectorAll('pre.code').forEach(function(pre){
 var b=pre.nextElementSibling&&pre.nextElementSibling.classList.contains('expand')?pre.nextElementSibling:null;
 if(!b){if(pre.scrollHeight<=260||pre.classList.contains('diff'))return;b=document.createElement('button');b.type='button';b.className='expand';
  pre.classList.add('clamped');pre.after(b);b.addEventListener('click',function(){var full=pre.classList.toggle('full');pre.classList.toggle('clamped',!full);
   b.setAttribute('aria-expanded',String(full));b.textContent=str(full?'collapse':'show_full');});b.setAttribute('aria-expanded','false');}
 b.textContent=str(pre.classList.contains('full')?'collapse':'show_full');});}
document.addEventListener('toggle',function(ev){if(ev.target.open)expanders();},true);
/* active section */
root.classList.add('no-anim');requestAnimationFrame(function(){requestAnimationFrame(function(){root.classList.remove('no-anim');});});
var areas=[].slice.call(document.querySelectorAll('main .area')),links={},ctx=document.querySelector('.topbar-context'),hero=document.querySelector('.decision');
document.querySelectorAll('.sidenav [data-area]').forEach(function(li){links[li.getAttribute('data-area')]=li;});
function mark(id){Object.keys(links).forEach(function(a){var li=links[a],on=a===id;li.classList.toggle('active',on);var link=li.querySelector('.nav-area');
 if(on){link.setAttribute('aria-current','location');var bar=li.closest('.sidenav');if(bar&&getComputedStyle(li.parentElement).display==='flex'){var r=li.getBoundingClientRect(),b=bar.getBoundingClientRect();if(r.left<b.left||r.right>b.right)bar.scrollLeft+=r.left-b.left-16;}}
 else link.removeAttribute('aria-current');});}
function current(){var best=areas[0],line=window.innerHeight*0.3;areas.forEach(function(a){if(a.getBoundingClientRect().top<=line)best=a;});if(best)mark(best.id);
 if(ctx&&hero)ctx.classList.toggle('show',hero.getBoundingClientRect().bottom<0);}
var ticking=false;window.addEventListener('scroll',function(){if(!ticking){ticking=true;requestAnimationFrame(function(){ticking=false;current();});}},{passive:true});
current();
/* copy */
var live=document.getElementById('live');
document.addEventListener('click',function(ev){var b=ev.target.closest&&ev.target.closest('.copy');if(!b)return;
 var pre=b.closest('.cmd').querySelector('pre');var text=pre?pre.textContent:'';
 function done(){if(live)live.textContent=str('copied');b.classList.add('done');setTimeout(function(){b.classList.remove('done');},1500);}
 if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(text).then(done,function(){});}
 else{var rg=document.createRange();rg.selectNodeContents(pre);var s=getSelection();s.removeAllRanges();s.addRange(rg);try{document.execCommand('copy');done();}catch(e){}}});
/* print: every collapsed detail is part of the audit record */
var reopened=[];
window.addEventListener('beforeprint',function(){reopened=[].slice.call(document.querySelectorAll('details:not([open])'));reopened.forEach(function(d){d.open=true;});});
window.addEventListener('afterprint',function(){reopened.forEach(function(d){d.open=false;});reopened=[];});
if(initial!==lang)apply(initial);else{localTimes();counts();expanders();}
})();
"""
