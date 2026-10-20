"""Automated accessibility results: axe-core JSON (``axe.run`` results, as written by @axe-core/playwright,
@axe-core/cli, which writes a list of them, or a page script).

What such a run proves is narrow, and the evidence says so: the rules the engine checked found these violations on
this page in this state. Automated rules cover only part of WCAG (keyboard use, focus order, meaningful text, captions
and most of what people need are judged by people), so no violations is never "accessible", and ``incomplete``
results are items the engine could not decide: they need a person's review, they are not passes.
"""

from __future__ import annotations

import json
from pathlib import Path

CLAIM = ("automated rules check part of WCAG on the pages and states they ran on; no violation is not proof of "
         "accessibility, and items the engine could not decide need review")
_SEVERITY = {"critical": "high", "serious": "high", "moderate": "medium", "minor": "low"}


def _page(data: dict, source: str) -> dict:
    engine = data.get("testEngine") or {}
    agent = (data.get("testEnvironment") or {}).get("userAgent") or ""

    def rules(items, with_nodes=True):
        return [{"rule": item.get("id"), "impact": item.get("impact"), "nodes": len(item.get("nodes") or []),
                 "wcag": [t for t in item.get("tags") or [] if t.startswith("wcag")], "help": item.get("help"),
                 **({"targets": [", ".join(map(str, n.get("target") or [])) for n in (item.get("nodes") or [])[:5]]} if with_nodes else {})}
                for item in items or []]

    return {
        "source": source, "url": data.get("url"), "engine": engine.get("name"), "engine_version": engine.get("version"),
        "browser": next((part for part in agent.split() if part.split("/")[0] in ("HeadlessChrome", "Chrome", "Firefox", "Safari", "Edg")), None),
        "timestamp": data.get("timestamp"),
        "violations": rules(data.get("violations")), "needs_review": rules(data.get("incomplete")),
        "passed_rules": len(data.get("passes") or []), "inapplicable_rules": len(data.get("inapplicable") or []),
    }


def load_accessibility(path: str | Path) -> dict:
    """Pages checked, with violations, items needing review and rule counts; ``error`` when unreadable."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        runs = data if isinstance(data, list) else [data]
        if not runs or not all(isinstance(r, dict) and "violations" in r and "passes" in r for r in runs):
            raise ValueError("not axe-core results (violations and passes expected)")
        return {"source": str(path), "pages": [_page(r, path.name) for r in runs], "claim": CLAIM, "error": None}
    except (OSError, ValueError, TypeError) as exc:
        return {"source": str(path), "pages": [], "claim": CLAIM, "error": f"{type(exc).__name__}: {exc}"[:300]}


def findings(report: dict) -> list:
    """Engine findings for violations and for items needing review, one per page and rule."""
    from assertiva.models import Finding

    out = []
    for page in report.get("pages") or []:
        for v in page["violations"]:
            out.append(Finding("ACCESSIBILITY_VIOLATION",
                               f"{page['url'] or page['source']}: {v['rule']} ({v['impact'] or 'impact unknown'}) on {v['nodes']} element(s)",
                               {"url": page["url"], "rule": v["rule"], "impact": v["impact"], "wcag": v["wcag"], "targets": v.get("targets", []),
                                "engine": f"{page['engine']} {page['engine_version']}"},
                               severity=_SEVERITY.get(v["impact"] or "", "medium"), recommendation=v["help"]))
        for item in page["needs_review"]:
            out.append(Finding("ACCESSIBILITY_NEEDS_REVIEW",
                               f"{page['url'] or page['source']}: {item['rule']} could not be decided automatically on {item['nodes']} element(s)",
                               {"url": page["url"], "rule": item["rule"], "wcag": item["wcag"], "targets": item.get("targets", [])},
                               severity="low", recommendation="review these elements by hand; an undecided rule is not a pass"))
    return out
