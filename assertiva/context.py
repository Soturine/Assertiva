"""Documentary context and functional traceability that the auditing agent attaches to one audit run.

The agent decides which sources define the intended behavior, reads them with whatever its host offers (native text
or visual reading, rendered pages, an extractor) and says what it read. The engine checks only what it can check
mechanically:

- a source path stays inside the project (no ``..``, no link that leaves it) and the file exists;
- the source's SHA-256 now, and whether the digest the agent read still matches (``STALE`` when not);
- the number of units of a format it can count without a dependency (PDF pages), so a reviewed range and a cited
  locator must fall inside it;
- a citation points at a unit the agent says it reviewed (citing page 2 after reading page 1 is refused);
- a coverage status is no stronger than the evidence linked to it (a mapped test is not an executed one, an executed
  pass is not a demonstrated protection).

Method and completeness are separate dimensions. ``labels`` derives the familiar names (INVENTORIED, READ_NATIVE,
READ_VISUAL, READ_PARTIAL, TEXT_ONLY, UNSUPPORTED, BLOCKED, STALE, …) from them. Reading itself stays
``AGENT_REPORTED``: a digest proves which bytes were cited, never that they were understood. Nothing here reads a
source marked private, follows a URI or runs anything a document says.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

SOURCE_KINDS = ("requirements", "specification", "acceptance_criteria", "adr", "test_plan", "contract", "schema",
                "diagram", "manual", "readme", "issue", "policy", "regulation", "prototype", "spreadsheet", "presentation",
                "other")
AVAILABILITY = ("AVAILABLE", "MISSING", "INACCESSIBLE", "PRIVATE", "OUT_OF_SCOPE", "UNSUPPORTED_FORMAT", "BLOCKED")
AUTHORITY = ("APPROVED", "POLICY", "REGULATION", "DRAFT", "PROPOSAL", "SUPERSEDED", "CONFLICTING", "OBSERVED_BEHAVIOR",
             "CHARACTERIZATION", "RISK_HYPOTHESIS", "EXPLORATORY", "UNKNOWN")
METHODS = ("HOST_NATIVE_TEXT", "HOST_NATIVE_VISUAL", "RENDERED_PAGES", "TEXT_EXTRACTION", "OCR", "STRUCTURED_PARSE",
           "SPREADSHEET_FORMULAS", "PROVIDER_REVIEW", "USER_PROVIDED_SUMMARY")
NATIVE_METHODS = ("HOST_NATIVE_TEXT", "HOST_NATIVE_VISUAL")
MODALITIES = ("text", "visual", "table", "formula", "diagram", "audio", "video")
UNITS = ("page", "slide", "sheet", "section", "line", "file", "minute")
RELATIONS = ("validates", "covers", "observes", "simulates", "characterizes", "reproduces")
ORACLES = ("STRONG", "PARTIAL", "WEAK", "NONE")
PROTECTION_KINDS = ("NEGATIVE_CONTROL", "MUTANT", "ENGINE_MUTATION")
VERIFIED_BASES = ("ENGINE_VERIFIED", "IMPROVE_REPORT_VERIFIED")
# Coverage states a behavior can be claimed in, strongest first; STALE is the engine's, never claimed.
COVERAGE_STATES = ("PROVEN_IN_SCOPE", "OBSERVED_PASS", "PARTIAL", "WEAK", "CHARACTERIZATION_ONLY", "NOT_EVIDENCED",
                   "UNKNOWN", "BLOCKED", "NOT_APPLICABLE")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,79}")
_RANGE = re.compile(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$")
_LOCATOR = re.compile(r"^(page|slide|line|sheet|section|figure|table|cell|node|edge|time|anchor)s?:(.+)$")
_MAX_HASH_BYTES = 256 * 1024 * 1024


class ContextError(ValueError):
    """The context section cannot be attached; the message says why."""


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextError(f"{what} must be non-empty text")
    return value.strip()


def _opt_text(entry: dict, key: str, what: str) -> str | None:
    return _text(entry[key], f"{what}: {key}") if entry.get(key) is not None else None


def _choice(value: Any, allowed: tuple, what: str) -> str:
    if value not in allowed:
        raise ContextError(f"{what} must be one of {', '.join(allowed)}")
    return value


def _choices(value: Any, allowed: tuple, what: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(v in allowed for v in value):
        raise ContextError(f"{what} must be a list of {', '.join(allowed)}")
    return sorted(set(value), key=allowed.index)


def _ident(value: Any, what: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ContextError(f"{what} must be a short id (letters, digits, '.', '_', ':', '-')")
    return value


def parse_ranges(values: Any, what: str) -> list[tuple[int, int]]:
    """["1-3", "5"] -> [(1, 3), (5, 5)], merged and sorted; 1-based and inclusive."""
    if values is None:
        return []
    if not isinstance(values, list):
        raise ContextError(f"{what} must be a list of ranges such as \"1-3\" or \"5\"")
    spans = []
    for value in values:
        match = _RANGE.match(str(value))
        if not match:
            raise ContextError(f"{what}: {value!r} is not a range such as \"1-3\" or \"5\"")
        start, end = int(match.group(1)), int(match.group(2) or match.group(1))
        if start < 1 or end < start:
            raise ContextError(f"{what}: {value!r} must be 1-based and increasing")
        spans.append((start, end))
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _count(spans: list[tuple[int, int]]) -> int:
    return sum(end - start + 1 for start, end in spans)


def _covers(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(a <= start and end <= b for a, b in spans)


def pdf_page_count(data: bytes) -> int | None:
    """Pages of a PDF from its page-tree objects, without a PDF library; None when the file does not show them plainly
    (compressed object streams, encryption): unknown, never guessed."""
    if not data.startswith(b"%PDF-"):
        return None
    if b"/ObjStm" in data or b"/Encrypt" in data:
        return None
    pages = len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))
    return pages or None


def _inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip() or "\x00" in relative:
        raise ContextError("a source path must be non-empty text")
    candidate = Path(relative)
    if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
        raise ContextError(f"source path {relative!r} must be relative to the project, without '..' "
                           "(a source outside the project is declared with \"external\": true and is not read)")
    resolved = (root / candidate).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ContextError(f"source path {relative!r} leaves the project through a link; it is not read")
    return resolved


def _digest(path: Path) -> tuple[str | None, int | None, bytes | None]:
    size = path.stat().st_size
    if size > _MAX_HASH_BYTES:
        return None, size, None
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), size, data


def labels(source: dict) -> list[str]:
    """Familiar read-state names derived from the separate dimensions (never claimed directly)."""
    out = []
    availability, review, coverage = source["availability"], source.get("review") or {}, source.get("coverage") or {}
    if availability == "PRIVATE":
        out.append("PRIVATE")
    elif availability == "OUT_OF_SCOPE":
        out.append("OUT_OF_SCOPE")
    elif availability == "UNSUPPORTED_FORMAT":
        out.append("UNSUPPORTED")
    elif availability in ("BLOCKED", "INACCESSIBLE", "MISSING"):
        out.append("BLOCKED")
    if source.get("authority") == "SUPERSEDED":
        out.append("SUPERSEDED")
    if (source.get("verification") or {}).get("digest") == "MISMATCH":
        out.append("STALE")
    if availability != "AVAILABLE":
        return out
    reviewed = coverage.get("reviewed") or 0
    if not reviewed:
        out.append("INVENTORIED")
        out.append("NOT_READ")
        return out
    methods, read = set(review.get("methods") or []), set(review.get("modalities_read") or [])
    if methods & set(NATIVE_METHODS):
        out.append("READ_NATIVE")
    if read & {"visual", "diagram"}:
        out.append("READ_VISUAL")
    if not coverage.get("complete"):
        out.append("READ_PARTIAL")
    present = set(source.get("modalities_present") or [])
    if read <= {"text"} and present - {"text"}:
        out.append("TEXT_ONLY")
    return out


def _source(entry: Any, root: Path) -> dict:
    if not isinstance(entry, dict):
        raise ContextError("each source must be an object")
    sid = _ident(entry.get("id"), "source id")
    what = f"source {sid}"
    out: dict[str, Any] = {"id": sid, "title": _text(entry.get("title"), f"{what}: title"),
                           "kind": _choice(entry.get("kind", "other"), SOURCE_KINDS, f"{what}: kind"),
                           "availability": _choice(entry.get("availability", "AVAILABLE"), AVAILABILITY, f"{what}: availability"),
                           "authority": _choice(entry.get("authority", "UNKNOWN"), AUTHORITY, f"{what}: authority"),
                           "modalities_present": _choices(entry.get("modalities_present"), MODALITIES, f"{what}: modalities_present")}
    for key in ("revision", "effective", "approved_by", "note"):
        value = _opt_text(entry, key, what)
        if value:
            out[key] = value
    external = bool(entry.get("external"))
    verification: dict[str, Any] = {"read_by": "AGENT_REPORTED"}
    total_engine = None
    path = entry.get("path")
    if path is not None and external:
        raise ContextError(f"{what}: an external source names a uri (or a label), not a project path")
    if path is not None:
        out["path"] = Path(path).as_posix()
        if out["availability"] == "PRIVATE":
            verification["digest"] = "NOT_READ_PRIVATE"
        else:
            resolved = _inside(root, path)
            if not resolved.is_file():
                if out["availability"] == "AVAILABLE":
                    raise ContextError(f"{what}: {path} is not a file in the project; mark it MISSING or fix the path")
                verification["digest"] = "MISSING"
            else:
                digest, size, data = _digest(resolved)
                verification.update({"sha256": digest, "size": size})
                declared = entry.get("digest")
                if declared is not None:
                    declared = str(declared).lower().removeprefix("sha256:")
                    verification["declared_sha256"] = declared
                    verification["digest"] = "MATCH" if declared == digest else "MISMATCH"
                else:
                    verification["digest"] = "RECORDED_AT_ATTACH" if digest else "TOO_LARGE_TO_HASH"
                if data is not None and resolved.suffix.lower() == ".pdf":
                    total_engine = pdf_page_count(data)
    elif external or entry.get("uri"):
        out["external"] = True
        if entry.get("uri"):
            out["uri"] = _text(entry["uri"], f"{what}: uri")
        verification["digest"] = "NOT_VERIFIED_EXTERNAL"
        if entry.get("digest"):
            verification["declared_sha256"] = str(entry["digest"]).lower().removeprefix("sha256:")
    elif out["availability"] == "AVAILABLE":
        raise ContextError(f"{what}: an available source needs a project path, or \"external\": true with a uri or label")
    out["verification"] = verification

    review = entry.get("review") or {}
    if not isinstance(review, dict):
        raise ContextError(f"{what}: review must be an object")
    unit = _choice(review.get("unit", "page"), UNITS, f"{what}: review unit")
    declared_total = review.get("total")
    if declared_total is not None and (not isinstance(declared_total, int) or declared_total < 1):
        raise ContextError(f"{what}: review total must be a positive integer")
    if total_engine is not None and unit == "page":
        if declared_total is not None and declared_total != total_engine:
            raise ContextError(f"{what}: the file has {total_engine} pages, the review says {declared_total}")
        total, total_basis = total_engine, "ENGINE_COUNTED"
    else:
        total, total_basis = declared_total, ("AGENT_REPORTED" if declared_total else "UNKNOWN")
    spans = parse_ranges(review.get("reviewed"), f"{what}: reviewed")
    if spans and out["availability"] != "AVAILABLE":
        raise ContextError(f"{what}: a {out['availability']} source cannot have reviewed units")
    if total is not None and spans and spans[-1][1] > total:
        raise ContextError(f"{what}: reviewed {unit} {spans[-1][1]} is beyond the {total} {unit}s of the source")
    methods = _choices(review.get("methods"), METHODS, f"{what}: methods")
    read = _choices(review.get("modalities_read"), MODALITIES, f"{what}: modalities_read")
    if spans and not methods:
        raise ContextError(f"{what}: reviewed units need the methods used to read them")
    if spans and not read:
        raise ContextError(f"{what}: reviewed units need the modalities read (text, visual, table, formula, …)")
    if set(read) & {"visual", "diagram"} and not set(methods) & {"HOST_NATIVE_VISUAL", "RENDERED_PAGES", "OCR", "PROVIDER_REVIEW"}:
        raise ContextError(f"{what}: a visual modality needs a visual method (HOST_NATIVE_VISUAL, RENDERED_PAGES, OCR or "
                           "PROVIDER_REVIEW); text extraction does not see figures")
    if out["availability"] != "AVAILABLE" and (methods or read):
        raise ContextError(f"{what}: a {out['availability']} source was not read; leave methods and modalities empty")
    reviewed = _count(spans)
    unread_modalities = sorted(set(out["modalities_present"]) - set(read)) if spans else []
    complete = bool(total and reviewed == total and not unread_modalities)
    out["review"] = {"unit": unit, "methods": methods, "modalities_read": read, "reviewed": [f"{a}-{b}" if a != b else str(a) for a, b in spans]}
    for key in ("tool", "tool_version", "host"):
        value = _opt_text(review, key, what)
        if value:
            out["review"][key] = value
    losses = review.get("losses") or []
    if not isinstance(losses, list) or not all(isinstance(v, str) and v.strip() for v in losses):
        raise ContextError(f"{what}: losses must be a list of text")
    out["review"]["losses"] = [v.strip() for v in losses]
    out["coverage"] = {"unit": unit, "reviewed": reviewed, "of": total, "of_basis": total_basis, "complete": complete,
                       "unread_modalities": unread_modalities}
    out["_spans"] = spans
    out["labels"] = labels(out)
    return out


def _locator(value: Any, source: dict, what: str) -> dict:
    text = _text(value, f"{what}: locator")
    match = _LOCATOR.match(text)
    if not match:
        raise ContextError(f"{what}: locator {text!r} must look like page:2, pages:1-3, slide:4, line:10-20, sheet:Name!A1:B9, "
                           "section:3.2, figure:1, table:2, node:ID or time:00:01:30")
    kind, rest = match.group(1), match.group(2).strip()
    out = {"locator": text, "kind": kind, "verified": "NOT_CHECKABLE"}
    review = source.get("review") or {}
    if kind in ("page", "slide", "line") and kind == review.get("unit"):
        spans = parse_ranges([rest], f"{what}: locator")
        start, end = spans[0]
        total = (source.get("coverage") or {}).get("of")
        if total is not None and end > total:
            raise ContextError(f"{what}: {text} is beyond the {total} {kind}s of {source['id']}")
        if not _covers(source["_spans"], start, end):
            raise ContextError(f"{what}: {text} of {source['id']} is outside what the review says was read "
                               f"({', '.join(review.get('reviewed') or []) or 'nothing'}); read it or cite what was read")
        out["verified"] = "INSIDE_REVIEWED_RANGE"
    return out


def _test_index(report: dict) -> dict[str, dict]:
    """Every test the run's reports name: id -> {"outcome", "provenance"} (an engine run wins over an import)."""
    index: dict[str, dict] = {}
    for run in ((report.get("states") or {}).get("current") or {}).get("runs") or []:
        provenance = run.get("provenance")
        for test_id, outcome in (run.get("outcomes_by_invocation") or {}).items():
            known = index.get(test_id)
            if known and known["provenance"] == "ENGINE_EXECUTED" and provenance != "ENGINE_EXECUTED":
                continue
            index[test_id] = {"outcome": outcome, "provenance": provenance}
    return index


def _base(test_id: str) -> str:
    return test_id.split("[", 1)[0]


def _resolve_test(test_id: str, index: dict[str, dict], root: Path, receipts: dict[str, dict]) -> dict:
    """Where a linked test was observed: an engine or imported run of this audit, an external execution receipt, or only
    its file in the project."""
    if test_id.startswith("external:"):
        receipt_id, _, name = test_id[len("external:"):].partition("::")
        receipt = receipts.get(receipt_id)
        if receipt is None:
            raise ContextError(f"test {test_id!r} names no external execution receipt {receipt_id!r}")
        known = receipt.get("test_outcomes") or {}
        outcome = known.get(name)
        if outcome is None and known:
            near = sorted(k for k in known if k.endswith(name.split("::")[-1]))[:3]
            raise ContextError(f"test {test_id!r}: receipt {receipt_id} has no test {name!r}"
                               + (f" (did you mean {', '.join(near)}?)" if near else ""))
        return {"test": test_id, "observed_in": "EXTERNAL_RECEIPT", "outcome": outcome or "UNKNOWN",
                "provenance": receipt["provenance"]}
    exact = index.get(test_id)
    matches = [exact] if exact else [v for k, v in index.items() if _base(k) == test_id]
    if matches:
        outcomes = sorted({m["outcome"] for m in matches})
        provenance = "ENGINE_EXECUTED" if all(m["provenance"] == "ENGINE_EXECUTED" for m in matches) else \
            sorted({m["provenance"] for m in matches})[0]
        outcome = outcomes[0] if len(outcomes) == 1 else "MIXED"
        return {"test": test_id, "observed_in": "RUN", "outcome": outcome, "provenance": provenance, "invocations": len(matches)}
    file_part = test_id.split("::", 1)[0]
    try:
        present = _inside(root, file_part).is_file()
    except ContextError:
        present = False
    if not present:
        raise ContextError(f"test {test_id!r} is neither in this run's results nor a file of the project "
                           "(an external result is named external:<receipt id>::<test>)")
    return {"test": test_id, "observed_in": "SOURCE_ONLY", "outcome": "NOT_RUN", "provenance": None}


def _file_digest(root: Path, test_id: str) -> str | None:
    if test_id.startswith("external:"):
        return None
    try:
        path = _inside(root, test_id.split("::", 1)[0])
    except ContextError:
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _mutation_detectors(report: dict) -> dict[str, set[str]]:
    """Each mutant an engine-run mutation tool detected on this state, by id and by label -> the tests it named as
    detecting that mutant. Imported reports and runs not tied to the state do not count; a kill of another mutant
    says nothing about this one."""
    detectors: dict[str, set[str]] = {}
    for run in ((report.get("states") or {}).get("current") or {}).get("mutation") or []:
        if run.get("provenance") != "ENGINE_EXECUTED" or run.get("matches_state") is not True:
            continue
        for detection in run.get("detections") or []:
            killers = set(detection.get("killed_by") or [])
            for key in (detection.get("mutant_id"), detection.get("mutant")):
                if key:
                    detectors.setdefault(str(key), set()).update(killers)
    return detectors


def _improve_binding(proof: dict, root: Path, what: str) -> tuple[str, str]:
    """(basis, why) for a negative control said to come from an ``assertiva improve`` report. VERIFIED only when the
    report file (under an evidence root, with the declared SHA-256) records this control as protection gained, detected
    by the named tests, and the audited tree is exactly that improve run's baseline plus its candidate changes."""
    import json

    from .receipts import ReceiptError, _sha256, authorized_evidence
    from .workspace import Baseline, capture_baseline

    cited = proof.get("improve_report")
    if not isinstance(cited, dict) or not cited.get("path"):
        return "AGENT_REPORTED", "no improve report cited"
    declared = str(cited.get("sha256") or "").lower().removeprefix("sha256:")
    try:
        path = authorized_evidence(str(cited["path"]), root, what)
    except ReceiptError as exc:
        raise ContextError(str(exc)) from exc
    if not path.is_file():
        return "AGENT_REPORTED", "the cited improve report is not available"
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ContextError(f"{what}: the cited improve report is larger than 64 MiB")
    if _sha256(path) != declared:
        raise ContextError(f"{what}: the improve report no longer has the declared SHA-256; it cannot vouch for the control")
    try:
        improve = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContextError(f"{what}: the cited improve report is not readable JSON ({type(exc).__name__})") from exc
    if improve.get("workflow") != "improve":
        raise ContextError(f"{what}: the cited report is not an improve report")
    gained = ((improve.get("candidate_qualification") or {}).get("protection") or {}).get("gained") or []
    match = [g for g in gained if g.get("kind") == "negative_control" and g.get("id") == proof["ref"]]
    if not match:
        return "AGENT_REPORTED", f"the improve report records no protection gained by control {proof['ref']}"
    named = {g.get("detected_by") for g in match}
    if not set(proof["detected_by"]) <= named:
        return "AGENT_REPORTED", "the improve report names other detecting tests: " + ", ".join(sorted(str(n) for n in named))
    baseline_digest = (improve.get("project") or {}).get("baseline_digest")
    files = dict(capture_baseline(root).files)
    for change in (improve.get("change_set") or {}).get("changes") or []:
        rel = change.get("path") or change.get("change_id")
        if files.get(rel) != change.get("candidate_fingerprint"):
            return "AGENT_REPORTED", f"the audited {rel} is not the candidate the improve run qualified"
        if change.get("original_fingerprint"):
            files[rel] = change["original_fingerprint"]
        else:
            files.pop(rel, None)
    if not baseline_digest or Baseline(root=str(root), revision=None, dirty=None, files=files).digest != baseline_digest:
        return "AGENT_REPORTED", "the audited tree minus the candidate changes is not the improve run's baseline"
    return "IMPROVE_REPORT_VERIFIED", "control recorded as protection gained by these tests; tree = improve baseline + candidate"


def _behavior(entry: Any, sources: dict[str, dict], tests: dict[str, dict], root: Path, receipts: dict[str, dict],
              detectors: dict[str, set[str]]) -> dict:
    if not isinstance(entry, dict):
        raise ContextError("each behavior must be an object")
    bid = _ident(entry.get("id"), "behavior id")
    what = f"behavior {bid}"
    out: dict[str, Any] = {"id": bid, "title": _text(entry.get("title"), f"{what}: title"),
                           "authority": _choice(entry.get("authority", "UNKNOWN"), AUTHORITY, f"{what}: authority"),
                           "rationale": _text(entry.get("rationale"), f"{what}: rationale")}
    status = entry.get("status")
    if status == "STALE":
        raise ContextError(f"{what}: STALE is set by the engine when a cited source or test changed, never claimed")
    out["claimed_status"] = _choice(status, COVERAGE_STATES, f"{what}: status")
    slice_ = entry.get("slice") or {}
    if not isinstance(slice_, dict) or not slice_.get("expected"):
        raise ContextError(f"{what}: slice needs at least the expected result (and, when known, precondition, input, "
                           "action, boundary, forbidden effects, failure handling)")
    out["slice"] = {k: _text(v, f"{what}: slice.{k}") for k, v in slice_.items()
                    if k in ("precondition", "input", "action", "boundary", "expected", "forbidden", "failure", "actor",
                             "timing", "configuration") and v is not None}
    for key in ("component", "level"):
        value = _opt_text(entry, key, what)
        if value:
            out[key] = value
    cited = entry.get("sources") or []
    if not isinstance(cited, list):
        raise ContextError(f"{what}: sources must be a list")
    if not cited and out["authority"] not in ("OBSERVED_BEHAVIOR", "CHARACTERIZATION", "RISK_HYPOTHESIS", "EXPLORATORY", "UNKNOWN"):
        raise ContextError(f"{what}: an {out['authority']} behavior cites the source that states it")
    out["sources"] = []
    for ref in cited:
        if not isinstance(ref, dict) or ref.get("source") not in sources:
            raise ContextError(f"{what}: each source reference names a listed source id")
        source = sources[ref["source"]]
        if source["availability"] != "AVAILABLE":
            raise ContextError(f"{what}: cites {source['id']}, which is {source['availability']} and was not read")
        item = {"source": source["id"], **(_locator(ref["locator"], source, what) if ref.get("locator") else
                                          {"locator": None, "verified": "NO_LOCATOR"})}
        if "STALE" in source["labels"]:
            item["stale"] = True
        out["sources"].append(item)
    for key in ("conflicts_with", "supersedes", "depends_on"):
        values = entry.get(key) or []
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ContextError(f"{what}: {key} must be a list of behavior ids")
        if values:
            out[key] = values

    linked = []
    for link in entry.get("tests") or []:
        if not isinstance(link, dict):
            raise ContextError(f"{what}: each test link is an object")
        test_id = _text(link.get("test"), f"{what}: test")
        observed = _resolve_test(test_id, tests, root, receipts)
        item = {**observed, "relation": _choice(link.get("relation", "covers"), RELATIONS, f"{what}: relation of {test_id}"),
                "oracle": _choice(link.get("oracle"), ORACLES, f"{what}: oracle of {test_id}"),
                "file_sha256": _file_digest(root, test_id)}
        if link.get("note"):
            item["note"] = _text(link["note"], f"{what}: note")
        linked.append(item)
    out["tests"] = linked

    protection = []
    for proof in entry.get("protection") or []:
        if not isinstance(proof, dict):
            raise ContextError(f"{what}: each protection entry is an object")
        kind = _choice(proof.get("kind"), PROTECTION_KINDS, f"{what}: protection kind")
        detected_by = proof.get("detected_by") or []
        if not isinstance(detected_by, list) or not all(isinstance(t, str) for t in detected_by):
            raise ContextError(f"{what}: detected_by lists test ids")
        unknown = [t for t in detected_by if t not in {x["test"] for x in linked}]
        if unknown:
            raise ContextError(f"{what}: protection names tests not linked to the behavior: {', '.join(unknown)}")
        if not isinstance(proof.get("detected"), bool):
            raise ContextError(f"{what}: protection detected must be true or false (JSON boolean), not {proof.get('detected')!r}")
        item = {"kind": kind, "ref": _text(proof.get("ref"), f"{what}: protection ref"),
                "detected": proof["detected"], "detected_by": detected_by,
                "evidence": [_text(v, f"{what}: protection evidence") for v in (proof.get("evidence") or [])]}
        if item["detected"] and not detected_by:
            raise ContextError(f"{what}: a detected break names the linked tests that detected it")
        if kind == "ENGINE_MUTATION":
            killers = detectors.get(item["ref"])
            if killers is None:
                raise ContextError(f"{what}: ENGINE_MUTATION {item['ref']} is not a mutant this run's engine mutation detected "
                                   "(name it by mutant id or label)")
            wrong = [t for t in detected_by if t not in killers and _base(t) not in {_base(k) for k in killers}]
            if item["detected"] and wrong:
                raise ContextError(f"{what}: mutant {item['ref']} was not detected by {', '.join(wrong)} in this run "
                                   f"(the tool named {', '.join(sorted(killers)) or 'no test'})")
            item["basis"], item["verification"] = ("ENGINE_VERIFIED", "this mutant, detected by these tests in this run")
        else:
            if not item["evidence"]:
                raise ContextError(f"{what}: a {kind} needs its evidence (command, revision, output) to be rerun")
            if kind == "NEGATIVE_CONTROL" and proof.get("improve_report") is not None:
                item["basis"], item["verification"] = _improve_binding({**proof, "ref": item["ref"], "detected_by": detected_by}, root, what)
                item["improve_report"] = {"name": Path(str(proof["improve_report"].get("path"))).name,
                                          "sha256": str(proof["improve_report"].get("sha256") or "")}
            else:
                item["basis"], item["verification"] = ("AGENT_REPORTED", "the agent's own break; not verified by the engine")
        protection.append(item)
    out["protection"] = protection
    out["evidence"] = [_text(v, f"{what}: evidence") for v in (entry.get("evidence") or [])]
    _check_strength(out, what)
    out["dimensions"] = _dimensions(out)
    status = out["claimed_status"]
    if status == "PROVEN_IN_SCOPE" and not _verified_detection(out):
        # the agent's analysis stays (claimed_status, protection entries); the mechanical status does not go beyond
        # what the engine could tie to this tree
        status = "OBSERVED_PASS"
        out["status_limited_by"] = ("no detected break is verified by the engine (an engine mutation of this run, or an "
                                    "improve report bound to this tree); the agent's report is kept as claimed")
    out["status"] = "STALE" if any(s.get("stale") for s in out["sources"]) else status
    return out


def _verified_detection(behavior: dict) -> bool:
    strong = {t["test"] for t in behavior["tests"] if _passing(t) and t["oracle"] == "STRONG" and t["relation"] in ("validates", "reproduces")}
    return any(p["detected"] and p["basis"] in VERIFIED_BASES and strong & set(p["detected_by"]) for p in behavior["protection"])


def _passing(test: dict) -> bool:
    return test["outcome"] in ("PASSED", "PASS", "passed") and test["provenance"] in ("ENGINE_EXECUTED", "AGENT_EXTERNAL_VERIFIED")


def _check_strength(behavior: dict, what: str) -> None:
    """Refuse a status the linked evidence cannot carry. Weaker statuses are always allowed."""
    status, tests = behavior["claimed_status"], behavior["tests"]
    failing = [t["test"] for t in tests if t["outcome"] in ("FAILED", "ERROR", "FAIL", "MIXED")]
    if status in ("PROVEN_IN_SCOPE", "OBSERVED_PASS") and failing:
        raise ContextError(f"{what}: {status} with a linked test that did not pass ({', '.join(failing)})")
    if status == "OBSERVED_PASS" and not any(_passing(t) for t in tests):
        raise ContextError(f"{what}: OBSERVED_PASS needs a linked test that passed in an engine run or a verified "
                           "external receipt of this audit; a mapped or imported test is PARTIAL at most")
    if status == "PROVEN_IN_SCOPE":
        strong = [t for t in tests if _passing(t) and t["oracle"] == "STRONG" and t["relation"] in ("validates", "reproduces")]
        if not strong:
            raise ContextError(f"{what}: PROVEN_IN_SCOPE needs a linked test that validates the behavior with a STRONG "
                               "oracle and passed in an engine run or a verified external receipt")
        names = {t["test"] for t in strong}
        if not any(p["detected"] and names & set(p["detected_by"]) for p in behavior["protection"]):
            raise ContextError(f"{what}: PROVEN_IN_SCOPE needs a break (negative control, mutant) detected by one of those "
                               "tests; without it the strongest status is OBSERVED_PASS")
        if not behavior["sources"] and behavior["authority"] not in ("OBSERVED_BEHAVIOR", "CHARACTERIZATION"):
            raise ContextError(f"{what}: PROVEN_IN_SCOPE cites the source of the behavior")
    if status in ("PARTIAL", "WEAK", "CHARACTERIZATION_ONLY") and not tests:
        raise ContextError(f"{what}: {status} names the tests it rests on; with none, use NOT_EVIDENCED or UNKNOWN")
    if status == "CHARACTERIZATION_ONLY" and not any(t["relation"] == "characterizes" for t in tests):
        raise ContextError(f"{what}: CHARACTERIZATION_ONLY links a test whose relation is characterizes")
    if status == "NOT_EVIDENCED" and any(t["relation"] == "validates" and t["oracle"] == "STRONG" for t in tests):
        raise ContextError(f"{what}: NOT_EVIDENCED while a linked test validates it with a STRONG oracle; use PARTIAL "
                           "or OBSERVED_PASS, or correct the oracle")


def _dimensions(behavior: dict) -> dict:
    """Each step of "is this behavior tested?" on its own; a later step never implies an earlier one is stronger."""
    tests = behavior["tests"]
    return {
        "declared_by_source": bool(behavior["sources"]),
        "linked_tests": len(tests),
        "oracle_present": sum(1 for t in tests if t["oracle"] in ("STRONG", "PARTIAL")),
        "executed": sum(1 for t in tests if t["observed_in"] != "SOURCE_ONLY"),
        "passed": sum(1 for t in tests if t["outcome"] in ("PASSED", "PASS", "passed")),
        "failed": sum(1 for t in tests if t["outcome"] in ("FAILED", "ERROR", "FAIL", "MIXED")),
        "fault_sensitivity": ("DEMONSTRATED" if any(p["detected"] and p["basis"] in VERIFIED_BASES for p in behavior["protection"])
                              else "AGENT_REPORTED" if any(p["detected"] for p in behavior["protection"])
                              else "NOT_DETECTED" if behavior["protection"] else "NOT_CHALLENGED"),
    }


def apply_context(report: dict, data: dict, root: Path, receipts: dict[str, dict]) -> dict | None:
    """The validated ``context`` section, or None when the assessment has none."""
    sources_in, behaviors_in = data.get("sources"), data.get("behaviors")
    if sources_in is None and behaviors_in is None:
        return None
    if not isinstance(sources_in or [], list) or not isinstance(behaviors_in or [], list):
        raise ContextError("sources and behaviors must be lists")
    sources: dict[str, dict] = {}
    for entry in sources_in or []:
        source = _source(entry, root)
        if source["id"] in sources:
            raise ContextError(f"source id {source['id']} is used more than once")
        sources[source["id"]] = source
    tests = _test_index(report)
    detectors = _mutation_detectors(report)
    behaviors: list[dict] = []
    for entry in behaviors_in or []:
        behavior = _behavior(entry, sources, tests, root, receipts, detectors)
        if any(b["id"] == behavior["id"] for b in behaviors):
            raise ContextError(f"behavior id {behavior['id']} is used more than once")
        behaviors.append(behavior)
    ids = {b["id"] for b in behaviors}
    for behavior in behaviors:
        for key in ("conflicts_with", "supersedes", "depends_on"):
            missing = [v for v in behavior.get(key) or [] if v not in ids]
            if missing:
                raise ContextError(f"behavior {behavior['id']}: {key} names unknown behaviors: {', '.join(missing)}")
    for source in sources.values():
        source.pop("_spans", None)
    by_status: dict[str, int] = {}
    for behavior in behaviors:
        by_status[behavior["status"]] = by_status.get(behavior["status"], 0) + 1
    conflicts = sorted({tuple(sorted((b["id"], other))) for b in behaviors for other in b.get("conflicts_with") or []})
    return {
        "schema": "assertiva-context/1",
        "sources": list(sources.values()),
        "behaviors": behaviors,
        "summary": {
            "sources": len(sources),
            "sources_by_label": _label_counts(sources.values()),
            "behaviors": len(behaviors),
            "behaviors_by_status": by_status,
            "unit": "behavior slices the auditing agent identified; not a complete requirement count",
            "conflicts": [list(c) for c in conflicts],
            "stale": sorted(b["id"] for b in behaviors if b["status"] == "STALE"),
        },
        "note": "reading is reported by the agent; the engine verified paths, digests, page counts it could count, "
                "citations against reviewed ranges and status strength against linked evidence",
    }


def _label_counts(sources) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in sources:
        for label in source["labels"]:
            counts[label] = counts.get(label, 0) + 1
    return counts


def carry_over(previous: dict | None, root: Path) -> dict | None:
    """What a new audit run can say about the previous run's traceability without re-reading anything: which behaviors
    still rest on the same source and test bytes (VALID_PENDING_REATTACH) and which became STALE, and why. The previous
    assessment is history, never re-applied to the new run."""
    context = (previous or {}).get("context")
    if not context:
        return None
    current: dict[str, str | None] = {}
    for source in context.get("sources") or []:
        path = source.get("path")
        if not path or source.get("availability") == "PRIVATE":
            continue
        try:
            resolved = _inside(root, path)
            current[source["id"]] = hashlib.sha256(resolved.read_bytes()).hexdigest() if resolved.is_file() else None
        except (ContextError, OSError):
            current[source["id"]] = None
    before = {s["id"]: (s.get("verification") or {}).get("sha256") for s in context.get("sources") or []}
    changed_sources = sorted(sid for sid, digest in current.items() if digest != before.get(sid))
    rows = []
    for behavior in context.get("behaviors") or []:
        reasons = [f"source {s['source']} changed" for s in behavior.get("sources") or [] if s["source"] in changed_sources]
        for test in behavior.get("tests") or []:
            if test.get("file_sha256") and _file_digest(root, test["test"]) != test["file_sha256"]:
                reasons.append(f"test file of {test['test']} changed")
        rows.append({"id": behavior["id"], "previous_status": behavior.get("status"),
                     "state": "STALE" if reasons else "VALID_PENDING_REATTACH", "because": reasons})
    return {"previous_run_id": previous.get("run_id"), "changed_sources": changed_sources, "behaviors": rows,
            "note": "the previous run's conclusions are kept as history; a new assessment re-establishes them for this run"}
