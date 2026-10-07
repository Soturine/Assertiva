"""The auditing agent's assessment of one audit run, joined to that run's report.

The engine observes and measures; the agent reasons over the engine's evidence and everything else it read or ran.
An assessment carries the agent's conclusion, a disposition for engine findings it reviewed and the findings it
discovered itself. It is validated against the run it names and merged into the same report model, so the canonical
page shows one coherent story. Engine findings are never removed and their severity, summary and evidence are never
rewritten: a disposition sits next to them and may restate the priority, with its rationale and evidence.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .report import recommendations

DISPOSITIONS = ("CONFIRMED", "PARTIAL", "CONTEXTUAL", "FALSE_POSITIVE", "UNRESOLVED")
SUBJECT_DISPOSITIONS = ("CONFIRMED", "CONTEXTUAL", "FALSE_POSITIVE", "UNRESOLVED")
PRIORITIES = ("high", "medium", "low", "info")
BASES = ("OBSERVED", "DECLARED", "INFERRED")
WHOLE = ("CONFIRMED", "FALSE_POSITIVE")  # verdicts about every item of a finding
_SLUG = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class AssessmentError(ValueError):
    """The assessment cannot be attached; the message says why."""


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AssessmentError(f"{what} must be non-empty text")
    return value.strip()


def _refs(value: Any, what: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v.strip() for v in value):
        raise AssessmentError(f"{what}: evidence must be a non-empty list of references (file:line, command, report field)")
    return [v.strip() for v in value]


def _priority(value: Any, what: str) -> str:
    if value not in PRIORITIES:
        raise AssessmentError(f"{what}: priority must be one of {', '.join(PRIORITIES)}")
    return value


def item_count(finding: dict) -> int | None:
    """How many items an engine finding is about, when its evidence says so."""
    evidence = finding.get("evidence") or {}
    if isinstance(evidence.get("count"), int):
        return evidence["count"]
    lists = [v for v in evidence.values() if isinstance(v, list)]
    return len(lists[0]) if len(lists) == 1 else None


def _disposition(entry: Any, findings: dict[str, dict]) -> dict:
    if not isinstance(entry, dict):
        raise AssessmentError("each disposition must be an object")
    target = entry.get("finding")
    if target not in findings:
        raise AssessmentError(f"no finding {target!r} in this run; dispositions name an engine finding id")
    what = f"disposition for {target}"
    disposition = entry.get("disposition")
    if disposition not in DISPOSITIONS:
        raise AssessmentError(f"{what}: disposition must be one of {', '.join(DISPOSITIONS)}")
    out = {"finding": target, "disposition": disposition, "rationale": _text(entry.get("rationale"), f"{what}: rationale"),
           "evidence": _refs(entry.get("evidence"), what)}
    if disposition == "FALSE_POSITIVE":
        if "priority" in entry:
            raise AssessmentError(f"{what}: a false positive has no priority; it leaves the action plan")
    elif "priority" in entry:
        out["priority"] = _priority(entry["priority"], what)
    elif disposition == "CONTEXTUAL":
        raise AssessmentError(f"{what}: CONTEXTUAL restates the impact, so it needs a priority")
    items = item_count(findings[target])
    scope = entry.get("scope")
    if scope is not None:
        if not (isinstance(scope, dict) and isinstance(scope.get("reviewed"), int) and isinstance(scope.get("of"), int)
                and 0 < scope["reviewed"] <= scope["of"]):
            raise AssessmentError(f"{what}: scope is {{\"reviewed\": n, \"of\": total}} with 0 < n <= total")
        if items is not None and scope["of"] != items:
            raise AssessmentError(f"{what}: the finding has {items} items, scope says {scope['of']}")
        out["scope"] = {"reviewed": scope["reviewed"], "of": scope["of"]}
    if disposition in WHOLE:
        if scope is None and (items or 0) > 1:
            raise AssessmentError(f"{what}: {disposition} for the whole finding needs every item reviewed: "
                                  f"give scope {{\"reviewed\": {items}, \"of\": {items}}}, or use PARTIAL / UNRESOLVED")
        if scope is not None and scope["reviewed"] < scope["of"]:
            raise AssessmentError(f"{what}: reviewed {scope['reviewed']} of {scope['of']}; {disposition} needs every item "
                                  "reviewed, so record the reviewed items with PARTIAL or UNRESOLVED")
    subjects = entry.get("subjects")
    if subjects is not None:
        if not isinstance(subjects, list) or not subjects:
            raise AssessmentError(f"{what}: subjects must be a non-empty list")
        out["subjects"] = []
        for subject in subjects:
            if not isinstance(subject, dict) or subject.get("disposition") not in SUBJECT_DISPOSITIONS:
                raise AssessmentError(f"{what}: each subject needs a subject and a disposition among {', '.join(SUBJECT_DISPOSITIONS)}")
            item = {"subject": _text(subject.get("subject"), f"{what}: subject"), "disposition": subject["disposition"]}
            if subject.get("note"):
                item["note"] = _text(subject["note"], f"{what}: note")
            out["subjects"].append(item)
    if disposition == "PARTIAL" and not out.get("subjects"):
        raise AssessmentError(f"{what}: PARTIAL names the items it confirms or rejects in subjects")
    return out


def _agent_finding(entry: Any) -> dict:
    if not isinstance(entry, dict):
        raise AssessmentError("each finding must be an object")
    slug = entry.get("id")
    if not isinstance(slug, str) or not _SLUG.fullmatch(slug):
        raise AssessmentError("a finding id is a short lowercase slug (letters, digits, '.', '_', '-')")
    what = f"finding {slug}"
    if entry.get("basis") not in BASES:
        raise AssessmentError(f"{what}: basis must be one of {', '.join(BASES)} (how you know it)")
    out = {
        "id": f"agent:{slug}", "code": "AGENT_FINDING", "origin": "agent",
        "title": _text(entry.get("title"), f"{what}: title"),
        "summary": _text(entry.get("claim"), f"{what}: claim"),
        "basis": entry["basis"],
        "evidence": {"refs": _refs(entry.get("evidence"), what)},
    }
    out["severity"] = out["priority"] = _priority(entry.get("priority"), what)
    for key in ("why", "recommendation"):
        if entry.get(key):
            out[key] = _text(entry[key], f"{what}: {key}")
    return out


def strip_assessment(report: dict) -> dict:
    """The engine's own report for the run: agent findings, dispositions and restated priorities removed."""
    base = copy.deepcopy(report)
    base.pop("assessment", None)
    base["findings"] = [f for f in base["findings"] if f.get("origin") != "agent"]
    for finding in base["findings"]:
        finding.pop("assessment", None)
        finding["priority"] = finding["severity"]
    base["recommendations"] = recommendations(base["findings"])
    return base


def apply_assessment(report: dict, data: Any) -> dict:
    """A new report: the run's engine report plus this assessment. Raises AssessmentError when it does not fit the run."""
    if not isinstance(data, dict):
        raise AssessmentError("the assessment must be a JSON object")
    if report.get("workflow") != "audit" or not report.get("run_id"):
        raise AssessmentError("assessments attach to an audit report that has a run_id (run `assertiva audit` again)")
    if data.get("run_id") != report["run_id"]:
        raise AssessmentError(f"the assessment was written for another run ({data.get('run_id')!r}); "
                              f"the latest audit of this project is {report['run_id']!r}")
    out = strip_assessment(report)
    by_id = {f["id"]: f for f in out["findings"]}
    dispositions = [_disposition(entry, by_id) for entry in data.get("dispositions") or []]
    targets = [d["finding"] for d in dispositions]
    if len(targets) != len(set(targets)):
        raise AssessmentError("a finding is dispositioned more than once")
    agent = [_agent_finding(entry) for entry in data.get("findings") or []]
    ids = [f["id"] for f in agent]
    if len(ids) != len(set(ids)):
        raise AssessmentError("an agent finding id is used more than once")
    unknowns = data.get("unknowns") or []
    if not isinstance(unknowns, list) or not all(isinstance(u, str) and u.strip() for u in unknowns):
        raise AssessmentError("unknowns must be a list of non-empty text")

    for d in dispositions:
        finding = by_id[d["finding"]]
        finding["assessment"] = {k: v for k, v in d.items() if k != "finding"}
        finding["priority"] = "none" if d["disposition"] == "FALSE_POSITIVE" else d.get("priority", finding["severity"])
    out["findings"].extend(agent)
    recs = recommendations([f for f in out["findings"] if f["origin"] == "engine"])
    withdrawn = {f["id"] for f in out["findings"] if f["priority"] == "none"}
    for rec in recs:
        if rec["finding_id"] in withdrawn:
            rec["status"] = "WITHDRAWN"
    recs += [{"finding": f["code"], "finding_id": f["id"], "recommendation": f["recommendation"], "status": "PROPOSED", "origin": "agent"}
             for f in agent if f.get("recommendation")]
    out["recommendations"] = recs
    out["assessment"] = {
        "source": "agent",
        "attached_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": _text(data.get("summary"), "summary"),
        "lang": data.get("lang") if isinstance(data.get("lang"), str) else None,
        "unknowns": [u.strip() for u in unknowns],
        "dispositions": len(dispositions),
        "findings": len(agent),
    }
    return out


def load_assessment(path: str | Path) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssessmentError(f"cannot read the assessment {path}: {exc}") from exc
