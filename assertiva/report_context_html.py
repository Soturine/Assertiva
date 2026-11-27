"""Report panels for the v1.1 sections: documentary context and traceability, external executions, independent reviews,
earlier traceability, and feedback about Assertiva.

Same page, same model: these render what ``audit.json`` holds, escaped, without scripts or remote resources. Agent text
is shown as written; enums and counts are the engine's.
"""

from __future__ import annotations

from typing import Any

from .report_html import _R, _e, _panel

_STATUS_TONE = {
    "PROVEN_IN_SCOPE": "pass", "OBSERVED_PASS": "pass", "PARTIAL": "warn", "WEAK": "warn", "CHARACTERIZATION_ONLY": "warn",
    "NOT_EVIDENCED": "fail", "UNKNOWN": "unknown", "BLOCKED": "blocked", "NOT_APPLICABLE": "neutral", "STALE": "warn",
    "PASS": "pass", "FAIL": "fail", "ERROR": "fail", "NO_TESTS": "unknown", "VERIFIED": "pass", "UNVERIFIED": "unknown",
    "WRITTEN": "pass", "DISABLED": "neutral", "NOT_RUN": "not_run", "DONE": "pass",
}


def _badge(r: _R, raw: Any) -> str:
    return r.pill(str(raw), tone=_STATUS_TONE.get(str(raw), "neutral"))


def _codes(values: list[str]) -> str:
    return " ".join(f"<code>{_e(v)}</code>" for v in values) or "—"


def _table(r: _R, caption_key: str, heads: list[str], rows: list[str]) -> str:
    head = "".join(f'<th scope="col">{r.t(h)}</th>' for h in heads)
    return (f'<div class="table-wrap"><table class="responsive"><caption>{r.t(caption_key)}</caption><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def context_panel(r: _R) -> str:
    context = r.report.get("context")
    if not context:
        return ""
    source_rows = []
    for s in context["sources"]:
        cov = s.get("coverage") or {}
        read = (f'{cov.get("reviewed", 0)}/{cov["of"]} {_e(cov.get("unit"))}' if cov.get("of") else
                f'{cov.get("reviewed", 0)} {_e(cov.get("unit"))} / ?')
        where = s.get("path") or s.get("uri") or "external"
        source_rows.append(
            f'<tr><th scope="row"><code>{_e(s["id"])}</code> {r.agent_text(s["title"])}<br><code class="muted">{_e(where)}</code></th>'
            f'<td {r.label_attr("ctx.src.authority")}><code>{_e(s["authority"])}</code></td>'
            f'<td {r.label_attr("ctx.src.read")}>{read}<br>{_codes(s["review"]["methods"])}<br>{_codes(s["review"]["modalities_read"])}</td>'
            f'<td {r.label_attr("ctx.src.state")}>{_codes(s["labels"])}<br><code class="muted">{_e((s.get("verification") or {}).get("digest"))}</code></td></tr>')
    behavior_rows = []
    for b in context["behaviors"]:
        d = b["dimensions"]
        cites = ", ".join(f'{c["source"]}' + (f' {c["locator"]}' if c.get("locator") else "") for c in b["sources"]) or "—"
        tests = "<br>".join(f'<code>{_e(t["test"])}</code> · {_e(t["relation"])} · oracle {_e(t["oracle"])} · {_e(t["outcome"])}'
                            for t in b["tests"]) or "—"
        behavior_rows.append(
            f'<tr><th scope="row"><code>{_e(b["id"])}</code> {r.agent_text(b["title"])}<br><span class="muted">{_e(cites)}</span></th>'
            f'<td {r.label_attr("ctx.beh.status")}>{_badge(r, b["status"])}'
            + (f'<br><span class="muted">claimed {_e(b["claimed_status"])}</span>' if b["status"] != b["claimed_status"] else "")
            + f'</td><td {r.label_attr("ctx.beh.tests")}>{d["executed"]}/{d["linked_tests"]} · {d["passed"]} ✓ · {d["failed"]} ✗<br>{tests}</td>'
            f'<td {r.label_attr("ctx.beh.fault")}><code>{_e(d["fault_sensitivity"])}</code>'
            + "".join(f'<br><code class="muted">{_e(p["ref"])}: {_e(p["basis"])}</code>' for p in b.get("protection") or [])
            + (f'<br>{r.t("ctx.limited", cls="muted")}' if b.get("status_limited_by") else "") + '</td></tr>')
    summary = context["summary"]
    counts = ", ".join(f"{k} {v}" for k, v in sorted(summary["behaviors_by_status"].items())) or "—"
    body = (_table(r, "ctx.src.caption", ["ctx.src.id", "ctx.src.authority", "ctx.src.read", "ctx.src.state"], source_rows)
            + (_table(r, "ctx.beh.caption", ["ctx.beh.id", "ctx.beh.status", "ctx.beh.tests", "ctx.beh.fault"], behavior_rows)
               if behavior_rows else r.t("ctx.beh.none", tag="p", cls="empty"))
            + f'<p class="meta-row"><code>{_e(counts)}</code></p>'
            + (f'<p class="meta-row">{r.t("ctx.conflicts")} <code>{_e(summary["conflicts"])}</code></p>' if summary["conflicts"] else "")
            + r.t("ctx.claim", tag="p", cls="muted"))
    return _panel(r, "context", "ctx.title", r.t("ctx.summary", n=summary["behaviors"], s=summary["sources"]), body, "ctx.lead", open_=True)


def external_panel(r: _R) -> str:
    receipts = r.report.get("external_executions") or []
    if not receipts:
        return ""
    rows = []
    for x in receipts:
        res = x.get("results") or {}
        counts = (f'{res.get("tests", 0)} · {res.get("passed", 0)} ✓ · {res.get("failed", 0) + res.get("errors", 0)} ✗ · '
                  f'{res.get("skipped", 0)} ⊘' if res else "—")
        rows.append(
            f'<tr><th scope="row"><code>{_e(x["id"])}</code><br>{_e(x["tool"])} {_e(x["tool_version"])} · {_e(x["ecosystem"])}</th>'
            f'<td {r.label_attr("ext.purpose")}><code>{_e(x["purpose"])}</code><br><code class="muted">{_e(x["isolation"])} · net {_e(x["network"])}</code></td>'
            f'<td {r.label_attr("ext.status")}>{_badge(r, x["status"])} <span class="muted">exit {_e(x.get("exit_code"))}</span><br>{counts}</td>'
            f'<td {r.label_attr("ext.link")}>{_badge(r, x["link"])}<br><code class="muted">{_e(x["revision_link"])} · {_e(x["results_consistency"])}</code></td></tr>'
            f'<tr><td colspan="4"><code class="raw-text">{_e(" ".join(x["command"]))}</code></td></tr>')
    body = _table(r, "ext.caption", ["ext.tool", "ext.purpose", "ext.status", "ext.link"], rows) + r.t("ext.claim", tag="p", cls="muted")
    return _panel(r, "external", "ext.title", r.t("ext.summary", n=len(receipts)), body, open_=True)


def reviews_panel(r: _R) -> str:
    reviews = r.report.get("reviews") or []
    if not reviews:
        return ""
    items = "".join(
        f'<li>{r.agent_text(v["scope"])} · <code>{_e(v["reviewer"]["kind"])}/{_e(v["reviewer"]["model"])}</code> · '
        f'<code>{_e(v["relation_to_author"])}</code> (independence {_e(v["independence"])}) · {_badge(r, v["outcome"])} · '
        f'<code class="muted">transmission {_e(v["transmission"]["mode"])}</code></li>' for v in reviews)
    return _panel(r, "reviews", "rev.title", r.t("rev.summary", n=len(reviews)), f'<ul class="list">{items}</ul>' + r.t("rev.claim", tag="p", cls="muted"))


def previous_panel(r: _R) -> str:
    previous = r.report.get("previous_traceability")
    if not previous:
        return ""
    stale = [b for b in previous["behaviors"] if b["state"] == "STALE"]
    items = "".join(f'<li><code>{_e(b["id"])}</code> {_badge(r, b["state"])} <span class="muted">{_e("; ".join(b["because"]))}</span></li>'
                    for b in previous["behaviors"])
    return _panel(r, "previous-trace", "prev.title", r.t("prev.summary", n=len(stale), v=len(previous["behaviors"]) - len(stale)),
                  f'<ul class="list">{items}</ul>', "prev.lead")


def dogfood_panel(r: _R) -> str:
    dogfood = r.report.get("dogfood")
    if not dogfood:
        return ""
    if dogfood.get("export") != "WRITTEN":
        body = r.t("df.notwritten", tag="p", cls="muted", why=dogfood.get("reason") or dogfood.get("export"))
        return _panel(r, "dogfood", "df.title", _badge(r, dogfood.get("export")), body, "df.lead")
    entries = "".join(
        f'<li><code>{_e(e["feedback_id"])}</code> {_e(e["title"])} · <code>{_e(e["kind"])}</code> · <code>{_e(e["component"])}</code> · '
        f'<code>{_e(e["observation_kind"])}</code> · <code class="muted">{_e(e["status"])} · {_e(e["provenance"])}</code></li>'
        for e in dogfood.get("entries") or [])
    files = " · ".join(f"<code>{_e(v)}</code>" for v in (dogfood.get("files") or {}).values())
    body = (f'<p class="meta-row"><code>{_e(dogfood["report_id"])}</code> · {_badge(r, dogfood["review_mode"])} · '
            f'{_badge(r, dogfood["review_status"])} · semantic review {_badge(r, dogfood["semantic_review"])}</p>'
            + (f'<ul class="list">{entries}</ul>' if entries else r.t("df.none", tag="p", cls="empty"))
            + f'<p class="meta-row">{r.t("df.files")} {files}</p>' + r.t("df.claim", tag="p", cls="muted"))
    return _panel(r, "dogfood", "df.title", r.t("df.summary", n=dogfood.get("feedback", 0), c=dogfood.get("confirmed_capabilities", 0)),
                  body, "df.lead")
