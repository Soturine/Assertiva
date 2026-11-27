"""External execution receipts: what the auditing agent ran itself, outside the engine, recorded as evidence.

When the engine has no adapter for a stack (C++, .NET, Ruby, a future language) the agent can still obtain runtime
evidence: it finds the project's own runner or a fitting tool, prepares it in isolation with the user's consent, runs
it and keeps the raw output. A receipt records that run so the report can carry it next to engine evidence without
pretending it is engine evidence.

A receipt is ingestion only. The engine never runs the command it records, never installs what it names and never
treats it as authorization for anything. It checks what it can:

- each raw artifact the receipt cites exists and still has the SHA-256 the receipt declares (integrity, not
  authenticity: the engine did not watch the tool produce it);
- a structured result artifact (JUnit XML, CTRF JSON, an Allure directory) is read with the same parsers as
  ``--test-results``, and its counts must agree with the counts the receipt declares;
- the revision or tree digest the run used is compared with the audited one.

``provenance`` is always ``AGENT_EXTERNAL``; ``link`` says whether the receipt is tied to this audit
(``VERIFIED``: same revision and every cited artifact verified, with structured results that agree) or not
(``UNVERIFIED``). A lint, format or type check never counts as test invocations, and a test run that executed
nothing is ``NO_TESTS``, never a pass.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from .process import redact
from .sanitize import sanitize_message

PURPOSES = ("tests", "lint", "format", "typecheck", "coverage", "mutation", "fuzz", "security", "build", "contract",
            "accessibility", "other")
ISOLATION = ("CONTAINER", "VM", "DISPOSABLE_COPY", "NONE")
NETWORK = ("NONE", "DOWNLOAD_STAGE_ONLY", "ALLOWED", "UNKNOWN")
CONSENT = ("USER_AUTHORIZED", "PREAUTHORIZED_SCOPE", "NOT_NEEDED", "NOT_GIVEN")
ARTIFACT_KINDS = ("junit", "ctrf", "allure", "log", "mutation", "coverage", "trx", "sarif", "other")
STRUCTURED = ("junit", "ctrf", "allure")
_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_SHA = re.compile(r"[0-9a-f]{64}")
_OUTCOMES = ("PASSED", "FAILED", "ERROR", "SKIPPED", "NOT_RUN")


class ReceiptError(ValueError):
    """A receipt cannot be attached; the message says why."""


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReceiptError(f"{what} must be non-empty text")
    return value.strip()


def _choice(value: Any, allowed: tuple, what: str) -> str:
    if value not in allowed:
        raise ReceiptError(f"{what} must be one of {', '.join(allowed)}")
    return value


def _count(value: Any, what: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ReceiptError(f"{what} must be a non-negative integer")
    return value


MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_ARTIFACT_FILES = 5000


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    """Digest of a result file, or of a results directory (relative names and contents), within fixed bounds: an
    artifact is a tool's output, not a tree to walk without limit."""
    if path.is_dir():
        files = []
        for child in path.rglob("*"):
            if child.is_symlink():
                raise ReceiptError(f"{path.name} contains a link ({child.name}); a results directory is plain files")
            if child.is_file():
                files.append(child)
                if len(files) > MAX_ARTIFACT_FILES:
                    raise ReceiptError(f"{path.name} holds more than {MAX_ARTIFACT_FILES} files; cite the result files themselves")
        if sum(f.stat().st_size for f in files) > MAX_ARTIFACT_BYTES:
            raise ReceiptError(f"{path.name} is larger than {MAX_ARTIFACT_BYTES} bytes")
        digest = hashlib.sha256()
        for child in sorted(files):
            digest.update(child.relative_to(path).as_posix().encode() + b"\0")
            digest.update(bytes.fromhex(_file_sha256(child)))
        return digest.hexdigest()
    if path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ReceiptError(f"{path.name} is larger than {MAX_ARTIFACT_BYTES} bytes")
    return _file_sha256(path)


def evidence_roots() -> list[Path]:
    """Where cited evidence may be read from: ``ASSERTIVA_HOME`` and the directories the user lists in
    ``ASSERTIVA_EVIDENCE_ROOTS`` (os.pathsep-separated). An absolute path elsewhere is not authorization to read a
    file: the engine hashes what it reads, and a hash of a private file can itself be sensitive."""
    from .workspace import assertiva_home

    roots = [assertiva_home()]
    for item in os.environ.get("ASSERTIVA_EVIDENCE_ROOTS", "").split(os.pathsep):
        if item.strip():
            roots.append(Path(item.strip()))
    return [r.resolve() for r in roots]


def authorized_evidence(raw: str, project: Path, what: str) -> Path:
    """The resolved path of a cited evidence file or results directory, or a refusal: absolute, outside the project,
    under an evidence root, not a link, a regular file or a directory (never a device, pipe or socket)."""
    path = Path(raw)
    if not path.is_absolute():
        raise ReceiptError(f"{what}: evidence paths are absolute (the tool wrote them outside the project)")
    if path.is_symlink():
        raise ReceiptError(f"{what}: {path.name} is a link; cite the file itself")
    resolved = path.resolve()
    if resolved == project.resolve() or resolved.is_relative_to(project.resolve()):
        raise ReceiptError(f"{what}: {path.name} is inside the project; an audit never runs tools in the project tree, so "
                           "cited evidence lives outside it")
    if not any(resolved == r or resolved.is_relative_to(r) for r in evidence_roots()):
        raise ReceiptError(f"{what}: {path.name} is outside the evidence roots (ASSERTIVA_HOME, or a directory listed in "
                           "ASSERTIVA_EVIDENCE_ROOTS by the user); it is not read")
    if resolved.exists() and not (resolved.is_file() or resolved.is_dir()):
        raise ReceiptError(f"{what}: {path.name} is not a regular file or directory")
    return resolved


def _artifact(entry: Any, root: Path, what: str) -> dict:
    if not isinstance(entry, dict):
        raise ReceiptError(f"{what}: each artifact is an object with path, sha256 and kind")
    kind = _choice(entry.get("kind", "other"), ARTIFACT_KINDS, f"{what}: artifact kind")
    declared = str(entry.get("sha256") or "").lower().removeprefix("sha256:")
    if not _SHA.fullmatch(declared):
        raise ReceiptError(f"{what}: each artifact declares the SHA-256 of what the tool wrote (64 hex characters)")
    raw = _text(entry.get("path"), f"{what}: artifact path")
    path = Path(raw)
    resolved = authorized_evidence(raw, root, what)
    out = {"kind": kind, "name": path.name, "declared_sha256": declared}
    if not resolved.exists():
        out["integrity"] = "UNAVAILABLE"
        return out
    actual = _sha256(resolved)
    out["sha256"] = actual
    out["integrity"] = "VERIFIED" if actual == declared else "MISMATCH"
    if out["integrity"] == "MISMATCH":
        raise ReceiptError(f"{what}: {path.name} no longer has the SHA-256 the receipt declares; the artifact changed after "
                           "the run, so the receipt cannot vouch for it")
    if kind in STRUCTURED:
        from .adapters.portable_results import load_results

        try:
            run = load_results(resolved)
        except Exception as exc:  # a parser error is a finding about the artifact, not a crash
            out["parsed"] = {"error": sanitize_message(str(exc))}
            return out
        tally: dict[str, int] = {}
        outcomes: dict[str, str] = {}
        for invocation in run.invocations:
            outcome = invocation.outcome.name if invocation.outcome else "NOT_RUN"
            tally[outcome] = tally.get(outcome, 0) + 1
            outcomes[invocation.invocation_id] = outcome
        out["parsed"] = {"tests": len(run.invocations), "outcomes": tally}
        out["_outcomes"] = outcomes
    return out


def _results(value: Any, what: str) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ReceiptError(f"{what}: results is an object of counts")
    out = {key: _count(value.get(key, 0), f"{what}: results.{key}") for key in ("tests", "passed", "failed", "skipped", "errors")}
    if out["passed"] + out["failed"] + out["skipped"] + out["errors"] > out["tests"]:
        raise ReceiptError(f"{what}: passed + failed + skipped + errors exceeds tests")
    return out


def _agrees(declared: dict, parsed: dict) -> bool:
    tally = parsed.get("outcomes") or {}
    return (declared["tests"] == parsed.get("tests") and declared["passed"] == tally.get("PASSED", 0) + tally.get("XFAILED", 0)
            and declared["failed"] + declared["errors"] == tally.get("FAILED", 0) + tally.get("ERROR", 0) + tally.get("XPASSED", 0)
            and declared["skipped"] == tally.get("SKIPPED", 0))


def _status(purpose: str, exit_code: int | None, results: dict | None) -> str:
    if exit_code is None:
        return "UNKNOWN"
    if purpose != "tests":
        return "PASS" if exit_code == 0 else "FAIL"
    if results is None:
        return "UNKNOWN" if exit_code == 0 else "FAIL"
    if results["tests"] == 0 or results["tests"] == results["skipped"]:
        return "NO_TESTS"
    if results["failed"] or results["errors"]:
        return "FAIL"
    return "PASS" if exit_code == 0 else "ERROR"


def receipt(entry: Any, report: dict, root: Path) -> dict:
    if not isinstance(entry, dict):
        raise ReceiptError("each external execution is an object")
    rid = entry.get("id")
    if not isinstance(rid, str) or not _ID.fullmatch(rid):
        raise ReceiptError("an external execution id is a short lowercase slug")
    what = f"external execution {rid}"
    purpose = _choice(entry.get("purpose"), PURPOSES, f"{what}: purpose")
    command = entry.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
        raise ReceiptError(f"{what}: command is the exact argument list that ran")
    exit_code = entry.get("exit_code")
    if exit_code is not None and (not isinstance(exit_code, int) or isinstance(exit_code, bool)):
        raise ReceiptError(f"{what}: exit_code is the integer the process returned (null when it never finished)")
    consent = entry.get("consent") or {}
    if not isinstance(consent, dict):
        raise ReceiptError(f"{what}: consent is an object")
    execute_consent = _choice(consent.get("execute", "NOT_GIVEN"), CONSENT, f"{what}: consent.execute")
    if execute_consent == "NOT_GIVEN":
        raise ReceiptError(f"{what}: a run without the user's consent is not recorded as evidence; record it as a proposal "
                           "in the assessment's unknowns instead")
    out: dict[str, Any] = {
        "id": rid, "purpose": purpose, "provenance": "AGENT_EXTERNAL",
        "tool": _text(entry.get("tool"), f"{what}: tool"),
        "tool_version": _text(entry.get("tool_version"), f"{what}: tool_version (as the tool itself reported it)"),
        "ecosystem": _text(entry.get("ecosystem", "unknown"), f"{what}: ecosystem"),
        "command": [sanitize_message(redact(c), limit=400) for c in command],
        "exit_code": exit_code,
        "isolation": _choice(entry.get("isolation"), ISOLATION, f"{what}: isolation"),
        "network": _choice(entry.get("network", "UNKNOWN"), NETWORK, f"{what}: network"),
        "consent": {"execute": execute_consent,
                    "download": _choice(consent.get("download", "NOT_NEEDED"), CONSENT, f"{what}: consent.download")},
    }
    if out["consent"]["download"] == "NOT_GIVEN":
        raise ReceiptError(f"{what}: a download without consent is not recorded as evidence")
    for key in ("duration_s",):
        if entry.get(key) is not None:
            if not isinstance(entry[key], (int, float)) or entry[key] < 0:
                raise ReceiptError(f"{what}: {key} is a non-negative number")
            out[key] = entry[key]
    for key in ("started_at", "cwd", "notes", "why_this_tool"):
        if entry.get(key):
            out[key] = sanitize_message(_text(entry[key], f"{what}: {key}"), limit=600)
    environment = entry.get("environment") or {}
    if not isinstance(environment, dict):
        raise ReceiptError(f"{what}: environment is an object")
    out["environment"] = {k: sanitize_message(str(v), limit=200) for k, v in environment.items() if isinstance(k, str)}
    research = entry.get("research") or []
    if not isinstance(research, list):
        raise ReceiptError(f"{what}: research is a list of consulted sources")
    out["research"] = []
    for item in research:
        if not isinstance(item, dict) or not item.get("url") or not item.get("accessed"):
            raise ReceiptError(f"{what}: each research entry has url, accessed (date) and what it settled")
        out["research"].append({k: sanitize_message(str(item[k]), limit=300) for k in ("url", "title", "accessed", "applies_to",
                                                                                       "conclusion") if item.get(k)})

    results = _results(entry.get("results"), what)
    if purpose != "tests" and (results or entry.get("test_outcomes")):
        raise ReceiptError(f"{what}: a {purpose} run has no test invocations; record what it reported in notes or an "
                           "artifact, never as test results")
    artifacts = [_artifact(a, root, what) for a in entry.get("artifacts") or []]
    parsed_outcomes: dict[str, str] = {}
    structured = [a for a in artifacts if a["kind"] in STRUCTURED and "parsed" in a and "error" not in a["parsed"]]
    consistency = "NO_STRUCTURED_RESULTS"
    if structured:
        totals = {"tests": 0, "outcomes": {}}
        for artifact in structured:
            totals["tests"] += artifact["parsed"]["tests"]
            for k, v in artifact["parsed"]["outcomes"].items():
                totals["outcomes"][k] = totals["outcomes"].get(k, 0) + v
            parsed_outcomes.update(artifact.pop("_outcomes", {}))
        if results is None:
            raise ReceiptError(f"{what}: the receipt cites structured results; declare the counts it reports")
        if not _agrees(results, totals):
            raise ReceiptError(f"{what}: the declared counts {results} do not agree with what the cited result files "
                               f"contain ({totals['tests']} tests, {totals['outcomes']})")
        consistency = "AGREES"
    for artifact in artifacts:
        artifact.pop("_outcomes", None)
    declared_outcomes = entry.get("test_outcomes") or {}
    if not isinstance(declared_outcomes, dict) or not all(v in _OUTCOMES for v in declared_outcomes.values()):
        raise ReceiptError(f"{what}: test_outcomes maps a test name to {', '.join(_OUTCOMES)}")
    for name, outcome in declared_outcomes.items():
        if name in parsed_outcomes and parsed_outcomes[name] != outcome:
            raise ReceiptError(f"{what}: {name} is {outcome} in the receipt and {parsed_outcomes[name]} in its result file")
    out["test_outcomes"] = {**declared_outcomes, **parsed_outcomes}
    out["artifacts"] = artifacts
    out["results"] = results
    out["results_consistency"] = consistency
    out["status"] = _status(purpose, exit_code, results)

    project = report.get("project") or {}
    revision = entry.get("revision")
    tree = entry.get("tree_digest")
    if revision and project.get("revision") and not project.get("dirty") and revision == project["revision"]:
        out["revision_link"] = "SAME_REVISION"
    elif tree and tree == project.get("digest"):
        out["revision_link"] = "SAME_TREE_DIGEST"
    elif revision and revision == project.get("revision") and project.get("dirty"):
        # the audited tree had local changes: the commit names the base, not the code the run saw
        out["revision_link"] = "SAME_REVISION_DIRTY_TREE"
    elif revision or tree:
        out["revision_link"] = "DIFFERENT"
    else:
        out["revision_link"] = "NOT_DECLARED"
    verified = (out["revision_link"] in ("SAME_REVISION", "SAME_TREE_DIGEST") and artifacts
                and all(a["integrity"] == "VERIFIED" for a in artifacts)
                and (purpose != "tests" or consistency == "AGREES"))
    out["link"] = "VERIFIED" if verified else "UNVERIFIED"
    out["test_provenance"] = "AGENT_EXTERNAL_VERIFIED" if verified else "AGENT_EXTERNAL_UNVERIFIED"
    return out


def apply_receipts(report: dict, data: dict, root: Path) -> list[dict]:
    entries = data.get("external_executions") or []
    if not isinstance(entries, list):
        raise ReceiptError("external_executions must be a list")
    out = []
    for entry in entries:
        item = receipt(entry, report, root)
        if any(r["id"] == item["id"] for r in out):
            raise ReceiptError(f"external execution id {item['id']} is used more than once")
        out.append(item)
    return out


def for_context(receipts: list[dict]) -> dict[str, dict]:
    """Receipts as the traceability checker reads them: a linked external test passes only through a verified receipt."""
    return {r["id"]: {**r, "provenance": r["test_provenance"]} for r in receipts}
