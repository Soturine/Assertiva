"""Offline HTML view of the portfolio report: one table of projects (status, why, counting units kept apart, findings
by severity) and the Assertiva feedback apart. Every value is escaped; no script, no external resource, no paths."""

from __future__ import annotations

import html

_STYLE = """
:root{--bg:#fbfbfa;--fg:#1d1d1b;--muted:#5f5e5a;--line:#dddcd6;--chip:#efeee9;--ok:#2f6b3a;--warn:#8a5a00;--bad:#9b2c2c}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--line:#34332f;--chip:#24231f;
--ok:#7fc28c;--warn:#e0b45c;--bad:#ef8f8f}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px}
main{max-width:1100px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}p.note{color:var(--muted);margin:0 0 20px}
.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;margin-bottom:28px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.st{display:inline-block;padding:1px 8px;border-radius:10px;background:var(--chip);font-size:12px;font-weight:600}
.CURRENT{color:var(--ok)}.STALE,.UNKNOWN{color:var(--warn)}.BLOCKED,.REGRESSION{color:var(--bad)}
code{font-size:12px}
"""


def _e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render(report: dict) -> str:
    rows = []
    for p in report.get("projects", []):
        last = p.get("last_summary") or {}
        units = last.get("units") or {}
        unit_text = "; ".join(f"{_e(k.replace('_', ' '))}: {_e(v)}" for k, v in units.items() if v not in (None, 0)) or "—"
        sev = ", ".join(f"{_e(k)} {_e(v)}" for k, v in sorted((last.get("findings_by_severity") or {}).items())) or "—"
        stacks = ", ".join(_e(s.get("name")) for s in p.get("stacks") or []) or "—"
        rows.append(f"<tr><td><strong>{_e(p['name'])}</strong><br><small>{_e(p.get('phase'))}</small></td>"
                    f"<td><span class='st {_e(p['status'])}'>{_e(p['status'])}</span><br><small>{_e(p.get('why'))}</small></td>"
                    f"<td>{stacks}</td><td>{_e(last.get('tests_status') or 'NOT_RUN')}</td><td>{unit_text}</td><td>{sev}</td>"
                    f"<td>{_e(p.get('audits'))}</td></tr>")
    feedback = []
    for f in report.get("assertiva_feedback", []):
        projects = sorted({s.get("project") for s in f.get("sightings") or []})
        feedback.append(f"<tr><td><code>{_e(f['feedback_id'])}</code></td><td>{_e(f['kind'])}</td><td>{_e(f['rule'])}</td>"
                        f"<td><span class='st {_e(f['state'])}'>{_e(f['state'])}</span></td><td>{_e(', '.join(projects))}</td>"
                        f"<td>{_e(f.get('signature'))}</td></tr>")
    empty = "<tr><td colspan='7'>No project registered.</td></tr>"
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Assertiva portfolio</title><style>{_STYLE}</style></head><body><main>"
        f"<h1>Portfolio</h1><p class='note'>{_e(report.get('note'))}. Generated {_e(report.get('generated_at'))}.</p>"
        "<h2>Projects</h2><div class='wrap'><table><thead><tr><th>Project</th><th>Status</th><th>Stacks (detected)</th>"
        "<th>Tests (last audit)</th><th>Counting units</th><th>Findings</th><th>Audits</th></tr></thead><tbody>"
        + ("".join(rows) or empty) + "</tbody></table></div>"
        "<h2>Feedback about Assertiva</h2><p class='note'>Defects, misses and false positives of the tool itself, kept apart "
        "from the projects' findings.</p><div class='wrap'><table><thead><tr><th>ID</th><th>Kind</th><th>Rule</th><th>State</th>"
        "<th>Seen in</th><th>Signature</th></tr></thead><tbody>"
        + ("".join(feedback) or "<tr><td colspan='6'>No feedback recorded.</td></tr>") + "</tbody></table></div></main></body></html>\n")
