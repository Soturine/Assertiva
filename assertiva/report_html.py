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
from pathlib import Path
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

def _outcome_counts(runs: list[dict]) -> dict[str, int] | None:
    """Summed per-outcome counts; None when a run predates them (older report JSON), so nothing is claimed from totals."""
    if not runs or any("outcomes" not in run for run in runs):
        return None
    total: dict[str, int] = {}
    for run in runs:
        for outcome, count in run["outcomes"].items():
            total[outcome] = total.get(outcome, 0) + count
    return total


def _passed_detail(counts: dict[str, int], key: str = "conf.tests.passed") -> Pair:
    """"N passed" from passed cases only; skipped, not-run and expected failures are named, never folded into passed."""
    parts = [pair_of(key, n=counts.get("PASSED", 0))]
    skipped = counts.get("SKIPPED", 0) + counts.get("NOT_RUN", 0)
    if skipped:
        parts.append(pair_of("conf.tail.skipped", n=skipped))
    if counts.get("XFAILED"):
        parts.append(pair_of("conf.tail.xfailed", n=counts["XFAILED"]))
    return _join(parts, (" · ", " · "))


def _confirmed(state: dict | None) -> list[tuple[Pair, str | None]]:
    """Facts backed by execution or deterministic evidence; never by the absence of a finding, never by a heuristic."""
    if not state:
        return []
    out: list[tuple[Pair, str | None]] = []
    tier = ((state.get("metrics") or {}).get("passed") or {}).get("evidence_tier")
    for run in state.get("runs", []):
        if run["status"] != "PASS" or not run["invocations"]:
            continue
        counts = _outcome_counts([run])
        if counts is None:
            out.append((pair_of("conf.run_passed", adapter=run["adapter"]), tier))
        elif counts.get("PASSED"):
            out.append((_passed_detail(counts, "conf.ingested.passed" if run["mode"] == "report" else "conf.tests.passed"), tier))
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
        counts = _outcome_counts(group)
        if counts is None:
            detail = pair_of("scope.tests.run", n=total, status=_lower(_label("st.", status)))
        else:
            detail = _passed_detail(counts, "scope.tests.passed")
            bad = counts.get("FAILED", 0) + counts.get("ERROR", 0)
            if bad:
                detail = _join([detail, pair_of("conf.tail.failing", n=bad)], (" · ", " · "))
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
        detail = pair_of("scope.negative", n=negative, m=_num(_metric(state, "negative_paths_without_contract_detail") or 0))
        post = _metric(state, "negative_paths_with_state_after_rejection")
        if post:  # a heuristic signal: shown with its inspected area, never as a confirmed fact
            detail = _join([detail, pair_of("scope.negative.post", n=post)], (" · ", " · "))
        rows.append({"area": "negative", "level": "INSPECTED", "detail": detail, "href": "#negative-paths"})
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
_AREA_ICON = {"tests": "flask", "coverage": "bars", "quality": "diamond", "negative": "branch", "fault": "shuffle",
              "artifact": "box", "ci": "branch", "local": "laptop", "deploy": "cloud"}


def _glyph(r: _R, level: str) -> str:
    return r.icon(_LEVEL_GLYPH[level], "ic lv")


def _legend(r: _R) -> str:
    items = "".join(f'<li class="tone-{_LEVEL_TONE[level]}">{_glyph(r, level)}{r.t("lvl." + level)}</li>'
                    for level in ("EXECUTED", "MEASURED", "INSPECTED", "DECLARED", "NOT_EVIDENCED"))
    return f'<ul class="legend" {r.attr("aria-label", "legend.label")}>{items}</ul>'


def _ledger_row(r: _R, area: Pair, level: str, detail: str, href: str | None = None, row_id: str = "", icon: str | None = None) -> str:
    tone = _LEVEL_TONE[level]
    rid = f' id="{row_id}"' if row_id else ""
    more = f'<a class="l-go" href="{href}" {r.attr("aria-label", "ledger.open")}>{r.icon("chev-r")}</a>' if href else ""
    area_icon = r.icon(icon, "ic l-ic") if icon else ""
    return (f'<li class="lrow lvl-{level.lower()} tone-{tone}"{rid}><span class="l-area">{area_icon}{r.p(area)}</span>'
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
    return "".join(_chip(r, "cnt." + sev, counts[sev], "sev-" + sev) for sev in ("high", "medium", "info") if counts[sev])


def _bar(fraction: float, tone: str = "pass") -> str:
    width = max(0.0, min(1.0, fraction)) * 100
    return f'<span class="bar tone-{tone}" aria-hidden="true"><span style="width:{width:.1f}%"></span></span>'


def _ring(percent: float, tone: str = "pass") -> str:
    """Decorative ring for a measured percentage; the number beside it is the information."""
    value = max(0.0, min(100.0, float(percent)))
    circumference = 2 * 3.14159 * 22
    dash = circumference * value / 100
    return (f'<svg class="ring tone-{tone}" viewBox="0 0 56 56" aria-hidden="true" focusable="false">'
            f'<circle cx="28" cy="28" r="22" class="ring-track"/><circle cx="28" cy="28" r="22" class="ring-val" '
            f'stroke-dasharray="{dash:.1f} {circumference:.1f}" transform="rotate(-90 28 28)"/></svg>')


# --- hero: identity, next step ------------------------------------------------------------

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


def _identity(r: _R) -> str:
    report = r.report
    project, prov = report["project"], report.get("provenance") or {}
    runtime = prov.get("runtime") or {}
    if report["workflow"] == "audit":
        mode = "mode.audit"
    else:
        mode = "mode.improve_applied" if report["states"].get("applied") else "mode.improve"
    revision = project.get("revision")
    revision_html = f'<code title="{_e(revision)}">{_e(revision[:12])}</code>' if revision else r.t("header.no_revision")
    dirty = bool(project.get("dirty"))
    when = r.p(_when(report["generated_at"]), tag="time", attrs=f' datetime="{_e(report["generated_at"])}" data-local')
    items = [
        ("calendar", "prov.generated", when),
        ("commit", "header.revision", revision_html),
        ("db", "prov.state", r.t("header.dirty" if dirty else "header.clean", cls="ws " + ("dirty" if dirty else "clean"))),
    ]
    if runtime.get("install") == "source-checkout" and runtime.get("revision"):
        items.append(("branch", "hero.runtime", f'<span>{_e(prov.get("assertiva_version"))}</span> <code title="{_e(runtime["revision"])}">{_e(runtime["revision"][:10])}</code>'))
    elif runtime.get("install"):
        items.append(("box", "hero.runtime", f'<span>{_e(prov.get("assertiva_version"))}</span> {r.t("prov.install." + runtime["install"], cls="muted")}'))
    if report["workflow"] == "improve":
        items.append(("layers", "states.shown", _ARROW_SEP.join(r.state(k) for k, _ in _states(report))))
    meta = "".join(f'<div>{r.icon(icon, "ic m-ic")}<dt>{r.t(key)}</dt><dd>{value}</dd></div>' for icon, key, value in items)
    art = f'<span class="hero-art" aria-hidden="true">{r.icon("shield" if report["workflow"] == "audit" else "layers", "ic")}</span>'
    return (f'<div class="ident">{art}<p class="eyebrow">{r.icon("shield", "ic")}{r.t(mode)}</p>'
            f'<h1 id="h-project">{_e(project.get("name") or "project")}</h1>'
            f'{r.t("hero.lead." + report["workflow"], tag="p", cls="ident-lead")}<dl class="idline">{meta}</dl></div>')


# --- conclusion, KPIs, decision cards ------------------------------------------------------

_VERDICT_BADGE = {"warn": "alert", "fail": "crossc", "unknown": "question", "neutral": "info", "accent": "checkc", "pass": "checkc"}


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
    else:
        findings = report["findings"]
        if findings:
            lines.append(f'<p class="c-chips"><span class="c-total">{r.t("att.count", n=len(findings))}</span>{_sev_chips(r, _severity_counts(findings))}</p>')
        if report["status"] in ("UNKNOWN", "NO_FINDINGS_IN_SCOPE") or not findings or not any(f["severity"] in ("high", "medium") for f in findings):
            lines.append(r.p(reason, tag="p", cls="c-reason"))
        shape, evmode = _evidence_mode(r)
        glyph = {"solid": "checkc", "half": "half", "hollow": "diamond"}[shape]
        lines.append(f'<p class="c-scope mode-{shape}">{r.icon(glyph, "ic")}{r.p(evmode)}</p>')
    badge = f'<span class="c-badge" aria-hidden="true">{r.icon(_VERDICT_BADGE.get(tone, "info"), "ic")}</span>'
    return (f'<div class="d-main">{badge}<div class="c-body"><p class="c-label" id="h-conclusion">{r.t("verdict.label")}</p>'
            f'<p class="c-headline">{r.icon(icon, "ic c-ic")}{r.p(headline)}</p>{"".join(lines)}</div></div>')


def _kpi(r: _R, icon: str, title_key: str, value: str, sub: str, extra: str = "", tone: str = "accent", side: str = "") -> str:
    return (f'<article class="kpi tone-{tone}"><div class="kpi-main"><p class="kpi-title">{r.icon(icon, "ic")}{r.t(title_key)}</p>'
            f'<p class="kpi-value">{value}</p><p class="kpi-sub">{sub}</p>{extra}</div>{side}</article>')


def _kpis(r: _R) -> str:
    report = r.report
    states = _states(report)
    if not states:
        return ""
    key, state = states[-1]
    tiles = []
    invocations, passed = _metric(state, "test_invocations"), _metric(state, "passed")
    if invocations and passed is not None:
        bad = (_metric(state, "failed") or 0) + (_metric(state, "errors") or 0) + (_metric(state, "collection_errors") or 0)
        skipped = _metric(state, "skipped") or 0
        notes = (r.t("snap.failing", tag="p", cls="kpi-note bad", n=bad) if bad else "") + (r.t("snap.skipped", tag="p", cls="kpi-note", n=skipped) if skipped else "")
        ratio = passed / invocations
        percent = r.p(_num(ratio * 100, "%", 1), cls="kpi-pct")
        tiles.append(_kpi(r, "play", "kpi.exec", f'{r.p(_num(passed))}<span class="of">/</span>{r.p(_num(invocations))}',
                          r.t("snap.passed"), f'<div class="kpi-bar">{_bar(ratio, "fail" if bad else "pass")}{percent}</div>{notes}',
                          "fail" if bad else "pass"))
    elif report["workflow"] == "audit":
        tiles.append(_kpi(r, "play", "kpi.exec", r.t("kpi.exec.none"), r.t("kpi.exec.none.sub"), tone="muted"))
    line = _metric(state, "line_coverage")
    if line is not None:
        branch = _metric(state, "branch_coverage")
        sub = r.t("snap.branches", tag="p", cls="kpi-note", value=_num(branch, "%", 1)) if branch is not None else ""
        tiles.append(_kpi(r, "bars", "kpi.cov", r.p(_num(line, "%", 1)), r.t("snap.lines"), sub, "info", _ring(line, "info")))
    else:
        tiles.append(_kpi(r, "bars", "kpi.cov", r.t("kpi.cov.none"), r.t("kpi.cov.none.sub"), tone="muted"))
    if report["workflow"] == "improve":
        checks = _checks(report)
        ok = sum(c["status"] == "PASS" for c in checks)
        tiles.append(_kpi(r, "shield", "kpi.quals", f'{_e(ok)}<span class="of">/</span>{_e(len(checks))}', r.t("kpi.quals.sub"),
                          f'<div class="kpi-bar">{_bar(ok / len(checks) if checks else 0, "warn" if ok < len(checks) else "pass")}</div>',
                          "warn" if ok < len(checks) else "pass"))
        delta = report.get("evidence_delta") or {}
        tiles.append(_kpi(r, "delta", "kpi.delta", _e(len(delta.get("improved") or [])), r.t("dc.improved", n=len(delta.get("improved") or [])),
                          f'<p class="kpi-note">{_chip(r, "dc.regressed", len(delta.get("regressed") or []), "sev-high" if delta.get("regressed") else "zero")}</p>',
                          "fail" if delta.get("regressed") else "pass"))
    else:
        surface = report.get("verification_surface") or []
        tiles.append(_kpi(r, "doc", "kpi.checks", _e(len(surface)), r.t("kpi.checks.sub"), tone="muted"))
        counts = _severity_counts(report["findings"])
        tiles.append(_kpi(r, "alert", "kpi.findings", _e(len(report["findings"])), r.t("kpi.findings.sub"),
                          f'<p class="kpi-note chips">{_sev_chips(r, counts)}</p>' if report["findings"] else "",
                          "warn" if counts["high"] or counts["medium"] else "muted"))
    return f'<section class="kpis" aria-labelledby="h-kpis"><h2 class="sr-only" id="h-kpis">{r.t("cards.title")}</h2>{"".join(tiles)}</section>'


def _fact(r: _R, cls: str, icon: str, title_key: str, count: int | None, body: str, link: str = "") -> str:
    figure = f'<span class="f-count">{count}</span>' if count is not None else ""
    return (f'<section class="fact {cls}" aria-labelledby="h-{cls}"><h3 id="h-{cls}"><span class="f-badge">{r.icon(icon)}</span>'
            f'{r.t(title_key)}{figure}</h3>{body}{link}</section>')


def _bullets(r: _R, pairs: list[Pair], limit: int = 3) -> str:
    if not pairs:
        return ""
    more = r.t("decision.more", tag="li", cls="more-n", n=len(pairs) - limit) if len(pairs) > limit else ""
    return '<ul class="flist">' + "".join(f"<li>{r.p(p)}</li>" for p in pairs[:limit]) + more + "</ul>"


def _improve_card(r: _R) -> str:
    recs = r.report.get("recommendations") or []
    body = (r.t("card.imp.count", tag="p", cls="fnote strong", n=len(recs)) + r.t("card.imp.lead", tag="p", cls="fnote")) if recs else r.t("card.imp.none", tag="p", cls="fnote")
    return (f'<section class="card-imp" aria-labelledby="h-card-imp"><h3 id="h-card-imp"><span class="f-badge">{r.icon("bulb")}</span>'
            f'{r.t("card.imp")}<span class="f-count">{len(recs)}</span></h3>{body}' + (r.link("#improvements", "card.imp.go") if recs else "") + "</section>")


def _facts_audit(r: _R) -> str:
    report = r.report
    state = report["states"].get("current")
    confirmed = _confirmed(state)
    conf_body = _bullets(r, [p for p, _ in confirmed]) if confirmed else r.t("conf.none.why", tag="p", cls="fnote")
    counts = _severity_counts(report["findings"])
    serious = [(i, f) for i, f in _sorted_findings(report["findings"]) if f["severity"] in ("high", "medium")]
    if serious:
        att_body = ('<ul class="flist links">' + "".join(f'<li><a href="#finding-{i}">{r.p(_finding_title(f))}</a></li>' for i, f in serious[:3])
                    + (r.t("decision.more", tag="li", cls="more-n", n=len(serious) - 3) if len(serious) > 3 else "") + "</ul>")
    else:
        att_body = r.t("att.none", tag="p", cls="fnote")
    if counts["info"]:
        att_body += r.t("att.info", tag="p", cls="fnote", n=counts["info"])
    shorts = [_short_unknown(item, report) for item in report["claim_boundary"].get("not_evidenced") or []]
    return (
        f'<div class="facts"><h2 class="sr-only" id="h-facts">{r.t("strip.title")}</h2>'
        + _fact(r, "d-conf", "check", "conf.title", len(confirmed), conf_body, r.link("#green", "conf.go"))
        + _fact(r, "d-att", "alert", "att.title", len(serious), att_body, r.link("#findings", "att.go") if report["findings"] else "")
        + _fact(r, "d-unk", "question", "unk.title", len(shorts), _bullets(r, shorts) or r.t("unk.none", tag="p", cls="fnote"),
                r.link("#green", "unk.go") if shorts else "")
        + _improve_card(r) + "</div>"
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
    changes = (report.get("change_set") or {}).get("changes") or []
    change_card = (f'<section class="card-imp" aria-labelledby="h-card-imp"><h3 id="h-card-imp"><span class="f-badge">{r.icon("doc")}</span>'
                   f'{r.t("changes.title")}<span class="f-count">{len(changes)}</span></h3>{r.t("changes.lead.short", tag="p", cls="fnote")}'
                   f'{r.link("#changes", "next.review.go")}</section>')
    return (
        f'<div class="facts"><h2 class="sr-only" id="h-facts">{r.t("strip.title")}</h2>'
        + _fact(r, "d-conf", "check", "conf.title", len(passed), _bullets(r, [_label("q.", c["check"]) for c in passed]) or r.t("conf.none", tag="p", cls="fnote"),
                r.link("#candidate", "conf.go.checks"))
        + _fact(r, "d-att", "alert", "att.title", len(attention), _bullets(r, attention) or r.t("att.none.improve", tag="p", cls="fnote"),
                r.link("#candidate", "att.go.checks") if attention else "")
        + _fact(r, "d-unk", "question", "unk.title", len(unknown), _bullets(r, unknown), r.link("#green", "unk.go"))
        + change_card + "</div>"
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


def _decision(r: _R) -> str:
    tone = _verdict(r)[0]
    improve = r.report["workflow"] == "improve"
    facts = _facts_improve(r) if improve else _facts_audit(r)
    hero = f'<div class="hero">{_identity(r)}{_rail(r)}</div>'
    banner = f'<section class="decision tone-{tone}" aria-labelledby="h-conclusion">{_conclusion(r)}</section>'
    return hero + banner + (_lifecycle(r) if improve else "") + _kpis(r) + facts


# --- "What does green prove?" ------------------------------------------------------------

def _green_audit(r: _R) -> str:
    report = r.report
    rows = "".join(
        _ledger_row(r, pair_of("area." + row["area"]), row["level"], r.p(row["detail"]), row.get("href"), f"scope-{row['area']}", _AREA_ICON.get(row["area"]))
        for row in _scope(report)
    )
    head = (f'<li class="lrow lhead" aria-hidden="true"><span>{r.t("ledger.area")}</span><span>{r.t("ledger.result")}</span>'
            f'<span>{r.t("ledger.detail")}</span><span></span></li>')
    return (
        f'<section id="green" class="sub green" aria-labelledby="h-green">'
        f'<div class="sub-head"><h2 id="h-green"><span class="h-badge">{r.icon("shield")}</span>{r.t("green.title")}</h2>{r.t("green.lead.audit", tag="p", cls="lead")}'
        f'{r.link("#claim", "green.full")}</div>'
        f'<ol class="ledger" {r.attr("aria-label", "scope.title")}>{head}{rows}</ol>'
        f'<div class="ledger-foot">{_legend(r)}{_limitations(r, report["claim_boundary"].get("limitations") or [])}</div></section>'
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
    rows.append(_ledger_row(r, pair_of("area.deploy"), "NOT_EVIDENCED", r.t("scope.preview"), "#claim", icon="cloud"))
    return (
        f'<section id="green" class="sub green" aria-labelledby="h-green">'
        f'<div class="sub-head"><h2 id="h-green"><span class="h-badge">{r.icon("shield")}</span>{r.t("green.title")}</h2>{r.t("green.lead.improve", tag="p", cls="lead")}'
        f'{r.link("#claim", "green.full")}</div>'
        f'<ol class="ledger" {r.attr("aria-label", "qual.title")}>{"".join(rows)}</ol>'
        f'<div class="ledger-foot">{_limitations(r, report["claim_boundary"].get("limitations") or [])}</div></section>'
    )


def _overview(r: _R) -> str:
    improve = r.report["workflow"] == "improve"
    green = _green_improve(r) if improve else _green_audit(r)
    return (f'<section id="overview" class="area area-overview" data-layer="decision" aria-labelledby="h-project">'
            f"{_decision(r)}{green}</section>")


# --- findings ----------------------------------------------------------------------------

def _finding(r: _R, index: int, f: dict, number: int) -> str:
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
    meta_bits = [f'<span class="tag-area">{r.t("cat." + category)}</span>']
    if affected:
        meta_bits.append(r.p(affected))
    meta_bits.append(_basis(r, meta.get("tier")))
    observed = r.p(summary, tag="p") if summary else (r.t("finding.observed.original", tag="p") + f'<p class="original" lang="en">{_e(f["summary"])}</p>')
    other = {k: v for k, v in evidence.items() if not isinstance(v, (list, dict)) and k not in _COUNT_KEYS}
    kv = "".join(f"<dt><code>{_e(k)}</code></dt><dd><code>{_e(v)}</code></dd>" for k, v in other.items())
    evidence_html = ((f'<p class="affected">{r.p(affected)}</p>' if affected else "")
                     + (r.items(listed, kind="code", limit=8) if listed else "") + (f'<dl class="kv">{kv}</dl>' if kv else ""))
    left = [f'<div class="f-block">{r.icon("info", "ic fb-ic")}<div><h4>{r.t("finding.observed")}</h4>{observed}</div></div>']
    if why:
        left.append(f'<div class="f-block">{r.icon("alert", "ic fb-ic")}<div><h4>{r.t("finding.why")}</h4>{r.p(why, tag="p")}</div></div>')
    left.append(f'<div class="f-block" id="{fid}-evidence">{r.icon("doc", "ic fb-ic")}<div><h4>{r.t("finding.evidence")}</h4>'
                f'{evidence_html or r.t("finding.no_items", tag="p", cls="empty")}</div></div>')
    right = []
    if rec:
        rec_pair = _rec_pair(code, rec)
        rec_html = r.p(rec_pair, tag="p") if rec_pair else f'<p lang="en" class="raw-text">{_e(rec)}</p>'
        right.append(f'<div class="f-block f-fix" id="{fid}-fix">{r.icon("wrench", "ic fb-ic")}<div><h4>{r.t("finding.recommendation")}'
                     f'<span class="pill tone-accent">{r.t("proposed.short")}</span></h4>{rec_html}</div></div>')
    if meta.get("close"):
        right.append(f'<div class="f-block f-close">{r.icon("checkc", "ic fb-ic")}<div><h4>{r.t("finding.close")}</h4>{r.p(meta["close"], tag="p")}</div></div>')
    tech = (f'<details class="tech"><summary>{r.t("finding.technical")}</summary><dl class="kv">'
            f'<dt>{r.t("finding.code")}</dt><dd><code>{_e(code)}</code></dd><dt>{r.t("finding.basis")}</dt><dd>{r.tier(meta.get("tier"))}</dd>'
            f'<dt>{r.t("original")}</dt><dd lang="en">{_e(f["summary"])}</dd></dl>'
            f'<p class="tech-label">{r.t("finding.raw")}</p><pre class="code">{_e(json.dumps(evidence, indent=2, ensure_ascii=False))}</pre></details>')
    return (
        f'<details class="finding sev-{_e(severity)}{" compact" if compact else ""}" id="{fid}" data-severity="{_e(severity)}" data-category="{_e(category)}">'
        f'<summary class="f-row" data-layer="decision"><span class="f-num" aria-hidden="true">{number}</span>'
        f'<span class="f-sev">{r.pill(severity, prefix="severity.")}</span>'
        f'<h3 class="f-title" id="{fid}-t">{r.p(_finding_title(f))}</h3>'
        + (r.p(why, cls="f-why") if why and not compact else "")
        + f'<span class="f-meta">{_DOT_SEP.join(meta_bits)}</span>{r.icon("chev", "ic chev")}</summary>'
        f'<div class="f-body"><div class="f-col">{"".join(left)}</div><div class="f-col">{"".join(right)}</div>{tech}</div></details>'
    )


def _donut(counts: dict[str, int]) -> str:
    total = sum(counts.values()) or 1
    circumference, offset, arcs = 2 * 3.14159 * 30, 0.0, []
    for sev in ("high", "medium", "info"):
        if counts[sev]:
            length = circumference * counts[sev] / total
            arcs.append(f'<circle cx="40" cy="40" r="30" class="d-{sev}" stroke-dasharray="{length:.1f} {circumference:.1f}" '
                        f'stroke-dashoffset="{-offset:.1f}" transform="rotate(-90 40 40)"/>')
            offset += length
    return f'<svg class="donut" viewBox="0 0 80 80" aria-hidden="true" focusable="false"><circle cx="40" cy="40" r="30" class="d-track"/>{"".join(arcs)}</svg>'


def _findings_rail(r: _R) -> str:
    report = r.report
    findings = report["findings"]
    counts = _severity_counts(findings)
    legend = "".join(f'<li class="lg-{s}"><span class="sw" aria-hidden="true"></span>{r.t("severity." + s)}<b>{counts[s]}</b></li>' for s in ("high", "medium", "info"))
    by_area: dict[str, int] = {}
    for f in findings:
        by_area[_category(f["code"])] = by_area.get(_category(f["code"]), 0) + 1
    top = max(by_area.values()) if by_area else 1
    areas = "".join(f'<li><button type="button" class="area-pick" data-cat="{_e(c)}" {r.attr("aria-label", "frail.filter", area=_label("cat.", c))}>{r.t("cat." + c)}</button>{_bar(n / top, "accent")}<b>{n}</b></li>'
                    for c, n in sorted(by_area.items(), key=lambda kv: (-kv[1], kv[0])))
    return (f'<aside class="f-rail" {r.attr("aria-label", "frail.label")}>'
            f'<section class="rail-card"><h3>{r.t("frail.summary")}</h3><div class="donut-row"><div class="donut-wrap">{_donut(counts)}'
            f'<span class="donut-n"><b>{len(findings)}</b>{r.t("att.count.word", n=len(findings))}</span></div><ul class="sev-legend">{legend}</ul></div></section>'
            f'<section class="rail-card"><h3>{r.t("frail.areas")}</h3><ul class="area-bars">{areas}</ul></section>'
            f'<section class="rail-card"><h3>{r.t("improve.title")}</h3>{r.t("card.imp.count", tag="p", cls="fnote", n=len(report.get("recommendations") or []))}'
            f'{r.link("#improvements", "card.imp.go")}</section></aside>')


def _findings_area(r: _R) -> str:
    report = r.report
    findings = report["findings"]
    counts = _severity_counts(findings)
    head = (f'<div class="area-head"><p class="eyebrow">{r.icon("alert", "ic")}{r.t("findings.eyebrow")}</p><h2 id="h-findings">{r.t("findings.title")}</h2>'
            + (f'<p class="lead"><span class="chips">{_sev_chips(r, counts)}</span> {r.t("findings.lead")}</p>'
               if findings else r.t("findings.none", tag="p", cls="lead")) + "</div>")
    if not findings:
        return f'<section id="findings" class="area" aria-labelledby="h-findings">{head}</section>'
    categories = sorted({_category(f["code"]) for f in findings})
    sev_options = "".join(f'<option value="{s}"{r.attr_text("severity." + s)}>{_e(r.s("severity." + s))}</option>' for s in ("high", "medium", "info") if counts[s])
    cat_options = "".join(f'<option value="{c}"{r.attr_text("cat." + c)}>{_e(r.s("cat." + c))}</option>' for c in categories)
    empty_attrs = ' id="findings-empty" hidden'
    filters = (
        f'<div class="filters" role="search"><label class="search-box">{r.icon("search", "ic")}<span class="sr-only">{r.t("findings.filter.search")}</span>'
        f'<input id="q" class="search" type="search" {r.attr("placeholder", "findings.filter.search")}></label>'
        f'<label for="cat" class="fl">{r.t("findings.filter.category")}</label>'
        f'<select id="cat" class="select"><option value=""{r.attr_text("findings.filter.all")}>{_e(r.s("findings.filter.all"))}</option>{cat_options}</select>'
        f'<label for="sev" class="fl">{r.t("findings.filter.severity")}</label>'
        f'<select id="sev" class="select"><option value=""{r.attr_text("findings.filter.all")}>{_e(r.s("findings.filter.all"))}</option>{sev_options}</select>'
        f'<button type="button" id="clear-filters" class="btn ghost small" hidden>{r.t("findings.filter.clear")}</button>'
        f'<span id="findings-count" class="muted" aria-live="polite"></span></div>'
        f'{r.t("findings.filter.empty", tag="p", cls="empty", attrs=empty_attrs)}'
    ) if len(findings) > 3 else ""
    cards = "".join(_finding(r, i, f, n) for n, (i, f) in enumerate(_sorted_findings(findings), start=1))
    return (f'<section id="findings" class="area" aria-labelledby="h-findings">{head}<div class="with-rail"><div class="main-col">{filters}'
            f'<div class="finding-list">{cards}</div></div>{_findings_rail(r)}</div></section>')


# --- improvements: a prioritized plan --------------------------------------------------------

def _improvements_area(r: _R) -> str:
    report = r.report
    recs = report.get("recommendations") or []
    head = (f'<div class="area-head"><p class="eyebrow">{r.icon("bulb", "ic")}{r.t("improve.eyebrow")}</p><h2 id="h-improvements">{r.t("improve.title")}</h2>'
            f'{r.t("improve.lead", tag="p", cls="lead")}</div>')
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
    out, number = [], 0
    group_icon = {"first": "arrow-up", "high": "alert", "medium": "bars", "info": "ring"}
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
        out.append(f'<section class="rec-group g-{group}" aria-labelledby="h-rec-{group}"><h3 id="h-rec-{group}">{r.icon(group_icon[group], "ic")}{r.t("improve.group." + group)}'
                   f'<span class="count">{len(items)}</span></h3>{note}<ol class="rec-list">{"".join(rows)}</ol></section>')
    return f'<section id="improvements" class="area" data-layer="decision" aria-labelledby="h-improvements">{head}{"".join(out)}</section>'


# --- evidence snapshot -----------------------------------------------------------------------

def _tile(r: _R, domain: str, level: str, value: str, label: str, sub: str = "", change: str = "", tone: str | None = None, side: str = "") -> str:
    tone = tone or _LEVEL_TONE[level]
    return (f'<div class="tile tone-{tone}"><div class="tile-main"><p class="t-domain">{_glyph(r, level)}{r.t("metrics.group." + domain)}</p>'
            f'<p class="t-value">{value}</p><p class="t-label">{label}</p>{sub}{change}</div>{side}</div>')


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
    if invocations and passed is not None:
        failing = (_metric(main, "failed") or 0) + (_metric(main, "errors") or 0) + (_metric(main, "collection_errors") or 0)
        skipped = _metric(main, "skipped") or 0
        sub = (r.t("snap.failing", tag="p", cls="t-sub bad", n=failing) if failing else "") + (r.t("snap.skipped", tag="p", cls="t-sub", n=skipped) if skipped else "")
        tiles.append(_tile(r, "execution", "FAILED" if failing else "EXECUTED", f'{num(main, "passed")}<span class="of">/</span>{num(main, "test_invocations")}',
                           r.t("snap.passed"), sub + f'<div class="t-bar">{_bar(passed / invocations, "fail" if failing else "pass")}</div>', change("passed")))
    line = _metric(main, "line_coverage")
    if line is not None:
        branch = _metric(main, "branch_coverage")
        sub = f'<p class="t-sub">{r.t("snap.branches", value=_num(branch, "%", 1))}</p>' if branch is not None else ""
        tiles.append(_tile(r, "coverage", "MEASURED", num(main, "line_coverage"), r.t("snap.lines"), sub, change("line_coverage"), side=_ring(line, "info")))
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
    return (f'<section id="evidence" class="area" aria-labelledby="h-evidence"><div class="area-head"><p class="eyebrow">{r.icon("doc", "ic")}{r.t("evidence.eyebrow")}</p>'
            f'<h2 id="h-evidence">{r.t("evidence.title")}</h2>{r.t("evidence.lead", tag="p", cls="lead")}</div>{_snapshot(r)}'
            f'<div class="sub-head panels-head"><h3>{r.t("ev.records")}</h3>{r.t("ev.records.lead", tag="p", cls="lead")}</div>'
            f'<div class="panels-d numbered">{panels}</div></section>')


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
    head = (f'<div class="area-head"><p class="eyebrow">{r.icon("shield", "ic")}{r.t("cand.eyebrow")}</p><h2 id="h-candidate">{r.t("cand.title")}</h2>'
            f'{r.t("cand.lead", tag="p", cls="lead")}</div>')
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
    for name, key, icon, tone in (("observed", "claim.observed", "checkc", "pass"), ("not_evidenced", "claim.not", "question", "warn"),
                                  ("limitations", "claim.limits", "info", "info")):
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
            f'<details class="claim-g cg-{name} tone-{tone}"{" open" if len(values) <= 6 else ""}><summary><span class="cg-title">{r.icon(icon, "ic lv")}{r.t(key)}<span class="count">{len(values)}</span></span>'
            f'<ul class="cd-index">{index}</ul>{r.icon("chev", "ic chev")}</summary><div class="cg-body">{body or r.t("none", tag="p", cls="empty")}</div></details>'
        )
    return (f'<section id="claim" class="sub" aria-labelledby="h-claim">{_section_head(r, "claim", "claim.title", "claim.lead")}'
            f'<div class="claim-groups">{"".join(groups)}</div></section>')


def _artifacts_table(r: _R) -> str:
    """Files and artifacts this report rests on, as recorded; nothing is listed that the report does not reference."""
    report = r.report
    rows = []
    for key, state in _states(report):
        for a in state.get("artifacts", []):
            name = a["artifact"] or r.s("art.not_built")
            rows.append((r.t("arts.wheel", kind=a["kind"]), f"<code>{_e(name)}</code>", f'<code title="{_e(a["sha256"] or "")}">{_e((a["sha256"] or "—")[:16])}</code>', r.pill(a["status"])))
        for c in state.get("coverage") or []:
            rows.append((r.t("arts.coverage"), f'<code>{_e(c.get("tool") or "unknown")}</code>', f'<code class="wrap">{_e(c.get("source") or "—")}</code>',
                         r.pill("FAIL" if c.get("error") else "PASS")))
    prov = report.get("provenance") or {}
    if prov.get("trace"):
        rows.append((r.t("arts.trace"), f'<code class="wrap">{_e(Path(prov["trace"]).name)}</code>', f'<code class="wrap">{_e(prov["trace"])}</code>', ""))
    if report.get("report_path"):
        rows.append((r.t("arts.page"), f'<code>{_e(Path(report["report_path"]).name)}</code>', f'<code class="wrap">{_e(report["report_path"])}</code>', ""))
    if not rows:
        return ""
    body = "".join(f'<tr><th scope="row">{a}</th><td {r.label_attr("arts.name")}>{b}</td><td {r.label_attr("arts.identity")}>{c}</td><td {r.label_attr("arts.status")}>{d}</td></tr>'
                   for a, b, c, d in rows)
    return (f'<div class="table-wrap arts"><table class="responsive"><caption>{r.t("arts.title")}</caption><thead><tr><th scope="col">{r.t("arts.kind")}</th>'
            f'<th scope="col">{r.t("arts.name")}</th><th scope="col">{r.t("arts.identity")}</th><th scope="col">{r.t("arts.status")}</th></tr></thead><tbody>{body}</tbody></table></div>')


def _run_command(report: dict) -> str:
    for _key_, state in _states(report):
        for run in state.get("runs", []):
            if run["mode"] != "report" and run.get("command"):
                return " ".join(run["command"]) if isinstance(run["command"], list) else str(run["command"])
    return ""


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
        ("tag", "prov.version", identity),
        ("commit", "prov.revision", f'<code title="{_e(project.get("revision") or "")}">{_e((project.get("revision") or "—")[:12])}</code>'),
        ("db", "prov.state", r.t("header.dirty" if project.get("dirty") else "header.clean")),
        ("play", "prov.mode", mode),
        ("users", "prov.adapters", " ".join(f"<code>{_e(a)}</code>" for a in runners) or "—"),
        ("calendar", "prov.generated", r.p(_when(report["generated_at"]), tag="time", attrs=f' datetime="{_e(report["generated_at"])}" data-local')),
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
    pairs = "".join(f'<div>{r.icon(icon, "ic p-ic")}<dt>{r.t(k)}</dt><dd>{v}</dd></div>' for icon, k, v in compact)
    more = "".join(f"<dt>{r.t(k)}</dt><dd>{v}</dd>" for k, v in full)
    command = _run_command(report)
    cmd = (f'<div class="cmd"><div class="cmd-head">{r.icon("terminal", "ic")}{r.t("prov.cmd")}{_copy(r)}</div><pre class="code"><code>{_e(command)}</code></pre></div>'
           if command else "")
    return (f'<section id="provenance" class="sub" aria-labelledby="h-provenance">{_section_head(r, "provenance", "prov.title")}'
            f'{warning}<dl class="prov">{pairs}</dl>{cmd}{_artifacts_table(r)}<details class="more"><summary>{r.t("prov.more")}</summary><dl class="kv">{more}</dl></details></section>')


def _raw(r: _R) -> str:
    data = json.dumps(r.report, indent=2, ensure_ascii=False, default=str)
    body = f'<div class="cmd"><div class="cmd-head">{r.t("raw.summary")}{_copy(r)}</div><pre class="code raw-json">{_e(data)}</pre></div>'
    return _panel(r, "raw", "raw.title", r.t("raw.summary"), body, "raw.lead")


def _details_area(r: _R) -> str:
    return (f'<section id="details" class="area area-tech" aria-labelledby="h-details"><div class="area-head"><p class="eyebrow">{r.icon("code", "ic")}{r.t("details.eyebrow")}</p>'
            f'<h2 id="h-details">{r.t("details.title")}</h2>'
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
    # Only informational findings: say so without implying the rest is fine; unproven areas stay in the reason.
    reason = pair_of("verdict.info.reason", n=counts["info"])
    unproven = len(report["claim_boundary"].get("not_evidenced") or [])
    if unproven:
        reason = _join([reason, pair_of("verdict.unproven", n=unproven)], (" ", " "))
    return "neutral", "info", pair_of("verdict.info"), reason


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
    "arrow-up": '<path d="M8 13V3.5M4.5 7L8 3.5 11.5 7" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
    "chev": '<path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "chev-r": '<path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "copy": '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M3.5 10.5v-7a1 1 0 011-1h7" fill="none" stroke="currentColor" stroke-width="1.4"/>',
    "moon": '<path d="M13 9.5A5.5 5.5 0 016.5 3a5.5 5.5 0 106.5 6.5z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>',
    "sun": '<circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1.5v1.6M8 12.9v1.6M1.5 8h1.6M12.9 8h1.6M3.4 3.4l1.1 1.1M11.5 11.5l1.1 1.1M3.4 12.6l1.1-1.1M11.5 4.5l1.1-1.1" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
    "globe": '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2 8h12M8 2c1.8 1.7 2.6 3.7 2.6 6S9.8 12.3 8 14C6.2 12.3 5.4 10.3 5.4 8S6.2 3.7 8 2z" fill="none" stroke="currentColor" stroke-width="1.2"/>',
    "home": '<path d="M2.5 7.5L8 3l5.5 4.5V13a.5.5 0 01-.5.5H9.5V10h-3v3.5H3a.5.5 0 01-.5-.5z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
    "doc": '<path d="M4 1.8h5.2L12 4.6V14H4z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M9 2v3h3M6 8h4M6 10.5h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
    "bulb": '<path d="M5.5 10.5a4.5 4.5 0 115 0V12h-5z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M6 14h4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
    "code": '<path d="M5.5 4.5L2 8l3.5 3.5M10.5 4.5L14 8l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
    "shield": '<path d="M8 1.8l5 2v4.1c0 3.1-2.1 5.4-5 6.3-2.9-.9-5-3.2-5-6.3V3.8z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
    "calendar": '<rect x="2" y="3" width="12" height="11" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M2 6.5h12M5 1.8v2.4M11 1.8v2.4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
    "commit": '<circle cx="8" cy="8" r="2.6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1.5 8h3.9M10.6 8h3.9" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
    "branch": '<circle cx="4.5" cy="3.5" r="1.6" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="4.5" cy="12.5" r="1.6" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="11.5" cy="5.5" r="1.6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M4.5 5.1v5.8M11.5 7.1c0 2.4-3.2 2.2-6.4 4" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "db": '<ellipse cx="8" cy="3.8" rx="5" ry="1.9" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M3 3.8v8.4c0 1 2.2 1.9 5 1.9s5-.9 5-1.9V3.8M3 8c0 1 2.2 1.9 5 1.9s5-.9 5-1.9" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    "layers": '<path d="M8 2l6 3-6 3-6-3zM2 8l6 3 6-3M2 11l6 3 6-3" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>',
    "play": '<circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M6.6 5.4l4 2.6-4 2.6z" fill="currentColor"/>',
    "bars": '<path d="M3 13.5V9M6.3 13.5V5.5M9.7 13.5V7.5M13 13.5V2.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    "delta": '<path d="M8 2.5l5.8 10.5H2.2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>',
    "flask": '<path d="M6 1.8h4M6.6 1.8v4.3L3 13.2a.8.8 0 00.7 1.1h8.6a.8.8 0 00.7-1.1L9.4 6.1V1.8" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>',
    "box": '<path d="M8 1.8l5.5 2.9v6.6L8 14.2l-5.5-2.9V4.7z M2.5 4.7L8 7.6l5.5-2.9M8 7.6v6.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>',
    "cloud": '<path d="M4.5 12.5h7a2.8 2.8 0 00.4-5.6 4 4 0 00-7.7-.6A3.1 3.1 0 004.5 12.5z" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>',
    "laptop": '<rect x="3" y="3" width="10" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M1.5 12.5h13" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>',
    "shuffle": '<path d="M2 4.5h2.5l6 7H14M2 11.5h2.5l1.6-1.9M10 6.4l.5-.6.5-1.3H14M12 2.5l2 2-2 2M12 9.5l2 2-2 2" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
    "search": '<circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M10.4 10.4L14 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    "wrench": '<path d="M10.5 2.5a3 3 0 00-3.2 4L2.8 11a1.4 1.4 0 002 2l4.5-4.5a3 3 0 004-3.2l-1.8 1.8-1.7-.4-.4-1.7z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/>',
    "terminal": '<rect x="1.8" y="2.8" width="12.4" height="10.4" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M4.5 6.5L6.5 8l-2 1.5M8 10h3" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>',
    "tag": '<path d="M2 2.5h5.5l6.5 6.5-5 5L2.5 7.5z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><circle cx="5" cy="5.5" r="1" fill="currentColor"/>',
    "users": '<circle cx="6" cy="5.5" r="2.4" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M1.8 13.5c.5-2.4 2.2-3.6 4.2-3.6s3.7 1.2 4.2 3.6M10.6 3.4a2.3 2.3 0 010 4.3M12 9.9c1.3.5 2 1.6 2.3 3.6" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>',
}


def _sprite() -> str:
    symbols = "".join(f'<symbol id="i-{name}" viewBox="0 0 16 16">{body}</symbol>' for name, body in _ICONS.items())
    return f'<svg class="sprite" aria-hidden="true" focusable="false">{symbols}</svg>'


_LOGO = ('<svg class="logo" viewBox="0 0 32 32" aria-hidden="true" focusable="false"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset="0" stop-color="var(--logo-a)"/><stop offset="1" stop-color="var(--logo-b)"/></linearGradient></defs>'
         '<rect x="1" y="1" width="30" height="30" rx="9" fill="url(#lg)"/>'
         '<path d="M9.5 22.5L16 8.5l6.5 14M12.3 17.2h7.4" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>')

_NAV_ICON = {"overview": "home", "findings": "alert", "improvements": "bulb", "evidence": "doc", "details": "code",
             "candidate": "shield", "delta": "delta"}


def _nav(r: _R) -> str:
    report = r.report
    if report["workflow"] == "improve":
        changes = len((report.get("change_set") or {}).get("changes") or [])
        areas = [("overview", "nav.overview", [("green", "green.title")], ""),
                 ("candidate", "nav.candidate", [("changes", "changes.title")], str(changes) if changes else ""),
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
        f'<li data-area="{aid}"><a class="nav-area" href="#{aid}">{r.icon(_NAV_ICON[aid], "ic nav-ic")}<span class="nav-label">{r.t(key)}</span>'
        + (f'<span class="badge">{badge}</span>' if badge else "") + "</a>"
        + ('<ul class="nav-sub">' + "".join(f'<li><a href="#{sid}">{r.t(skey)}</a></li>' for sid, skey in subs) + "</ul>" if subs else "")
        + "</li>"
        for aid, key, subs, badge in areas
    )
    return f'<nav class="sidenav" {r.attr("aria-label", "nav.label")}><ul>{items}</ul></nav>'


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
    tone, icon, headline, _reason = _verdict(r)
    sidebar = (
        f'<aside class="sidebar"><a class="brand" href="#overview">{_LOGO}<span class="brand-text"><span class="brand-name">Assertiva</span>'
        f'<span class="brand-product">{r.t("brand.product")}</span></span></a>{_nav(r)}'
        f'<div class="about"><p class="about-title">{r.icon("info", "ic")}{r.t("about.title")}</p>{r.t("about.body", tag="p")}</div>'
        f'<p class="side-version">Assertiva {_e(rendered_by)}<br>{r.t("brand.product")}</p></aside>'
    )
    header = (
        f'<header class="topbar"><div class="crumbs"><a class="brand-mini" href="#overview">{_LOGO}</a>{r.icon("home", "ic")}'
        f'<span class="crumb">{r.t("brand.product")}</span>{r.icon("chev-r", "ic sep")}<span class="crumb cur">{_e(project.get("name") or "project")}</span></div>'
        f'<div class="controls"><span class="status-pill tone-{tone}">{r.icon(icon, "ic")}{r.p(headline)}</span>'
        f'<label class="lang">{r.icon("globe")}<span class="sr-only">{r.t("lang.label")}</span>'
        f'<select id="lang" class="select" {r.attr("aria-label", "lang.label")}><option value="en" lang="en"{selected[1]}>English</option>'
        f'<option value="pt-BR" lang="pt-BR"{selected[0]}>Português (Brasil)</option></select></label>'
        f'<button id="theme" type="button" class="toggle" aria-pressed="false" {r.attr("aria-label", "theme.label")}>'
        f'<span class="tg-sun">{r.icon("sun")}</span><span class="tg-moon">{r.icon("moon")}</span><span class="toggle-text sr-only">{r.t("theme.toggle")}</span></button>'
        f"</div></header>"
    )
    skip = r.t("skip", tag="a", cls="skip", attrs=' href="#main"')
    footer = f'<footer class="footer">{r.t("footer", tag="p", v=REPORT_VERSION, a=rendered_by)}</footer>'
    data = json.dumps({"pt-BR": dict(sorted(r.used.items())), "js": _JS_STRINGS}, ensure_ascii=False).replace("</", "<\\/")
    return (
        f'<!doctype html>\n<html lang="{lang}" data-rendered="{lang}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark">'
        f'<meta name="generator" content="Assertiva {_e(rendered_by)}">'
        f"{title}<style>{_CSS}</style></head>\n<body>\n{skip}\n{_sprite()}\n"
        f'<div class="app">{sidebar}<div class="page">{header}<main id="main" tabindex="-1">{main}</main>{footer}</div></div>\n'
        '<div id="live" class="sr-only" aria-live="polite"></div>\n'
        f'<script type="application/json" id="i18n">{data}</script>\n<script>{_JS}</script>\n</body></html>\n'
    )


_CSS = """
:root{color-scheme:light;
--bg:#f3f5fa;--side:#ffffff;--surface:#ffffff;--surface-2:#f7f8fc;--sunk:#eef1f7;--rule:#e2e6ef;--rule-strong:#ccd3e0;
--ink:#0f172a;--ink-2:#334155;--muted:#5b6578;--faint:#8a93a6;
--accent:#3b5bdb;--accent-2:#6d4aff;--accent-soft:#e9edff;--on-tone:#ffffff;--logo-a:#4f6bff;--logo-b:#7b4dff;
--pass:#15803d;--fail:#c02626;--warn:#b45309;--unknown:#5f6b7f;--info:#1d63c9;
--glow:rgba(59,91,219,.07);--shadow:0 1px 2px rgba(15,23,42,.05);--lift:0 10px 30px -18px rgba(15,23,42,.35);
--r-sm:7px;--r:12px;--r-lg:16px;
--sans:ui-sans-serif,system-ui,-apple-system,"Segoe UI Variable Text","Segoe UI",Inter,Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:ui-monospace,SFMono-Regular,"SF Mono","Cascadia Mono",Menlo,Consolas,"Liberation Mono",monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;
--bg:#080d1a;--side:#0a1020;--surface:#0e1628;--surface-2:#111b31;--sunk:#0b1324;--rule:rgba(148,163,184,.13);--rule-strong:rgba(148,163,184,.24);
--ink:#e9eef8;--ink-2:#c4ccdc;--muted:#8f9ab0;--faint:#68738a;
--accent:#7b93ff;--accent-2:#9b7bff;--accent-soft:rgba(91,124,250,.16);--on-tone:#08101f;--logo-a:#4f6bff;--logo-b:#8a5cff;
--pass:#3ddc97;--fail:#ff7b7b;--warn:#f6b44b;--unknown:#a3adbf;--info:#6cb2ff;
--glow:rgba(91,124,250,.20);--shadow:0 1px 2px rgba(0,0,0,.4);--lift:0 18px 40px -22px rgba(0,0,0,.9)}}
:root[data-theme="dark"]{color-scheme:dark;
--bg:#080d1a;--side:#0a1020;--surface:#0e1628;--surface-2:#111b31;--sunk:#0b1324;--rule:rgba(148,163,184,.13);--rule-strong:rgba(148,163,184,.24);
--ink:#e9eef8;--ink-2:#c4ccdc;--muted:#8f9ab0;--faint:#68738a;
--accent:#7b93ff;--accent-2:#9b7bff;--accent-soft:rgba(91,124,250,.16);--on-tone:#08101f;--logo-a:#4f6bff;--logo-b:#8a5cff;
--pass:#3ddc97;--fail:#ff7b7b;--warn:#f6b44b;--unknown:#a3adbf;--info:#6cb2ff;
--glow:rgba(91,124,250,.20);--shadow:0 1px 2px rgba(0,0,0,.4);--lift:0 18px 40px -22px rgba(0,0,0,.9)}
*,*::before,*::after{box-sizing:border-box}
html{scroll-padding-top:76px;-webkit-text-size-adjust:100%}
@media (prefers-reduced-motion: no-preference){html{scroll-behavior:smooth}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
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
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:5px}
.skip{position:absolute;left:16px;top:-60px;background:var(--surface);color:var(--ink);padding:8px 14px;border-radius:var(--r-sm);z-index:40;box-shadow:var(--lift)}
.skip:focus{top:10px}
.quiet,.muted{color:var(--muted)}
.empty{color:var(--muted);margin:6px 0}
.tone-pass{--tone:var(--pass)}.tone-fail{--tone:var(--fail)}.tone-warn{--tone:var(--warn)}.tone-blocked{--tone:var(--warn)}
.tone-unknown{--tone:var(--unknown)}.tone-not_run{--tone:var(--faint)}.tone-neutral{--tone:var(--muted)}.tone-accent{--tone:var(--accent)}
.tone-info{--tone:var(--info)}.tone-muted{--tone:var(--faint)}
/* app shell */
.app{display:grid;grid-template-columns:252px minmax(0,1fr);min-height:100vh}
.sidebar{position:sticky;top:0;height:100vh;display:flex;flex-direction:column;gap:18px;padding:22px 16px 18px;background:var(--side);border-right:1px solid var(--rule);overflow:auto}
.brand{display:flex;align-items:center;gap:12px;color:var(--ink);text-decoration:none;padding:0 8px}
.logo{width:34px;height:34px;flex:none}
.brand-text{display:flex;flex-direction:column;line-height:1.15}
.brand-name{font-weight:720;letter-spacing:-.015em;font-size:1.06rem}
.brand-product{color:var(--muted);font-size:.8rem}
.sidenav ul{list-style:none;margin:0;padding:0}
.sidenav>ul{display:grid;gap:4px}
.nav-area{display:flex;align-items:center;gap:12px;color:var(--ink-2);text-decoration:none;padding:10px 12px;border-radius:10px;font-weight:560;transition:background .15s ease,color .15s ease}
.nav-ic{width:18px;height:18px;color:var(--muted)}
.nav-label{flex:1}
.nav-area:hover{background:var(--sunk);color:var(--ink)}
li.active>.nav-area{color:var(--ink);background:linear-gradient(90deg,var(--accent-soft),transparent);box-shadow:inset 3px 0 0 var(--accent)}
li.active>.nav-area .nav-ic{color:var(--accent)}
.badge{font-size:.74rem;font-weight:700;color:var(--ink-2);background:var(--sunk);border:1px solid var(--rule);border-radius:999px;padding:0 8px;line-height:1.7;font-variant-numeric:tabular-nums}
.nav-sub{display:none;margin:2px 0 6px 42px!important;border-left:1px solid var(--rule)}
li.active>.nav-sub{display:block}
.nav-sub a{display:block;color:var(--muted);text-decoration:none;font-size:.83rem;padding:3px 10px}
.nav-sub a:hover{color:var(--ink)}
.about{margin-top:auto;padding:14px;border:1px solid var(--rule);border-radius:var(--r);background:var(--surface-2);font-size:.82rem;color:var(--muted)}
.about-title{display:flex;align-items:center;gap:7px;font-weight:650;color:var(--ink-2);margin-bottom:6px}
.side-version{font-size:.78rem;color:var(--faint);padding:0 8px;line-height:1.45}
.page{min-width:0;display:flex;flex-direction:column}
.topbar{position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;gap:16px;height:60px;padding:0 32px;background:color-mix(in srgb,var(--bg) 86%,transparent);backdrop-filter:saturate(1.3) blur(12px);border-bottom:1px solid var(--rule)}
.crumbs{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:.875rem;min-width:0}
.crumbs .sep{width:12px;height:12px;color:var(--faint)}
.crumb.cur{color:var(--ink);font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.brand-mini{display:none}
.controls{display:flex;align-items:center;gap:10px}
.status-pill{display:inline-flex;align-items:center;gap:7px;font-size:.84rem;font-weight:620;color:var(--tone);padding:6px 12px;border-radius:999px;border:1px solid color-mix(in srgb,var(--tone) 40%,transparent);background:color-mix(in srgb,var(--tone) 12%,transparent);white-space:nowrap}
.status-pill .ic{width:15px;height:15px}
.lang{display:flex;align-items:center;gap:6px;color:var(--muted)}
.select,.search{font:inherit;font-size:.875rem;color:var(--ink);background:var(--surface);border:1px solid var(--rule-strong);border-radius:9px;padding:7px 11px;min-height:36px}
.select{appearance:none;padding-right:32px;background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%);background-position:calc(100% - 16px) 52%,calc(100% - 11px) 52%;background-size:5px 5px;background-repeat:no-repeat}
.select:hover,.search:hover{border-color:var(--faint)}
.toggle{display:inline-flex;align-items:center;gap:2px;padding:3px;border-radius:999px;border:1px solid var(--rule-strong);background:var(--surface);cursor:pointer;min-height:36px}
.toggle>span{display:grid;place-items:center;width:28px;height:28px;border-radius:999px;color:var(--muted)}
.toggle[aria-pressed="false"] .tg-sun,.toggle[aria-pressed="true"] .tg-moon{background:var(--accent);color:var(--on-tone)}
main{min-width:0;width:100%;max-width:1340px;margin:0 auto;padding:0 32px 96px}
main:focus{outline:none}
/* cards */
.card,.kpi,.fact,.card-imp,.life,.ledger,.finding,.rec-list,.tile,.panels-d,.prov,.claim-g,.rail-card,.pillar,.drows,.dcounts,.changes,.table-wrap,.filters,.decision,.rail{border-radius:var(--r-lg)}
/* hero */
.area.area-overview{padding-top:30px;margin-top:0}
.hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,380px);gap:24px;align-items:stretch;margin-bottom:20px;position:relative}
.hero::before{content:"";position:absolute;inset:-30px -32px auto -32px;height:260px;background:radial-gradient(600px 220px at 70% 0%,var(--glow),transparent 70%);pointer-events:none;z-index:-1}
.ident{display:flex;flex-direction:column;justify-content:flex-start;padding-top:22px;min-width:0}
.eyebrow{display:flex;align-items:center;gap:7px;font-size:.8125rem;font-weight:640;color:var(--accent);margin-bottom:8px}
.eyebrow .ic{width:15px;height:15px}
h1{font-size:clamp(2rem,3.2vw,2.75rem);line-height:1.05;letter-spacing:-.03em;margin:0 0 8px;font-weight:760;overflow-wrap:anywhere}
.ident-lead{color:var(--muted);font-size:.98rem;margin-bottom:16px;max-width:70ch}
.hero-art{display:none}
@media (min-width:1321px){.ident{position:relative;padding-right:130px}.hero-art{display:grid;place-items:center;position:absolute;right:10px;top:18px;width:92px;height:92px;border-radius:26px;color:#fff;
background:linear-gradient(150deg,color-mix(in srgb,var(--logo-a) 88%,#fff),var(--logo-b));box-shadow:0 26px 50px -22px var(--logo-b),inset 0 1px 0 rgba(255,255,255,.4),inset 0 -10px 22px rgba(10,10,60,.25);
transform:perspective(500px) rotateY(-16deg) rotateX(8deg)}.hero-art .ic{width:42px;height:42px;filter:drop-shadow(0 3px 6px rgba(0,0,40,.35))}}
.idline{display:flex;flex-wrap:wrap;gap:12px 28px;margin:0;font-size:.85rem}
.idline div{display:grid;grid-template-columns:auto auto;grid-template-rows:auto auto;column-gap:9px;align-items:center}
.idline .m-ic{grid-row:1/3;width:18px;height:18px;color:var(--muted)}
.idline dt{color:var(--faint);font-size:.76rem}
.idline dd{margin:0;color:var(--ink);font-weight:560}
.idline code{font-size:.82rem}
.ws.dirty{color:var(--warn)}
.arrow{color:var(--faint);margin:0 6px;font-weight:400}
.rail{display:flex;flex-direction:column;align-items:flex-start;padding:22px 24px;background:linear-gradient(160deg,color-mix(in srgb,var(--accent) 14%,var(--surface)),var(--surface) 65%);border:1px solid color-mix(in srgb,var(--accent) 34%,var(--rule));box-shadow:var(--lift)}
.rail-label{display:flex;align-items:center;gap:8px;font-size:.84rem;font-weight:680;color:var(--accent);margin:0 0 10px}
.rail-label .ic{width:22px;height:22px;padding:4px;border-radius:7px;background:var(--accent);color:var(--on-tone)}
.rail-act{font-size:1.15rem;line-height:1.35;font-weight:680;letter-spacing:-.012em}
.rail-act.quiet{font-size:1rem;font-weight:520;color:var(--ink-2)}
.rail-dl{margin:12px 0 0;display:grid;gap:9px;font-size:.875rem}
.rail-dl dt{font-size:.76rem;color:var(--muted);font-weight:620}
.rail-dl dd{margin:2px 0 0;color:var(--ink-2)}
.rail-dl a{color:var(--ink);font-weight:580;margin-right:6px}
.rail-list{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:6px;font-size:.9rem}
.rail-list li{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.rail-list a{color:var(--ink);font-weight:580}
.rail-note{font-size:.84rem;color:var(--muted);margin-top:10px}
.rail-foot{font-size:.76rem;color:var(--muted);margin-top:auto;padding-top:14px}
.btn{display:inline-flex;align-items:center;gap:8px;margin-top:16px;font-size:.875rem;font-weight:650;color:#fff;background:linear-gradient(135deg,var(--accent),var(--accent-2));border-radius:10px;padding:9px 15px;text-decoration:none;border:0;font-family:inherit;cursor:pointer;box-shadow:0 8px 20px -10px var(--accent)}
.btn .ic{width:14px;height:14px;transition:transform .15s ease}
.btn:hover .ic{transform:translateX(2px)}
.btn.ghost{background:transparent;color:var(--accent);border:1px solid color-mix(in srgb,var(--accent) 45%,transparent);box-shadow:none}
.btn.small{margin-top:0;padding:6px 11px;font-size:.8125rem}
/* conclusion banner */
.decision{display:block;position:relative;margin-bottom:18px;background:linear-gradient(120deg,color-mix(in srgb,var(--tone,var(--muted)) 15%,var(--surface)),var(--surface) 58%);border:1px solid color-mix(in srgb,var(--tone,var(--muted)) 38%,var(--rule));box-shadow:var(--lift);overflow:hidden}
.decision::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--tone,var(--muted))}
.d-main{display:flex;gap:22px;align-items:center;padding:24px 28px 24px 30px}
.c-badge{display:grid;place-items:center;flex:none;width:68px;height:68px;border-radius:20px;color:var(--tone);background:color-mix(in srgb,var(--tone) 16%,transparent);border:1px solid color-mix(in srgb,var(--tone) 40%,transparent)}
.c-badge .ic{width:34px;height:34px}
.c-body{min-width:0}
.c-label{font-size:.8rem;color:var(--muted);font-weight:600;margin-bottom:2px}
.c-headline{display:flex;align-items:center;gap:10px;font-size:clamp(1.55rem,2.4vw,2.05rem);line-height:1.15;font-weight:740;letter-spacing:-.022em}
.c-ic{display:none}
.c-reason{font-size:1rem;color:var(--ink-2);margin-top:8px;max-width:72ch}
.c-chips{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:12px}
.c-total{font-size:1rem;font-weight:680;margin-right:2px}
.c-more{font-size:.85rem;font-weight:600;margin-left:4px}
.chip{display:inline-flex;align-items:baseline;gap:5px;font-size:.84rem;padding:3px 11px;border-radius:999px;background:var(--sunk);color:var(--ink-2);border:1px solid var(--rule)}
.chip b{font-variant-numeric:tabular-nums;font-weight:740;color:var(--ink)}
.chip.sev-high{background:color-mix(in srgb,var(--fail) 13%,transparent);border-color:color-mix(in srgb,var(--fail) 38%,transparent)}.chip.sev-high b{color:var(--fail)}
.chip.sev-medium{background:color-mix(in srgb,var(--warn) 13%,transparent);border-color:color-mix(in srgb,var(--warn) 38%,transparent)}.chip.sev-medium b{color:var(--warn)}
.chip.sev-pass{background:color-mix(in srgb,var(--pass) 13%,transparent);border-color:color-mix(in srgb,var(--pass) 38%,transparent)}.chip.sev-pass b{color:var(--pass)}
.chip.zero b{color:var(--faint)}
.c-scope{display:flex;align-items:center;gap:8px;margin-top:12px;font-size:.9rem;color:var(--ink-2)}
.c-scope .ic{color:var(--pass)}
.c-scope.mode-hollow .ic,.c-scope.mode-half .ic{color:var(--info)}
/* lifecycle */
.life{padding:16px 22px;margin-bottom:18px;background:var(--surface);border:1px solid var(--rule)}
.mini-label{font-size:.78rem;font-weight:640;color:var(--muted);margin:0 0 10px}
.steps{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px 16px;counter-reset:step}
.step{display:grid;grid-template-columns:20px minmax(0,1fr);gap:1px 8px;align-items:center;counter-increment:step;padding:8px 10px;border-radius:10px;background:var(--surface-2);border:1px solid var(--rule)}
.step .lv{width:18px;height:18px}
.step-name{font-weight:640;font-size:.875rem}
.step-name::before{content:counter(step) ". ";color:var(--faint);font-weight:500}
.step-state{grid-column:2;font-size:.78rem;color:var(--tone,var(--muted))}
.step.st-todo{opacity:.8}.step.st-todo .step-name{color:var(--muted)}
.step.st-fail{border-color:color-mix(in srgb,var(--fail) 40%,var(--rule));background:color-mix(in srgb,var(--fail) 8%,var(--surface-2))}
/* KPI tiles */
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:14px}
.kpi{display:flex;justify-content:space-between;gap:10px;padding:16px 18px;background:var(--surface);border:1px solid var(--rule);box-shadow:var(--shadow);min-width:0}
.kpi-main{min-width:0;flex:1}
.kpi-title{display:flex;align-items:center;gap:8px;font-size:.84rem;font-weight:620;color:var(--ink-2);margin-bottom:8px}
.kpi-title .ic{width:22px;height:22px;padding:4px;border-radius:7px;color:var(--tone);background:color-mix(in srgb,var(--tone) 15%,transparent)}
.kpi-value{font-size:1.85rem;font-weight:760;letter-spacing:-.03em;line-height:1.05;font-variant-numeric:tabular-nums}
.kpi.tone-muted .kpi-value{font-size:1.2rem;font-weight:650;color:var(--ink-2)}
.kpi-sub{font-size:.84rem;color:var(--muted);margin-top:3px}
.kpi-bar{display:flex;align-items:center;gap:10px;margin-top:10px}
.kpi-pct{font-size:.8rem;font-weight:650;color:var(--ink-2);font-variant-numeric:tabular-nums}
.kpi-note{font-size:.8rem;color:var(--muted);margin-top:6px}
.kpi-note.bad{color:var(--fail);font-weight:620}
.kpi-note.chips{display:flex;gap:5px;flex-wrap:wrap}
.kpi-note .chip{font-size:.76rem;padding:1px 8px}
.bar{display:block;flex:1;height:7px;border-radius:99px;background:var(--sunk);overflow:hidden;border:1px solid var(--rule)}
.bar>span{display:block;height:100%;border-radius:99px;background:var(--tone,var(--accent))}
.ring{width:62px;height:62px;flex:none;align-self:center}
.ring-track{fill:none;stroke:var(--sunk);stroke-width:6}
.ring-val{fill:none;stroke:var(--tone,var(--accent));stroke-width:6;stroke-linecap:round}
.of{color:var(--faint);margin:0 2px;font-weight:450}
/* decision cards */
.facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:8px}
.fact,.card-imp{position:relative;padding:16px 18px 18px;background:linear-gradient(160deg,color-mix(in srgb,var(--tone) 11%,var(--surface)),var(--surface) 70%);border:1px solid color-mix(in srgb,var(--tone) 32%,var(--rule));min-width:0;display:flex;flex-direction:column}
.d-conf{--tone:var(--pass)}.d-att{--tone:var(--warn)}.d-unk{--tone:var(--unknown)}.card-imp{--tone:var(--accent)}
.fact h3,.card-imp h3{display:flex;align-items:center;gap:10px;font-size:.98rem;font-weight:680;margin:0 0 10px}
.f-badge{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;color:var(--tone);background:color-mix(in srgb,var(--tone) 17%,transparent)}
.f-badge .ic{width:17px;height:17px}
.f-count{margin-left:auto;font-size:.8rem;font-weight:740;color:var(--tone);background:color-mix(in srgb,var(--tone) 15%,transparent);border-radius:999px;padding:0 9px;line-height:1.8;font-variant-numeric:tabular-nums}
.fnote{font-size:.85rem;color:var(--muted);margin-top:4px}
.fnote.strong{font-size:.95rem;color:var(--ink);font-weight:620}
.flist{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:.9rem;color:var(--ink-2)}
.flist li{padding-left:16px;position:relative;overflow-wrap:anywhere}
.flist li::before{content:"";position:absolute;left:2px;top:.6em;width:6px;height:6px;border-radius:50%;background:var(--tone)}
.flist.links a{color:var(--ink-2);text-decoration-color:var(--rule-strong)}
.flist .more-n{color:var(--muted)}.flist .more-n::before{display:none}
.tier-code{font-family:var(--mono);font-size:.72rem;color:var(--faint);border:1px solid var(--rule-strong);border-radius:4px;padding:0 4px;margin-left:2px}
.fact .link,.card-imp .link{margin-top:auto;padding-top:12px}
.link{display:inline-flex;align-items:center;gap:6px;font-size:.86rem;font-weight:620;text-decoration:none}
.link:hover{text-decoration:underline}
.link .ic{width:13px;height:13px}
/* ledger */
.sub{margin-top:40px}
.sub-head{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:4px 18px;margin-bottom:14px}
.sub-head>h2,.sub-head>h3{flex-basis:100%}
.sub-head .lead{flex:1;min-width:280px}
.sub-head h2,.area-head h2{display:flex;align-items:center;gap:10px;font-size:1.4rem;font-weight:720;letter-spacing:-.02em;line-height:1.2;margin:0}
.sub-head h3{font-size:1.1rem;letter-spacing:-.01em;margin:0}
.h-badge{display:grid;place-items:center;width:32px;height:32px;border-radius:9px;color:var(--accent);background:var(--accent-soft)}
.h-badge .ic{width:18px;height:18px}
.lead{color:var(--muted);margin-top:4px;font-size:.93rem;max-width:76ch}
.ledger{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);box-shadow:var(--shadow);overflow:hidden}
.lrow{display:grid;grid-template-columns:minmax(170px,230px) minmax(150px,190px) minmax(0,1fr) 28px;gap:16px;align-items:center;padding:12px 18px;border-top:1px solid var(--rule)}
.lrow:first-child{border-top:0}
.lrow.lhead{font-size:.76rem;font-weight:650;color:var(--muted);background:var(--surface-2);padding-top:9px;padding-bottom:9px}
.lrow:not(.lhead):hover{background:color-mix(in srgb,var(--sunk) 60%,transparent)}
.l-area{display:flex;align-items:center;gap:10px;font-weight:620}
.l-ic{width:17px;height:17px;color:var(--muted)}
.l-level{display:flex;align-items:center;gap:8px;font-size:.88rem;color:var(--tone);font-weight:640}
.l-level .lv{width:17px;height:17px}
.l-detail{color:var(--ink-2);font-size:.9rem;min-width:0}
.l-go{color:var(--faint);display:flex;justify-content:center}
.l-go:hover{color:var(--accent)}
.lvl-not_evidenced .l-area,.lvl-declared .l-area{color:var(--ink-2);font-weight:540}
.lvl-failed{background:color-mix(in srgb,var(--fail) 7%,transparent)}
.ledger-foot{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:flex-start;justify-content:space-between;margin-top:12px}
.legend{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.8rem;color:var(--muted)}
.legend li{display:flex;align-items:center;gap:5px}
.legend .lv{width:13px;height:13px}
.limits{font-size:.88rem;color:var(--ink-2);max-width:64ch}
.limits>summary{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2);font-weight:560}
.limits[open]>summary{margin-bottom:8px}
.limits-none{font-size:.85rem;color:var(--muted)}
.original{margin-top:10px;padding:10px 12px;background:var(--sunk);border-radius:var(--r-sm)}
.original-label,.tech-label{font-size:.8rem;color:var(--muted);font-weight:620;margin:12px 0 4px}
.original .original-label{margin-top:0}
.raw-text{color:var(--ink-2)}
summary{cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
.chev{transition:transform .18s ease;color:var(--muted)}
details[open]>summary .chev{transform:rotate(180deg)}
@media (prefers-reduced-motion: no-preference){details[open]>summary~*{animation:reveal .18s ease}}
@keyframes reveal{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:none}}
:target{animation:flash 1.4s ease}
@keyframes flash{0%{box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 50%,transparent)}100%{box-shadow:0 0 0 3px transparent}}
@media (prefers-reduced-motion: reduce){:target{animation:none;outline:2px solid var(--accent)}}
/* areas */
.area{padding-top:52px;margin-top:6px}
.area-head{margin-bottom:18px;max-width:84ch;display:flex;flex-direction:column;gap:2px}
.area-head h2{font-size:1.75rem;letter-spacing:-.025em}
.area-head .lead{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.chips{display:inline-flex;flex-wrap:wrap;gap:6px}
.pill{display:inline-flex;align-items:center;gap:5px;font-size:.78rem;font-weight:650;line-height:1.25;padding:3px 10px 3px 8px;border-radius:999px;color:var(--tone,var(--unknown));background:color-mix(in srgb,var(--tone,var(--unknown)) 13%,transparent);border:1px solid color-mix(in srgb,var(--tone,var(--unknown)) 34%,transparent);white-space:nowrap;vertical-align:middle}
.pill .ic{width:12px;height:12px}
.pill.tone-blocked{border-style:double;border-width:3px;padding:1px 8px 1px 6px}
.pill.tone-unknown{border-style:dotted}
.pill.tone-not_run{border-style:dashed}
.tier,.basis{font-size:.8125rem;color:var(--muted);white-space:nowrap}
.tag{display:inline-block;font-family:var(--mono);font-size:.78rem;background:var(--sunk);border-radius:5px;padding:1px 6px;margin:1px 4px 1px 0}
.tag-area{font-size:.78rem;font-weight:600;color:var(--ink-2);background:var(--sunk);border:1px solid var(--rule);border-radius:6px;padding:1px 8px}
.dot-sep{color:var(--faint);margin:0 2px}
/* findings */
.with-rail{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:20px;align-items:start}
.main-col{min-width:0}
.filters{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;margin:0 0 14px;padding:12px 14px;background:var(--surface);border:1px solid var(--rule)}
.search-box{display:flex;align-items:center;gap:8px;flex:1 1 240px;min-width:0;border:1px solid var(--rule-strong);border-radius:9px;padding:0 10px;background:var(--surface-2)}
.search-box .ic{color:var(--muted)}
.search{flex:1;min-width:0;border:0;background:transparent;padding-left:0}
.search:focus{outline:none}
.search-box:focus-within{outline:2px solid var(--accent);outline-offset:2px}
.fl{font-size:.82rem;color:var(--muted)}
#findings-count{margin-left:auto;font-size:.82rem;font-variant-numeric:tabular-nums}
.finding-list{display:grid;gap:10px}
.finding{background:var(--surface);border:1px solid var(--rule);position:relative;overflow:hidden;transition:border-color .15s ease,box-shadow .15s ease;--tone:var(--rule-strong)}
.finding.sev-high{--tone:var(--fail)}.finding.sev-medium{--tone:var(--warn)}.finding.sev-info{--tone:var(--info)}
.finding::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--tone)}
.finding:hover{border-color:var(--rule-strong)}
.finding[open]{box-shadow:var(--lift);border-color:color-mix(in srgb,var(--tone) 45%,var(--rule))}
.f-row{display:grid;grid-template-columns:34px 96px minmax(0,1fr) 20px;grid-template-areas:"num sev title chev" ". . why ." ". . meta .";gap:3px 14px;padding:15px 18px 14px 22px;align-items:center}
.f-row>.f-num{grid-area:num;display:grid;place-items:center;width:30px;height:30px;border-radius:9px;font-weight:720;font-size:.86rem;color:var(--ink-2);background:var(--sunk);border:1px solid var(--rule)}
.f-row>.f-sev{grid-area:sev}.f-row>.f-title{grid-area:title;margin:0}.f-row>.f-why{grid-area:why}.f-row>.f-meta{grid-area:meta}.f-row>.chev{grid-area:chev}
.f-row:hover .f-title{text-decoration:underline;text-decoration-color:var(--rule-strong);text-underline-offset:4px}
.f-title{font-size:1.02rem;line-height:1.35;font-weight:660;letter-spacing:-.005em}
.f-why{display:block;color:var(--ink-2);font-size:.92rem;max-width:84ch}
.f-meta{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px;margin-top:4px;font-size:.82rem;color:var(--muted)}
.finding.compact .f-row{padding-top:11px;padding-bottom:10px}
.finding.compact .f-title{font-size:.96rem;font-weight:600}
.f-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px 26px;padding:18px 22px 22px 70px;border-top:1px solid var(--rule)}
.f-col{display:grid;gap:14px;align-content:start;min-width:0}
.f-body>.tech{grid-column:1/-1}
.f-block{display:grid;grid-template-columns:30px minmax(0,1fr);gap:10px;min-width:0}
.fb-ic{width:30px;height:30px;padding:7px;border-radius:9px;color:var(--accent);background:var(--accent-soft)}
.f-fix .fb-ic{color:var(--pass);background:color-mix(in srgb,var(--pass) 14%,transparent)}
.f-close .fb-ic{color:var(--pass);background:color-mix(in srgb,var(--pass) 14%,transparent)}
.f-block h4{font-size:.9rem;margin:3px 0 4px;display:flex;align-items:center;gap:10px;color:var(--ink)}
.f-block p{color:var(--ink-2)}
.f-fix{padding:12px;border:1px solid color-mix(in srgb,var(--pass) 28%,var(--rule));border-radius:var(--r);background:color-mix(in srgb,var(--pass) 5%,transparent)}
.f-fix p{font-weight:560;color:var(--ink)}
.affected{font-weight:640;margin-bottom:4px;color:var(--ink)}
.tech>summary,.more>summary{display:inline-flex;align-items:center;gap:6px;font-size:.84rem;color:var(--accent);font-weight:620}
.tech>summary::before,.more>summary::before{content:"";width:6px;height:6px;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(-45deg);transition:transform .15s ease}
.tech[open]>summary::before,.more[open]>summary::before{transform:rotate(45deg)}
.kv{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:5px 16px;margin:8px 0;font-size:.84rem}
.kv dt{color:var(--muted)}
.kv dd{margin:0;min-width:0;overflow-wrap:anywhere}
pre.code{margin:6px 0 0;padding:12px 14px;background:var(--sunk);border:1px solid var(--rule);border-radius:10px;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;max-height:420px;overflow:auto;font-size:.79rem;line-height:1.55}
pre.code.clamped{max-height:13.5em;overflow:hidden;-webkit-mask-image:linear-gradient(#000 70%,transparent);mask-image:linear-gradient(#000 70%,transparent)}
pre.code.full{max-height:none}
.expand{margin-top:6px;font:inherit;font-size:.8125rem;font-weight:620;color:var(--accent);background:none;border:0;padding:2px 0;cursor:pointer}
pre.diff{white-space:pre;overflow-x:auto}
.list{margin:4px 0;padding-left:1.15em}
.list li{margin:3px 0;overflow-wrap:anywhere}
.list li::marker{color:var(--faint)}
.f-rail{display:grid;gap:14px;position:sticky;top:76px}
.rail-card{padding:16px 18px;background:var(--surface);border:1px solid var(--rule);box-shadow:var(--shadow)}
.rail-card h3{font-size:.92rem;margin:0 0 12px}
.donut-row{display:flex;align-items:center;gap:16px}
.donut-wrap{position:relative;width:96px;height:96px;flex:none}
.donut{width:96px;height:96px}
.donut circle{fill:none;stroke-width:11}
.d-track{stroke:var(--sunk)}.d-high{stroke:var(--fail)}.d-medium{stroke:var(--warn)}.d-info{stroke:var(--info)}
.donut-n{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;font-size:.72rem;color:var(--muted)}
.donut-n b{font-size:1.35rem;color:var(--ink);line-height:1}
.sev-legend{list-style:none;margin:0;padding:0;display:grid;gap:6px;font-size:.85rem;flex:1}
.sev-legend li{display:flex;align-items:center;gap:8px}
.sev-legend b{margin-left:auto;font-variant-numeric:tabular-nums}
.sw{width:10px;height:10px;border-radius:3px;background:var(--faint)}
.lg-high .sw{background:var(--fail)}.lg-medium .sw{background:var(--warn)}.lg-info .sw{background:var(--info)}
.area-bars{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.area-bars li{display:grid;grid-template-columns:minmax(0,1fr) 90px 22px;gap:10px;align-items:center;font-size:.85rem}
.area-bars b{text-align:right;font-variant-numeric:tabular-nums}
.area-pick{font:inherit;text-align:left;color:var(--ink-2);background:none;border:0;padding:0;cursor:pointer;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.area-pick:hover{color:var(--accent);text-decoration:underline}
/* improvements */
.rec-group{margin-top:22px}
.rec-group>h3{display:flex;align-items:center;gap:10px;font-size:1rem;margin:0 0 10px}
.rec-group>h3 .ic{width:20px;height:20px;padding:3px;border-radius:6px;color:var(--accent);background:var(--accent-soft)}
.count{font-size:.76rem;font-weight:700;color:var(--muted);background:var(--sunk);border:1px solid var(--rule);border-radius:999px;padding:0 8px;line-height:1.7;font-variant-numeric:tabular-nums}
.g-first>h3{color:var(--pass)}.g-first>h3 .ic{color:var(--pass);background:color-mix(in srgb,var(--pass) 15%,transparent)}
.group-note{color:var(--muted);font-size:.88rem;margin:-4px 0 10px}
.rec-list{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);overflow:hidden}
.g-first .rec-list{border-color:color-mix(in srgb,var(--pass) 40%,var(--rule));box-shadow:var(--lift)}
.rec+.rec{border-top:1px solid var(--rule)}
.rec summary{display:grid;grid-template-columns:38px minmax(0,1fr) auto 20px;gap:6px 14px;align-items:start;padding:14px 18px}
.rec summary:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.rec-n{display:grid;place-items:center;width:30px;height:30px;border-radius:9px;font-family:var(--mono);font-size:.8rem;color:var(--muted);background:var(--sunk);border:1px solid var(--rule)}
.g-first .rec-n{color:var(--pass);font-weight:700;border-color:color-mix(in srgb,var(--pass) 40%,var(--rule))}
.rec-main{display:flex;flex-direction:column;gap:2px;min-width:0}
.rec-act{font-weight:660;font-size:1rem}
.rec-why{color:var(--muted);font-size:.88rem}
.rec-side{display:flex;gap:6px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.rec-body{padding:0 18px 18px 70px}
.rec-text{color:var(--ink-2);max-width:84ch}
.rec-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px 24px;margin:12px 0 0;font-size:.86rem}
.rec-meta dt{color:var(--muted);font-size:.76rem;font-weight:620}
.rec-meta dd{margin:2px 0 0;color:var(--ink-2)}
.rec-meta a{color:var(--ink)}
.rec-states{list-style:none;margin:0;padding:0;display:flex;gap:4px;flex-wrap:wrap}
.rec-states li{font-size:.76rem;padding:1px 8px;border-radius:999px;border:1px dashed var(--rule-strong);color:var(--faint)}
.rec-states li.on{border-style:solid;border-color:var(--accent);color:var(--accent);font-weight:640}
/* evidence */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:14px}
.tile{display:flex;justify-content:space-between;gap:10px;padding:16px 18px;background:var(--surface);border:1px solid var(--rule);box-shadow:var(--shadow);min-width:0}
.tile-main{min-width:0;flex:1}
.t-domain{display:flex;align-items:center;gap:7px;font-size:.8rem;font-weight:640;color:var(--muted);margin-bottom:8px}
.t-domain .lv{width:15px;height:15px}
.t-value{font-size:1.75rem;font-weight:760;letter-spacing:-.03em;line-height:1.1;font-variant-numeric:tabular-nums}
.tile.tone-fail .t-value{color:var(--fail)}
.t-label{font-size:.85rem;color:var(--ink-2);margin-top:2px}
.t-sub{font-size:.8rem;color:var(--muted);margin-top:5px}
.t-sub.bad{color:var(--fail);font-weight:620}
.t-bar{margin-top:10px}
.t-note{font-size:.76rem;color:var(--warn);margin-top:4px}
.t-change{font-size:.78rem;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px dashed var(--rule)}
.dmark{font-size:.72rem;font-weight:680;padding:0 6px;border-radius:4px}
.dm-improved{color:var(--pass);background:color-mix(in srgb,var(--pass) 14%,transparent)}.dm-regressed{color:var(--fail);background:color-mix(in srgb,var(--fail) 14%,transparent)}
.dm-changed{color:var(--muted);background:var(--sunk)}.dm-unknown{color:var(--unknown);background:var(--sunk)}
.t-change.dm-improved,.t-change.dm-regressed,.t-change.dm-changed,.t-change.dm-unknown{background:none}
.panels-head{margin-top:34px}
.panels-d{margin-top:10px;background:var(--surface);border:1px solid var(--rule);overflow:hidden;counter-reset:panel}
.panel-d+.panel-d{border-top:1px solid var(--rule)}
.panel-d>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 18px}
.panels-d.numbered .panel-d>summary::before{counter-increment:panel;content:counter(panel,decimal-leading-zero);font-family:var(--mono);font-size:.76rem;color:var(--muted);background:var(--sunk);border:1px solid var(--rule);border-radius:8px;padding:3px 7px}
.panel-d>summary:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.pd-title{display:flex;align-items:baseline;flex-wrap:wrap;gap:2px 14px;min-width:0;flex:1}
.pd-title h3{font-size:.96rem;margin:0;font-weight:640}
.pd-sum{color:var(--muted);font-size:.83rem}
.pd-body{padding:4px 18px 20px;font-size:.92rem}
.pd-body>.lead{margin:0 0 12px;font-size:.86rem}
.table-wrap{background:var(--surface);border:1px solid var(--rule);overflow:hidden;margin:0 0 12px}
table{border-collapse:collapse;width:100%;font-size:.84rem}
caption{text-align:left;font-size:.84rem;font-weight:660;color:var(--ink-2);padding:11px 14px 7px}
th,td{text-align:left;vertical-align:top;padding:8px 14px;border-top:1px solid var(--rule)}
thead th{font-size:.76rem;font-weight:660;color:var(--muted);background:var(--surface-2)}
tbody th{font-weight:520}
.num-col{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.m-name{display:block}
.m-id{display:block;font-size:.72rem;color:var(--faint)}
.th-note{display:block;font-size:.78rem;color:var(--muted);margin-top:3px;white-space:normal}
.dir{color:var(--muted)}
.origins{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:12px;margin-top:10px}
.origin{border:1px solid var(--rule);border-radius:var(--r);min-width:0;overflow:hidden}
.origin-head{display:flex;justify-content:space-between;align-items:center;margin:0;padding:9px 14px;border-bottom:1px solid var(--rule);font-size:.9rem;background:var(--surface-2)}
.origin-head .count{background:none;border:0;padding:0}
.check-list{list-style:none;margin:0;padding:0}
.check{border-top:1px solid var(--rule)}
.check:first-child{border-top:0}
.check summary{display:grid;grid-template-columns:auto minmax(0,1fr) auto auto;gap:10px;align-items:center;padding:8px 14px}
.check summary:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.kind{font-size:.74rem;font-weight:660;padding:1px 7px;border-radius:6px;background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.kind-unknown,.kind-custom{background:var(--sunk);color:var(--muted)}
.check-title{display:flex;flex-direction:column;min-width:0}
.check-name{font-weight:580;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.check-where{font-size:.8rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gate{font-size:.8rem;color:var(--muted);white-space:nowrap}
.gate-blocking{color:var(--ink);font-weight:640}
.check-body{padding:2px 14px 12px}
.cmd{margin-top:10px}
.cmd-head{display:flex;align-items:center;gap:8px;font-size:.8rem;color:var(--muted);font-weight:640}
.cmd-head .copy{margin-left:auto}
.copy{font:inherit;font-size:.78rem;display:inline-flex;gap:5px;align-items:center;color:var(--muted);background:var(--surface);border:1px solid var(--rule-strong);border-radius:8px;padding:3px 9px;cursor:pointer;transition:color .15s ease,border-color .15s ease}
.copy:hover{color:var(--ink)}
.copy.done{color:var(--pass);border-color:var(--pass)}
.copy .ic{width:13px;height:13px}
code.wrap{white-space:pre-wrap}
.runs{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.run,.artifact{border:1px solid var(--rule);border-radius:var(--r);padding:12px 14px;background:var(--surface-2)}
.run-head{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
.run-title{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.run-how{color:var(--muted);font-size:.86rem;margin-top:4px}
.matrix{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.checks-list{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:5px;font-size:.84rem}
.checks-list li{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:14px 24px;margin-bottom:12px}
.cols h4{font-size:.875rem;margin:0 0 4px}
.meta-row{display:flex;flex-wrap:wrap;gap:6px 18px;color:var(--muted);font-size:.86rem;margin-bottom:10px;align-items:center}
/* candidate */
.pillars{display:grid;gap:10px}
.pillar{background:var(--surface);border:1px solid var(--rule);overflow:hidden;position:relative;--tone:var(--rule-strong)}
.pillar::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--tone)}
.pillar.st-fail,.pillar.st-blocked{--tone:var(--fail);border-color:color-mix(in srgb,var(--fail) 42%,var(--rule));box-shadow:var(--lift);background:linear-gradient(110deg,color-mix(in srgb,var(--fail) 7%,var(--surface)),var(--surface) 55%)}
.pillar.st-pass{--tone:var(--pass)}
.pillar.st-unknown,.pillar.st-not_run{--tone:var(--unknown)}
.pillar>summary{display:grid;grid-template-columns:118px minmax(0,1fr) auto 20px;gap:14px;align-items:center;padding:14px 18px 14px 22px}
.pillar>summary:hover{background:color-mix(in srgb,var(--sunk) 45%,transparent)}
.p-main{display:flex;flex-direction:column;gap:2px;min-width:0}
.p-name{font-size:1rem;margin:0;font-weight:660}
.p-reason{font-size:.89rem;color:var(--ink-2)}
.p-check{font-weight:620}
.pillar.st-pass .p-reason{color:var(--muted)}
.p-count{font-family:var(--mono);font-size:.8rem;color:var(--muted)}
.qlist{list-style:none;margin:0;padding:14px 22px 18px 154px;display:grid;gap:12px;border-top:1px solid var(--rule)}
.qrow{display:grid;grid-template-columns:110px minmax(0,1fr);gap:10px;align-items:start;margin-left:-118px}
.q-name{font-weight:620}
.q-sum{color:var(--ink-2);font-size:.91rem;margin-top:1px}
.q-main .tech{margin-top:4px}
.qrow.st-fail .q-name,.qrow.st-blocked .q-name{color:var(--fail)}
.changes{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);overflow:hidden}
.change+.change{border-top:1px solid var(--rule)}
.change summary{display:flex;align-items:center;gap:8px;padding:12px 18px;flex-wrap:wrap}
.change summary .chev{margin-left:auto}
.path{font-weight:620}
.change-body{padding:0 18px 16px}
/* delta */
.dcounts{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;background:var(--surface);border:1px solid var(--rule);overflow:hidden}
.dc{flex:1 1 140px;min-width:0}
.dc+.dc{border-left:1px solid var(--rule)}
.dc a{display:flex;flex-direction:column;gap:1px;padding:13px 16px;color:var(--ink-2);text-decoration:none;font-size:.84rem}
.dc a:hover{background:color-mix(in srgb,var(--sunk) 55%,transparent)}
.dc-n{font-size:1.65rem;font-weight:760;letter-spacing:-.025em;line-height:1.1;color:var(--ink);font-variant-numeric:tabular-nums}
.dc-improved .dc-n{color:var(--pass)}.dc-regressed .dc-n{color:var(--fail)}
.dc.zero .dc-n{color:var(--faint)}
.dc-regressed:not(.zero){background:color-mix(in srgb,var(--fail) 9%,transparent)}
.dc-unknown:not(.zero){background:var(--sunk)}
.dgroup{margin-top:22px}
.dgroup>h3{display:flex;align-items:center;gap:10px;font-size:1rem;margin:0}
.dg-lead{color:var(--muted);font-size:.86rem;margin:2px 0 8px}
.dg-regressed>h3{color:var(--fail)}.dg-improved>h3{color:var(--pass)}
.drows{list-style:none;margin:0;padding:0;background:var(--surface);border:1px solid var(--rule);overflow:hidden}
.drow{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:2px 14px;align-items:baseline;padding:10px 16px;border-top:1px solid var(--rule)}
.drow:first-child{border-top:0}
.d-glyph{font-family:var(--mono);font-weight:700;text-align:center;color:var(--muted)}
.d-improved .d-glyph{color:var(--pass)}.d-regressed .d-glyph{color:var(--fail)}
.d-regressed{background:color-mix(in srgb,var(--fail) 8%,transparent)}
.d-name .m-name{font-weight:580}
.d-vals{font-variant-numeric:tabular-nums;font-weight:680;white-space:nowrap}
.d-note{grid-column:2/-1;font-size:.84rem;color:var(--muted)}
.dg-unchanged>summary{display:flex;align-items:center;justify-content:space-between;padding:11px 16px;color:var(--ink-2);font-weight:580;background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-lg)}
.dg-unchanged[open]>summary{border-radius:var(--r-lg) var(--r-lg) 0 0}
.dg-unchanged .drows{border-top:0;border-radius:0 0 var(--r-lg) var(--r-lg)}
.dg-unchanged .drow{color:var(--muted)}
/* technical details */
.area-tech{font-size:.94rem}
.prov{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin:0 0 12px;background:var(--surface);border:1px solid var(--rule);overflow:hidden}
.prov div{display:grid;grid-template-columns:auto minmax(0,1fr);grid-template-rows:auto auto;column-gap:12px;padding:14px 16px;border-top:1px solid var(--rule);border-left:1px solid var(--rule);min-width:0}
.prov div:nth-child(-n+3){border-top:0}.prov div:nth-child(3n+1){border-left:0}
.p-ic{grid-row:1/3;width:30px;height:30px;padding:7px;border-radius:9px;color:var(--accent);background:var(--accent-soft)}
.prov dt{font-size:.76rem;color:var(--muted);font-weight:620}
.prov dd{margin:2px 0 0;font-size:.92rem;font-weight:560;overflow-wrap:anywhere}
.prov-warn{margin:0 0 10px;padding:10px 14px;border-radius:var(--r);background:color-mix(in srgb,var(--warn) 12%,transparent);color:var(--ink);border:1px solid color-mix(in srgb,var(--warn) 38%,transparent);font-size:.9rem}
.arts{margin-top:12px}
.claim-groups{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;align-items:start}
.claim-g{background:linear-gradient(160deg,color-mix(in srgb,var(--tone) 9%,var(--surface)),var(--surface) 70%);border:1px solid color-mix(in srgb,var(--tone) 30%,var(--rule));min-width:0}
.claim-g>summary{display:grid;grid-template-columns:minmax(0,1fr) 20px;gap:8px 12px;align-items:center;padding:13px 16px}
.cg-title{display:flex;align-items:center;gap:8px;font-weight:680}
.cg-title .lv{width:18px;height:18px}
.cd-index{grid-column:1/-1;grid-row:2;list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:4px 12px;font-size:.8rem;color:var(--muted)}
.cd-index li{display:flex;gap:5px;align-items:center}
.cd-index a{color:var(--ink-2);text-decoration:none}
.cd-index .count{background:none;border:0;padding:0}
.cg-body{padding:2px 16px 14px;border-top:1px solid var(--rule)}
.cd{padding-top:10px}
.cd-head{display:flex;align-items:center;gap:8px;font-size:.83rem;font-weight:660;color:var(--ink-2)}
.cd .list{font-size:.86rem}
.budget{list-style:none;margin:0;padding:0}
.budget-row{display:grid;grid-template-columns:auto minmax(110px,220px) minmax(0,1fr);gap:12px;align-items:baseline;padding:8px 0;border-top:1px solid var(--rule);font-size:.84rem}
.budget-reason{color:var(--muted)}
.more{margin:8px 0}
.footer{margin-top:auto;padding:22px 32px;color:var(--muted);font-size:.8rem;border-top:1px solid var(--rule)}
/* responsive */
@media (max-width:1320px){.with-rail{grid-template-columns:minmax(0,1fr)}.f-rail{position:static;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.kpis,.facts{grid-template-columns:repeat(2,minmax(0,1fr))}.claim-groups{grid-template-columns:minmax(0,1fr)}.steps{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:1100px){.app{grid-template-columns:minmax(0,1fr);grid-template-areas:"top" "nav" "main" "foot"}
.page{display:contents}.topbar{grid-area:top}main{grid-area:main}.footer{grid-area:foot}
.sidebar{grid-area:nav;position:sticky;top:60px;z-index:15;height:auto;flex-direction:row;padding:8px 20px;gap:8px;overflow-x:auto;scrollbar-width:none;background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:blur(8px);border-right:0;border-bottom:1px solid var(--rule)}
.sidebar .brand,.about,.side-version{display:none}
.sidenav>ul{display:flex;gap:6px;width:max-content}.nav-sub,li.active>.nav-sub{display:none}
.nav-area{border:1px solid var(--rule);border-radius:999px;padding:6px 13px;white-space:nowrap;font-size:.86rem}
li.active>.nav-area{background:var(--ink);color:var(--bg);box-shadow:none}li.active>.nav-area .nav-ic{color:var(--bg)}
li.active .badge{background:color-mix(in srgb,var(--bg) 22%,transparent);color:var(--bg);border-color:transparent}
.brand-mini{display:inline-flex}.brand-mini .logo{width:26px;height:26px}
html{scroll-padding-top:120px}.topbar{padding:0 20px}main{padding:0 20px 80px}
.hero{grid-template-columns:minmax(0,1fr)}.hero::before{display:none}
.area-overview{display:flex;flex-direction:column}.area-overview>*{order:3}.hero{display:contents}.ident{order:0;padding-top:0;margin-bottom:18px}.area-overview>.decision{order:1}.rail{order:2;margin-bottom:18px}.prov{grid-template-columns:repeat(2,minmax(0,1fr))}
.prov div{border-left:0!important;border-top:1px solid var(--rule)!important}.prov div:nth-child(-n+2){border-top:0!important}.prov div:nth-child(even){border-left:1px solid var(--rule)!important}}
@media (max-width:760px){body{font-size:14.5px}.topbar{height:56px;padding:0 14px}.sidebar{top:56px;padding:8px 14px}main{padding:0 14px 72px}
.crumbs .ic:not(.logo),.crumb:not(.cur){display:none}.status-pill{display:none}.lang .ic{display:none}.lang .select{max-width:140px}
.kpis,.facts{grid-template-columns:minmax(0,1fr)}.steps{grid-template-columns:repeat(2,minmax(0,1fr))}
.d-main{flex-direction:column;align-items:flex-start;gap:14px;padding:20px 18px}.c-badge{width:52px;height:52px;border-radius:15px}.c-badge .ic{width:26px;height:26px}
.lrow{grid-template-columns:minmax(0,1fr) auto;gap:4px 12px}.lrow.lhead{display:none}.l-detail{grid-column:1/-1}.l-go{display:none}
.f-row{grid-template-columns:30px minmax(0,1fr) 20px;grid-template-areas:"num sev chev" "title title title" "why why why" "meta meta meta";padding:13px 14px 12px 18px}
.f-body{grid-template-columns:minmax(0,1fr);padding:14px 16px 18px}
.rec summary{grid-template-columns:34px minmax(0,1fr) 20px}.rec-side{grid-column:2;justify-content:flex-start}.rec-body{padding:0 16px 16px}
.qlist{padding-left:18px}.qrow{margin-left:0;grid-template-columns:minmax(0,1fr)}
.pillar>summary{grid-template-columns:minmax(0,1fr) auto 20px}.pillar>summary>.pill{grid-column:1/-1;justify-self:start}
.dcounts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.dc+.dc{border-left:0}.dc{border-top:1px solid var(--rule)}.dc:nth-child(-n+2){border-top:0}.dc:nth-child(even){border-left:1px solid var(--rule)}
.prov{grid-template-columns:minmax(0,1fr)}.prov div{border-left:0!important;border-top:1px solid var(--rule)!important}.prov div:first-child{border-top:0!important}
table.responsive thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
table.responsive tr{display:block;border-top:1px solid var(--rule);padding:6px 0}
table.responsive th,table.responsive td{display:block;border:0;padding:3px 12px;text-align:left}
table.responsive td[data-label]::before{content:attr(data-label);display:block;font-size:.74rem;color:var(--muted)}
.num-col{text-align:left}
.check summary{grid-template-columns:minmax(0,1fr) auto}.check summary .kind{grid-column:1/-1;justify-self:start}
.budget-row{grid-template-columns:minmax(0,1fr)}.kv{grid-template-columns:minmax(0,1fr)}.kv dt{margin-top:6px}
.drow{grid-template-columns:20px minmax(0,1fr)}.d-vals{grid-column:2}}
@media (prefers-reduced-motion: reduce){*,*::before,*::after{transition:none!important;animation:none!important;scroll-behavior:auto!important}}
.no-anim *{transition:none!important}
@media print{
@page{margin:14mm}
body{background:#fff;color:#000;font-size:11pt}
.sidebar,.topbar,.filters,.copy,.skip,.expand,.l-go,.btn,.chev,.f-rail{display:none!important}
.app{display:block}main{padding:0;max-width:none}
.decision,.ledger,.finding,.pillar,.tile,.kpi,.fact,.card-imp,.rec,.panels-d,.claim-g,.prov,.rail{box-shadow:none;break-inside:avoid}
.area{padding-top:18px}
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
document.querySelectorAll('.area-pick').forEach(function(b){b.addEventListener('click',function(){if(F.cat){F.cat.value=b.dataset.cat;filter(true);var l=document.querySelector('.finding-list');if(l&&l.scrollIntoView)l.scrollIntoView({block:'start'});}});});
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
var areas=[].slice.call(document.querySelectorAll('main .area')),links={};
document.querySelectorAll('.sidenav [data-area]').forEach(function(li){links[li.getAttribute('data-area')]=li;});
function mark(id){Object.keys(links).forEach(function(a){var li=links[a],on=a===id;li.classList.toggle('active',on);var link=li.querySelector('.nav-area');
 if(on){link.setAttribute('aria-current','location');var bar=li.closest('.sidebar');if(bar&&getComputedStyle(li.parentElement).display==='flex'){var r=li.getBoundingClientRect(),b=bar.getBoundingClientRect();if(r.left<b.left||r.right>b.right)bar.scrollLeft+=r.left-b.left-16;}}
 else link.removeAttribute('aria-current');});}
function current(){var best=areas[0],line=window.innerHeight*0.3;areas.forEach(function(a){if(a.getBoundingClientRect().top<=line)best=a;});if(best)mark(best.id);}
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
