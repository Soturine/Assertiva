"""Continuous dogfood: portable feedback about Assertiva itself, produced by every audit and improve run.

Every audit is a chance to learn where Assertiva measured well, missed something, needed another instrument or was
blocked. That feedback must not depend on the maintainer's setup: no Portfolio registration, no GitHub account, no
network, no provider. Each run writes ``dogfood.json`` and ``dogfood.md`` next to its report (outside the project,
under ``ASSERTIVA_HOME`` or ``--report-dir``), plus an archive copy per run under ``dogfood/`` so one run never
overwrites another run's feedback. A colleague can hand the JSON to the maintainer voluntarily; the maintainer can
import it into a Portfolio (``assertiva portfolio import-feedback``). Nothing is sent anywhere.

Two layers, never confused:

- **mechanical** observations the engine derives from the run itself (an adapter missing for the stack, a run that was
  blocked, a finding the agent disposed as a false positive, an external tool the agent had to use). ``review_mode``
  is ``ENGINE_ONLY`` when no agent assessment is attached, and ``semantic_review`` is then ``NOT_RUN``: the engine
  does not pretend it reviewed itself.
- **agent-led** feedback the auditing agent writes in its assessment (``dogfood``): expected versus observed, scope,
  evidence, a sanitized reproducer, hypotheses kept apart from proven causes. A strong status (``REPRODUCED``,
  ``CONFIRMED``) needs a reproducer with its command and result and at least one evidence reference.

The file is sanitized (credentials, token shapes, e-mail addresses, absolute paths and the project's own name are
replaced) and marked ``LOCAL_ONLY`` / ``reviewed_for_export: false``: a scan is not a privacy guarantee, so a human
reviews it before sharing. ``ASSERTIVA_DOGFOOD=off`` disables writing it; the report then says so.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from . import __version__
from .sanitize import sanitize_message

SCHEMA = "assertiva-dogfood/1"
REVIEW_MODES = ("AGENT_LED", "ENGINE_ONLY", "SKILL_ONLY")
REVIEW_STATUSES = ("COMPLETED_IN_SCOPE", "PARTIAL", "NO_ADDITIONAL_FEEDBACK", "NOT_RUN", "BLOCKED")
OBSERVATION_KINDS = ("defect_candidate", "capability_gap", "confirmed_capability", "improvement_opportunity",
                     "environmental_limit", "inconclusive")
COMPONENTS = ("engine", "skill", "host_provider", "adapter", "document_assurance", "traceability", "orchestration",
              "tooling_discovery", "environment", "report", "ux", "performance", "integration", "packaging", "security",
              "regression")
ENTRY_STATUSES = ("OBSERVED", "REPRODUCED", "CONFIRMED")
STRONG = ("REPRODUCED", "CONFIRMED")
PRIORITIES = ("high", "medium", "low", "unknown")
_SLUG = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
MAX_BYTES = 1_000_000


class DogfoodError(ValueError):
    """The dogfood section or file is invalid; the message says why."""


def _feedback_kinds() -> tuple[str, ...]:
    from .portfolio import FEEDBACK_KINDS

    return FEEDBACK_KINDS


def _text(value: Any, what: str, limit: int = 600) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DogfoodError(f"{what} must be non-empty text")
    return value.strip()[:limit]


def _texts(value: Any, what: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise DogfoodError(f"{what} must be a list of non-empty text")
    return [v.strip()[:600] for v in value]


def _choice(value: Any, allowed: tuple, what: str) -> str:
    if value not in allowed:
        raise DogfoodError(f"{what} must be one of {', '.join(allowed)}")
    return value


def _reproducer(value: Any, what: str) -> dict | None:
    if value is None:
        return None
    if isinstance(value, str):
        return {"description": _text(value, f"{what}: reproducer")}
    if not isinstance(value, dict):
        raise DogfoodError(f"{what}: reproducer is text or an object with description, command, result, fixture")
    out = {"description": _text(value.get("description"), f"{what}: reproducer.description")}
    for key in ("command", "result", "fixture", "revision"):
        if value.get(key) is not None:
            out[key] = _text(value[key], f"{what}: reproducer.{key}")
    return out


def feedback_entry(entry: Any, provenance: str = "AGENT_REPORTED") -> dict:
    """One validated feedback entry. Strong statuses are refused without the evidence they claim."""
    if not isinstance(entry, dict):
        raise DogfoodError("each feedback entry is an object")
    title = _text(entry.get("title"), "feedback title", 200)
    what = f"feedback {title!r}"
    status = _choice(entry.get("status", "OBSERVED"), ENTRY_STATUSES, f"{what}: status")
    out: dict[str, Any] = {
        "kind": _choice(entry.get("kind"), _feedback_kinds(), f"{what}: kind"),
        "component": _choice(entry.get("component"), COMPONENTS, f"{what}: component"),
        "observation_kind": _choice(entry.get("observation_kind"), OBSERVATION_KINDS, f"{what}: observation_kind"),
        "status": status, "title": title,
        "rule": _text(entry.get("rule"), f"{what}: rule (finding code, engine rule or Skill section)", 120),
        "signature": _text(entry.get("signature"), f"{what}: signature (sanitized dedup key)", 300),
        "expected": _text(entry.get("expected"), f"{what}: expected"),
        "observed": _text(entry.get("observed"), f"{what}: observed"),
        "scope": _text(entry.get("scope"), f"{what}: scope"),
        "evidence": _texts(entry.get("evidence"), f"{what}: evidence"),
        "provenance": provenance,
    }
    if out["observation_kind"] == "confirmed_capability":
        raise DogfoodError(f"{what}: a confirmed capability goes in confirmed_capabilities, not in feedback")
    for key in ("impact", "cause_hypothesis", "cost_benefit"):
        if entry.get(key) is not None:
            out[key] = _text(entry[key], f"{what}: {key}")
    out["cause_proven"] = bool(entry.get("cause_proven"))
    if out["cause_proven"] and not out.get("cause_hypothesis"):
        raise DogfoodError(f"{what}: cause_proven names the cause in cause_hypothesis")
    out["priority"] = _choice(entry.get("priority", "unknown"), PRIORITIES, f"{what}: priority")
    out["alternatives"] = _texts(entry.get("alternatives"), f"{what}: alternatives")
    out["acceptance"] = _texts(entry.get("acceptance"), f"{what}: acceptance")
    out["regression_required"] = bool(entry.get("regression_required"))
    reproducer = _reproducer(entry.get("reproducer"), what)
    if reproducer:
        out["reproducer"] = reproducer
    tool = entry.get("tool")
    if tool is not None:
        if not isinstance(tool, dict) or not tool.get("name"):
            raise DogfoodError(f"{what}: tool is an object with name and version")
        out["tool"] = {"name": _text(tool["name"], f"{what}: tool.name", 120),
                       "version": str(tool.get("version") or "UNKNOWN")[:60]}
    research = entry.get("research") or []
    if not isinstance(research, list) or not all(isinstance(r, dict) and r.get("url") for r in research):
        raise DogfoodError(f"{what}: research lists objects with url, title, accessed, conclusion")
    out["research"] = [{k: str(r[k])[:300] for k in ("url", "title", "accessed", "applies_to", "conclusion") if r.get(k)}
                       for r in research]
    if status in STRONG:
        if not out["evidence"]:
            raise DogfoodError(f"{what}: {status} needs evidence references")
        if not reproducer or not reproducer.get("command") or not reproducer.get("result"):
            raise DogfoodError(f"{what}: {status} needs a reproducer with the command that shows it and its result")
    if status == "CONFIRMED" and not out["cause_proven"] and out["observation_kind"] == "defect_candidate":
        raise DogfoodError(f"{what}: CONFIRMED defect needs its proven cause (cause_proven with cause_hypothesis); "
                           "otherwise it is REPRODUCED")
    return out


def _capability(entry: Any) -> dict:
    if not isinstance(entry, dict):
        raise DogfoodError("each confirmed capability is an object")
    capability = _text(entry.get("capability"), "confirmed capability", 200)
    evidence = _texts(entry.get("evidence"), f"capability {capability!r}: evidence")
    if not evidence:
        raise DogfoodError(f"capability {capability!r}: a confirmed capability needs its evidence, not praise")
    return {"capability": capability, "component": _choice(entry.get("component", "engine"), COMPONENTS, "capability component"),
            "scope": _text(entry.get("scope"), f"capability {capability!r}: scope"), "evidence": evidence}


def validate_agent_section(data: Any) -> dict | None:
    """The assessment's ``dogfood`` section, validated (None when absent)."""
    if data is None:
        return None
    if not isinstance(data, dict):
        raise DogfoodError("dogfood must be an object")
    status = _choice(data.get("review_status"), REVIEW_STATUSES, "dogfood review_status")
    feedback = [feedback_entry(e) for e in data.get("feedback") or []]
    capabilities = [_capability(e) for e in data.get("confirmed_capabilities") or []]
    if status == "NO_ADDITIONAL_FEEDBACK" and feedback:
        raise DogfoodError("NO_ADDITIONAL_FEEDBACK means the review found nothing to add; it has no feedback entries")
    if status in ("COMPLETED_IN_SCOPE", "PARTIAL") and not (feedback or capabilities):
        raise DogfoodError(f"dogfood {status} records what the review found (feedback or confirmed capabilities); "
                           "a review that found nothing is NO_ADDITIONAL_FEEDBACK")
    agent = data.get("agent") or {}
    if not isinstance(agent, dict):
        raise DogfoodError("dogfood agent is an object (host, provider, model, capabilities)")
    capabilities_declared = agent.get("capabilities") or {}
    if not isinstance(capabilities_declared, dict):
        raise DogfoodError("dogfood agent.capabilities maps a capability (vision, pdf, web, shell, structured_output) "
                           "to OBSERVED, DECLARED, UNAVAILABLE or UNKNOWN")
    out_agent = {k: str(agent.get(k) or "unknown")[:120] for k in ("host", "provider", "model")}
    out_agent["capabilities"] = {str(k)[:40]: _choice(v, ("OBSERVED", "DECLARED", "UNAVAILABLE", "UNKNOWN"),
                                                       f"agent capability {k}") for k in capabilities_declared for v in [capabilities_declared[k]]}
    return {"review_status": status, "scope": _text(data.get("scope", "this audit run"), "dogfood scope"),
            "feedback": feedback, "confirmed_capabilities": capabilities,
            "not_evaluated": _texts(data.get("not_evaluated"), "dogfood not_evaluated"),
            "unknowns": _texts(data.get("unknowns"), "dogfood unknowns"), "agent": out_agent}


# --- mechanical observations from the run ----------------------------------------------------------------------------

def _mechanical(report: dict) -> tuple[list[dict], list[dict]]:
    """(feedback, observations) the engine can state about itself from this run alone, without semantic review."""
    feedback, observations = [], []
    language = (((report.get("project") or {}).get("technologies") or {}).get("language") or {}).get("name")
    codes = {f.get("code") for f in report.get("findings") or []}
    if "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED" in codes:
        feedback.append(feedback_entry({
            "kind": "UNSUPPORTED", "component": "adapter", "observation_kind": "capability_gap", "status": "OBSERVED",
            "title": f"No executable test adapter for {language or 'this stack'}",
            "rule": "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED", "signature": f"no executable adapter for {language or 'unknown stack'}",
            "expected": "Runtime evidence for the project's tests", "observed": "The engine recognized no runner it can execute",
            "scope": "this run", "evidence": ["finding NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED"],
        }, provenance="ENGINE_DERIVED"))
    for finding in report.get("findings") or []:
        disposition = (finding.get("assessment") or {})
        if finding.get("origin") == "engine" and disposition.get("disposition") == "FALSE_POSITIVE":
            feedback.append(feedback_entry({
                "kind": "FALSE_POSITIVE", "component": "engine", "observation_kind": "defect_candidate", "status": "OBSERVED",
                "title": f"{finding['code']} disposed as a false positive", "rule": finding["code"],
                "signature": f"{finding['code']} false positive",
                "expected": "The engine signal holds for the items it names",
                "observed": "The auditing agent reviewed the items and rejected the claim: " + disposition.get("rationale", ""),
                "scope": f"{(disposition.get('scope') or {}).get('reviewed', '?')} item(s) reviewed in this run",
                "evidence": list(disposition.get("evidence") or []),
                "cause_hypothesis": "heuristic signal outside its validity (see rationale)",
            }, provenance="ENGINE_DERIVED_FROM_ASSESSMENT"))
    for receipt in report.get("external_executions") or []:
        if receipt.get("purpose") in ("tests", "mutation", "coverage") and receipt.get("status") != "UNKNOWN":
            feedback.append(feedback_entry({
                "kind": "UNSUPPORTED", "component": "tooling_discovery", "observation_kind": "capability_gap", "status": "OBSERVED",
                "title": f"Agent used {receipt['tool']} for {receipt['ecosystem']} {receipt['purpose']} outside the engine",
                "rule": "external-execution", "signature": f"external {receipt['purpose']} {receipt['ecosystem']} {receipt['tool']}",
                "expected": "Native engine evidence, or none needed",
                "observed": f"External run recorded ({receipt['status']}, link {receipt['link']})",
                "scope": "this run", "evidence": [f"external execution {receipt['id']}"],
                "tool": {"name": receipt["tool"], "version": receipt.get("tool_version")},
                "cost_benefit": "unknown: decide on frequency across audits before adding a native adapter",
            }, provenance="ENGINE_DERIVED_FROM_RECEIPT"))
    for run in ((report.get("states") or {}).get("current") or {}).get("runs") or []:
        if run.get("status") == "BLOCKED":
            observations.append({"component": "environment", "observation_kind": "environmental_limit",
                                 "title": f"{run.get('adapter')} run BLOCKED",
                                 "basis": (run.get("limitations") or ["no reason recorded"])[0]})
    for source in (report.get("context") or {}).get("sources") or []:
        if "TEXT_ONLY" in source.get("labels", []):
            observations.append({"component": "document_assurance", "observation_kind": "capability_gap",
                                 "title": f"source {source['id']} read as text only although it has "
                                          + ", ".join(source["coverage"]["unread_modalities"]),
                                 "basis": "context source labels"})
    return feedback, observations


def _scrub(value: Any, names: list[str]) -> Any:
    if isinstance(value, str):
        out = sanitize_message(value, limit=2000) or ""
        for name in names:
            if name and len(name) >= 3:
                out = re.sub(re.escape(name), "<project>", out, flags=re.IGNORECASE)
        return out
    if isinstance(value, list):
        return [_scrub(v, names) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v, names) for k, v in value.items()}
    return value


def build(report: dict) -> dict:
    """The dogfood document for one report (audit or improve), sanitized."""
    assessment = report.get("assessment") or {}
    agent_section = assessment.get("dogfood")
    mechanical, observations = _mechanical(report)
    if agent_section:
        mode, status = "AGENT_LED", agent_section["review_status"]
    elif assessment:
        mode, status = "AGENT_LED", "NOT_RUN"
    else:
        mode, status = "ENGINE_ONLY", "NOT_RUN"
    run_id = report.get("run_id") or report.get("generated_at") or "unknown"
    project = report.get("project") or {}
    manifest_engine = (report.get("execution_manifest") or {}).get("engine") or {}
    doc = {
        "schema": SCHEMA,
        "report_id": "DF-" + hashlib.sha256(f"{run_id}".encode()).hexdigest()[:12],
        "run_id": run_id,
        "workflow": report.get("workflow"),
        "generated_at": report.get("generated_at"),
        "review_mode": mode,
        "review_status": status,
        "semantic_review": "DONE" if agent_section and status in ("COMPLETED_IN_SCOPE", "PARTIAL", "NO_ADDITIONAL_FEEDBACK") else "NOT_RUN",
        "scope": (agent_section or {}).get("scope") or "this run",
        "engine": {"version": manifest_engine.get("assertiva_version") or __version__, "revision": manifest_engine.get("revision")},
        "skill": {"revision": None, "digest": None},
        "agent": (agent_section or {}).get("agent") or {"host": "unknown", "provider": "unknown", "model": "unknown", "capabilities": {}},
        "environment": {"os": platform.system() or "unknown", "runtime": f"CPython {sys.version_info.major}.{sys.version_info.minor}"},
        "provenance": "AGENT_REPORTED" if agent_section else "ENGINE_DERIVED",
        "feedback": (agent_section or {}).get("feedback", []) + mechanical,
        "mechanical_observations": observations,
        "confirmed_capabilities": (agent_section or {}).get("confirmed_capabilities", []),
        "not_evaluated": (agent_section or {}).get("not_evaluated", []),
        "unknowns": (agent_section or {}).get("unknowns", []),
        "sharing": {"classification": "LOCAL_ONLY", "reviewed_for_export": False,
                    "note": "sanitized automatically; review it before sharing: a scan is not a privacy guarantee"},
    }
    if mode == "ENGINE_ONLY":
        doc["unknowns"] = doc["unknowns"] + ["no semantic review of Assertiva was attached to this run (engine-only)"]
    names = [project.get("name") or "", Path(str(project.get("root") or "")).name]
    doc = _scrub(doc, names)
    for entry in doc["feedback"]:
        from .portfolio import feedback_id

        entry["feedback_id"] = feedback_id(entry["kind"], entry["rule"], entry["signature"])
    return doc


def validate_document(doc: Any) -> dict:
    """A dogfood document read from a file (a colleague's, CI's, another machine's): schema, size and strong-status
    rules re-checked. Its content is data, never instructions."""
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise DogfoodError(f"not an {SCHEMA} document (schema {doc.get('schema') if isinstance(doc, dict) else None!r})")
    if not re.fullmatch(r"DF-[0-9a-f]{12}", str(doc.get("report_id") or "")):
        raise DogfoodError("report_id must look like DF-<12 hex>")
    _choice(doc.get("review_mode"), REVIEW_MODES, "review_mode")
    _choice(doc.get("review_status"), REVIEW_STATUSES, "review_status")
    feedback = doc.get("feedback")
    if not isinstance(feedback, list):
        raise DogfoodError("feedback must be a list")
    checked = []
    for entry in feedback:
        provenance = entry.get("provenance", "AGENT_REPORTED") if isinstance(entry, dict) else "AGENT_REPORTED"
        item = feedback_entry(entry, provenance=str(provenance)[:60])
        from .portfolio import feedback_id

        item["feedback_id"] = feedback_id(item["kind"], item["rule"], item["signature"])
        checked.append(item)
    return {**doc, "feedback": checked}


def load_document(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise DogfoodError(f"{path} is not a file")
    if path.stat().st_size > MAX_BYTES:
        raise DogfoodError(f"{path.name} is larger than {MAX_BYTES} bytes; a dogfood document is small by design")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DogfoodError(f"cannot read {path.name}: {exc}") from exc
    return validate_document(data)


# --- rendering and writing -------------------------------------------------------------------------------------------

def _md_escape(text: Any) -> str:
    return str(text).replace("<", "&lt;").replace(">", "&gt;").replace("|", "\\|").replace("\n", " ")


def to_markdown(doc: dict) -> str:
    lines = [f"# Feedback about Assertiva · {doc['report_id']}", "",
             f"- Run: `{_md_escape(doc['run_id'])}` ({_md_escape(doc.get('workflow'))}), engine {_md_escape(doc['engine']['version'])}",
             f"- Review: **{doc['review_mode']}**, {doc['review_status']} (semantic review: {doc['semantic_review']})",
             f"- Scope: {_md_escape(doc['scope'])}",
             f"- Agent: host {_md_escape(doc['agent'].get('host'))}, provider {_md_escape(doc['agent'].get('provider'))}, "
             f"model {_md_escape(doc['agent'].get('model'))}",
             f"- Sharing: {doc['sharing']['classification']}, reviewed for export: {str(doc['sharing']['reviewed_for_export']).lower()} "
             "(review before sharing; nothing was sent anywhere)", "",
             "This is feedback about the tool, not about the audited project's defects.", ""]
    lines += ["## Feedback", ""]
    if not doc["feedback"]:
        lines.append("No feedback entries" + (" (the review found nothing to add in its scope; this does not prove the "
                                              "absence of defects)." if doc["review_status"] == "NO_ADDITIONAL_FEEDBACK" else "."))
    for entry in doc["feedback"]:
        lines += [f"### {_md_escape(entry['title'])}", "",
                  f"- `{entry.get('feedback_id', '?')}` · {entry['kind']} · {entry['component']} · {entry['observation_kind']} · "
                  f"{entry['status']} · priority {entry['priority']} · {entry['provenance']}",
                  f"- Rule: `{_md_escape(entry['rule'])}`; signature: {_md_escape(entry['signature'])}",
                  f"- Expected: {_md_escape(entry['expected'])}", f"- Observed: {_md_escape(entry['observed'])}",
                  f"- Scope: {_md_escape(entry['scope'])}"]
        if entry.get("impact"):
            lines.append(f"- Impact: {_md_escape(entry['impact'])}")
        if entry.get("cause_hypothesis"):
            lines.append(f"- Cause ({'proven' if entry['cause_proven'] else 'hypothesis'}): {_md_escape(entry['cause_hypothesis'])}")
        if entry.get("reproducer"):
            r = entry["reproducer"]
            lines.append(f"- Reproducer: {_md_escape(r['description'])}" + (f"; command `{_md_escape(r['command'])}`" if r.get("command") else "")
                         + (f"; result: {_md_escape(r['result'])}" if r.get("result") else ""))
        if entry.get("tool"):
            lines.append(f"- Tool: {_md_escape(entry['tool']['name'])} {_md_escape(entry['tool']['version'])}")
        lines += [f"- Evidence: {_md_escape(e)}" for e in entry["evidence"]]
        lines += [f"- Alternative: {_md_escape(a)}" for a in entry["alternatives"]]
        lines += [f"- Acceptance: {_md_escape(a)}" for a in entry["acceptance"]]
        lines += [f"- Research: {_md_escape(r.get('title') or r['url'])} <{_md_escape(r['url'])}> ({_md_escape(r.get('accessed', '?'))}): "
                  f"{_md_escape(r.get('conclusion', ''))}" for r in entry["research"]]
        if entry.get("cost_benefit"):
            lines.append(f"- Cost/benefit: {_md_escape(entry['cost_benefit'])}")
        lines.append("")
    lines += ["## Confirmed capabilities", ""]
    lines += [f"- **{_md_escape(c['capability'])}** ({c['component']}; {_md_escape(c['scope'])}): "
              + "; ".join(_md_escape(e) for e in c["evidence"]) for c in doc["confirmed_capabilities"]] or ["None recorded."]
    lines += ["", "## Mechanical observations (engine, no semantic review)", ""]
    lines += [f"- {o['observation_kind']} · {o['component']}: {_md_escape(o['title'])} ({_md_escape(o['basis'])})"
              for o in doc["mechanical_observations"]] or ["None."]
    lines += ["", "## Not evaluated and unknowns", ""]
    lines += [f"- Not evaluated: {_md_escape(v)}" for v in doc["not_evaluated"]]
    lines += [f"- Unknown: {_md_escape(v)}" for v in doc["unknowns"]] or ["None recorded."]
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def write(report: dict, directory: Path, name: str) -> dict:
    """Write the run's dogfood files and return the summary the report carries. A failure never loses the report."""
    if os.environ.get("ASSERTIVA_DOGFOOD", "").strip().lower() in ("off", "0", "false", "no"):
        return {"export": "DISABLED", "reason": "ASSERTIVA_DOGFOOD=off"}
    try:
        doc = build(report)
        text = json.dumps(doc, indent=1, ensure_ascii=False)
        _atomic_write(directory / "dogfood" / f"{doc['report_id']}.json", text)
        _atomic_write(directory / f"{name}.dogfood.json", text)
        _atomic_write(directory / f"{name}.dogfood.md", to_markdown(doc))
    except (OSError, DogfoodError, KeyError, TypeError, ValueError) as exc:
        return {"export": "BLOCKED", "reason": sanitize_message(f"{type(exc).__name__}: {exc}")}
    return {"export": "WRITTEN", "report_id": doc["report_id"], "review_mode": doc["review_mode"],
            "review_status": doc["review_status"], "semantic_review": doc["semantic_review"],
            "feedback": len(doc["feedback"]), "confirmed_capabilities": len(doc["confirmed_capabilities"]),
            "mechanical_observations": len(doc["mechanical_observations"]),
            "files": {"json": f"{name}.dogfood.json", "markdown": f"{name}.dogfood.md", "archive": f"dogfood/{doc['report_id']}.json"},
            "entries": [{"feedback_id": e["feedback_id"], "title": e["title"], "kind": e["kind"], "component": e["component"],
                         "observation_kind": e["observation_kind"], "status": e["status"], "provenance": e["provenance"]}
                        for e in doc["feedback"][:20]]}
