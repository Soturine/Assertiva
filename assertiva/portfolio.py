"""Portfolio assurance: a registry of the projects an owner audits, their audits over time, and feedback about Assertiva.

Opt-in and local. The registry lives in ``ASSERTIVA_HOME/portfolio`` (schema-versioned JSON, never inside a project);
a project enters it only when the owner adds it (a local folder) or picks it from a discovery listing, which reads
repository metadata and clones nothing. Each audit run through the portfolio is the ordinary ``assertiva audit`` (same
read-only guard, same disposable copies, same consent rules); the registry keeps a summary that points to the run's
report, not a copy of the project's logs.

Two kinds of record never mix: PROJECT findings (the audited project's defects and risks, as the audit reported them)
and ASSERTIVA feedback (a false positive, a miss, an adapter error of Assertiva itself, with a sanitized reproducer and
a stable ``feedback_id`` derived from its signature, so the same issue seen again is one entry with more sightings).
Feedback states move OBSERVED -> REPRODUCED -> FIXED_IN_ASSERTIVA_BRANCH -> RETESTED_WITH_ASSERTIVA -> VERIFIED_AT_SHA;
BLOCKED, NOT_SUPPORTED, REOPENED and REGRESSION are terminal or re-entry states; history is appended, never rewritten.

A project's status says what the evidence allows: CURRENT (audited at the revision now checked out), STALE (audited
at another revision, or the tree changed), BLOCKED (the last audit could not run its tests), UNKNOWN (never audited
or no revision to compare). Legacy projects that do not build today stay NOT_RUN/BLOCKED with their recorded needs;
nothing scores them.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .workspace import assertiva_home

SCHEMA = 1
PHASES = ("active", "maintenance", "archived", "legacy", "unknown")
FEEDBACK_STATES = ("OBSERVED", "REPRODUCED", "FIXED_IN_ASSERTIVA_BRANCH", "RETESTED_WITH_ASSERTIVA", "VERIFIED_AT_SHA",
                   "BLOCKED", "NOT_SUPPORTED", "REOPENED", "REGRESSION")
FEEDBACK_KINDS = ("FALSE_POSITIVE", "FALSE_NEGATIVE", "MISSING_ANALYSIS", "ADAPTER_ERROR", "SECURITY", "COST",
                  "EVIDENCE_INCONSISTENCY", "UNSUPPORTED")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class PortfolioError(ValueError):
    """A portfolio request that cannot be honored (unknown project, invalid name, bad state)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def portfolio_dir() -> Path:
    return assertiva_home() / "portfolio"


@dataclass
class Project:
    name: str
    path: str | None = None  # local checkout (absolute); None for a project known only from discovery
    url: str | None = None
    visibility: str | None = None
    phase: str = "unknown"
    criticality: str = "unknown"
    consent: list[str] = field(default_factory=lambda: ["local-read"])
    stacks: list[dict] = field(default_factory=list)  # {"name", "basis"}: detected, never assumed
    needs: list[str] = field(default_factory=list)  # environment the project needs (JDK 11, Android SDK, a device…)
    added_at: str = field(default_factory=_now)
    runs: list[dict] = field(default_factory=list)  # newest last; summaries pointing to reports


def _load() -> dict:
    path = portfolio_dir() / "registry.json"
    if not path.is_file():
        return {"schema": SCHEMA, "projects": {}, "feedback": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise PortfolioError(f"portfolio registry schema {data.get('schema')} is not supported by this version (expects {SCHEMA})")
    return data


def _save(data: dict) -> None:
    """Write to a temporary file of this writer's own, flush it to disk, then replace the registry in one step: a crash
    or an error before the replace leaves the previous registry whole (the temporary file is removed)."""
    folder = portfolio_dir()
    folder.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix="registry.", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, folder / "registry.json")
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


_HELD = threading.local()
LOCK_TIMEOUT_S = 60.0


@contextmanager
def _locked():
    """An OS lock on ``registry.lock`` for one read-modify-write of the registry, across processes and threads. The
    operating system releases it when a process dies, so a crash leaves no stale lock. Reentrant within a thread."""
    if getattr(_HELD, "depth", 0):
        _HELD.depth += 1
        try:
            yield
        finally:
            _HELD.depth -= 1
        return
    folder = portfolio_dir()
    folder.mkdir(parents=True, exist_ok=True)
    handle = open(folder / "registry.lock", "a+b")
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt

                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    raise PortfolioError(f"the portfolio registry stayed locked by another process for {LOCK_TIMEOUT_S:.0f} s") from None
                time.sleep(0.02)
        _HELD.depth = 1
        try:
            yield
        finally:
            _HELD.depth = 0
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _serialized(function):
    """Run a registry operation (its load, change and save) under the registry lock."""
    @functools.wraps(function)
    def run(*args, **kwargs):
        with _locked():
            return function(*args, **kwargs)
    return run


def _revision(path: Path) -> tuple[str | None, bool | None]:
    """(HEAD sha, has local changes) of a Git checkout; (None, None) without version control."""
    def git(*args):
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=20, check=False)

    head = git("rev-parse", "HEAD")
    if head.returncode != 0:
        return None, None
    dirty = git("status", "--porcelain")
    return head.stdout.strip(), (bool(dirty.stdout.strip()) if dirty.returncode == 0 else None)


def detect_stacks(path: Path) -> list[dict]:
    """Stacks the files show, each with its basis (the file that shows it); detection is a hint, never a support claim."""
    from .adapters import runner_adapters
    from .adapters.technologies import project_technologies
    from .workspace import project_files

    try:
        files = project_files(path)
    except (OSError, ValueError):
        return []
    found = project_technologies(path, files, [])
    items = ([found["language"]] if found.get("language") else []) + list(found.get("technologies") or [])
    out = [{"name": item.get("name"), "basis": f"{item.get('basis')}: {item.get('evidence')}"} for item in items]
    out += [{"name": f"runner:{a.adapter_id}", "basis": "recognized by its adapter"} for a in runner_adapters(path)]
    return out


def add(path: str | Path, name: str | None = None, phase: str = "unknown", criticality: str = "unknown",
        needs: list[str] | None = None) -> Project:
    path = Path(path).resolve()
    if not path.is_dir():
        raise PortfolioError(f"{path} is not a folder")
    home = assertiva_home()
    if home == path or home.is_relative_to(path):
        raise PortfolioError(f"ASSERTIVA_HOME ({home}) must be outside the project ({path})")
    name = name or path.name
    if not _NAME.match(name):
        raise PortfolioError(f"{name!r} is not a usable project name (letters, digits, . _ -)")
    if phase not in PHASES:
        raise PortfolioError(f"phase must be one of {', '.join(PHASES)}")
    return _register(path, name, phase, criticality, needs, detect_stacks(path))


@_serialized
def _register(path: Path, name: str, phase: str, criticality: str, needs: list[str] | None, stacks: list[dict]) -> Project:
    data = _load()
    existing = data["projects"].get(name)
    if existing and existing.get("path") not in (None, str(path)):
        raise PortfolioError(f"{name} is already registered for {existing['path']}; choose another --name")
    project = Project(**existing) if existing else Project(name=name)
    project.path, project.phase, project.criticality = str(path), phase, criticality
    project.needs = list(needs or project.needs)
    project.stacks = stacks
    data["projects"][name] = asdict(project)
    _save(data)
    return project


@_serialized
def get(name: str) -> Project:
    data = _load()
    if name not in data["projects"]:
        raise PortfolioError(f"{name} is not in the portfolio (assertiva portfolio add PATH)")
    return Project(**data["projects"][name])


def status(project: Project) -> dict:
    """What the evidence allows saying about a project now, without running anything."""
    last = project.runs[-1] if project.runs else None
    head, dirty = _revision(Path(project.path)) if project.path and Path(project.path).is_dir() else (None, None)
    if last is None:
        state = "UNKNOWN"
        why = "never audited through the portfolio"
    elif last.get("tests_status") in ("BLOCKED",) and last.get("executed"):
        state, why = "BLOCKED", "the last audit could not run the tests: " + "; ".join(last.get("blocked_because", [])[:2])
    elif head is None or last.get("revision") is None:
        state, why = "UNKNOWN", "no version control revision to compare with the audited one"
    elif last["revision"] != head or dirty or last.get("dirty"):
        state, why = "STALE", f"audited {str(last['revision'])[:12]}, checked out {head[:12]}" + (" with local changes" if dirty else "")
    else:
        state, why = "CURRENT", f"audited at the checked-out revision {head[:12]}"
    last_real = next((r for r in reversed(project.runs) if r.get("executed") and r.get("tests_status") in ("PASS", "FAIL")), None)
    return {"name": project.name, "status": state, "why": why, "head": head, "phase": project.phase,
            "last_audit": last and {k: last.get(k) for k in ("at", "revision", "tests_status", "report")},
            "last_real_execution": last_real and {k: last_real.get(k) for k in ("at", "revision", "tests_status")},
            "needs": project.needs}


def summarize_run(report: dict, report_path: str | None) -> dict:
    """A portfolio-sized summary of one audit report: identity, counting units kept apart, findings by severity, and
    what did not run. Never a score."""
    current = (report.get("states") or {}).get("current") or {}
    runs = current.get("runs") or []
    engine = [r for r in runs if r.get("provenance") == "ENGINE_EXECUTED"]
    manifest = report.get("execution_manifest") or {}
    findings = report.get("findings") or []
    severities: dict[str, int] = {}
    for f in findings:
        severities[f.get("severity") or "info"] = severities.get(f.get("severity") or "info", 0) + 1
    statuses = {r.get("status") for r in engine}
    tests_status = ("FAIL" if "FAIL" in statuses else "BLOCKED" if "BLOCKED" in statuses else "PASS" if statuses == {"PASS"}
                    else "UNKNOWN" if engine else "NOT_RUN")
    return {
        "at": _now(), "run_id": report.get("run_id"), "report": report_path,
        "revision": (manifest.get("code") or {}).get("vcs_revision"), "dirty": (manifest.get("code") or {}).get("local_changes"),
        "tree_digest": (manifest.get("code") or {}).get("tree_digest"),
        "assertiva_version": (manifest.get("engine") or {}).get("assertiva_version"),
        "executed": bool(engine), "tests_status": tests_status,
        "blocked_because": [lim for r in engine if r.get("status") == "BLOCKED" for lim in (r.get("limitations") or [])[:1]],
        # counting units, never added together
        "units": {"static_definitions": sum((v or {}).get("tests") or 0 for v in
                                            ((report.get("test_effectiveness") or {}).get("languages") or {}).values()),
                  "invocations": sum(r.get("invocations") or 0 for r in engine),
                  "imported_results": sum(r.get("invocations") or 0 for r in runs if r.get("provenance") != "ENGINE_EXECUTED"),
                  "mutants": sum(sum((m.get("counts") or {}).values()) for m in current.get("mutation") or [])},
        "findings_by_severity": severities,
        "finding_codes": sorted({f.get("code") for f in findings if f.get("code")}),
        "not_evidenced": list((report.get("claim_boundary") or {}).get("not_evidenced") or [])[:10],
    }


@_serialized
def record_audit(name: str, report: dict, report_path: str | None) -> dict:
    data = _load()
    if name not in data["projects"]:
        raise PortfolioError(f"{name} is not in the portfolio")
    summary = summarize_run(report, report_path)
    data["projects"][name]["runs"].append(summary)
    _save(data)
    return summary


def audit(name: str, execute: bool = False, python: str | None = None, timeout_s: float | None = None) -> dict:
    """Run the ordinary audit on a registered project and record its summary (the report itself stays where audits
    write it)."""
    from .adapters import timeout_override
    from .audit import run_audit
    from .report import write_report
    from .workspace import state_dir

    project = get(name)
    if not project.path or not Path(project.path).is_dir():
        raise PortfolioError(f"{name} has no local checkout to audit ({project.path})")
    root = Path(project.path)
    with timeout_override(timeout_s):
        report = run_audit(root, execute=execute, python=python)
    report_path = str(write_report(report, state_dir(root, "reports"), "audit"))
    return record_audit(name, report, report_path)


# --- Assertiva feedback --------------------------------------------------------------------------------------------

def feedback_id(kind: str, rule: str, signature: str) -> str:
    """Stable identity of one Assertiva issue: the same kind, rule and sanitized signature is the same feedback."""
    normalized = re.sub(r"\s+", " ", signature.strip().lower())
    return "AFB-" + hashlib.sha256(f"{kind}|{rule}|{normalized}".encode()).hexdigest()[:10]


@_serialized
def add_feedback(project: str, kind: str, rule: str, signature: str, reproducer: str, engine_version: str,
                 run_id: str | None = None, note: str = "") -> dict:
    """Record (or add a sighting to) feedback about Assertiva. ``reproducer`` must be sanitized and synthetic: a
    description or a path to a synthetic fixture, never the audited project's code or data."""
    if kind not in FEEDBACK_KINDS:
        raise PortfolioError(f"feedback kind must be one of {', '.join(FEEDBACK_KINDS)}")
    if not reproducer.strip():
        raise PortfolioError("feedback needs a sanitized reproducer (a synthetic fixture or a description)")
    data = _load()
    if project not in data["projects"]:
        raise PortfolioError(f"{project} is not in the portfolio")
    fid = feedback_id(kind, rule, signature)
    entry = data["feedback"].get(fid) or {"feedback_id": fid, "kind": kind, "rule": rule, "signature": signature,
                                          "reproducer": reproducer, "state": "OBSERVED", "history": [], "sightings": []}
    entry["sightings"].append({"project": project, "run_id": run_id, "engine_version": engine_version, "at": _now(), "note": note})
    if entry["state"] in ("FIXED_IN_ASSERTIVA_BRANCH", "RETESTED_WITH_ASSERTIVA", "VERIFIED_AT_SHA"):
        entry["history"].append({"from": entry["state"], "to": "REGRESSION", "at": _now(), "evidence": f"seen again in {project}"})
        entry["state"] = "REGRESSION"
    data["feedback"][fid] = entry
    _save(data)
    return entry


@_serialized
def move_feedback(fid: str, state: str, evidence: str) -> dict:
    """Move feedback to ``state`` with the evidence for it (a test, a commit, a run). Moving to FIXED or later needs a
    commit or run reference in the evidence; no state is ever erased."""
    if state not in FEEDBACK_STATES:
        raise PortfolioError(f"state must be one of {', '.join(FEEDBACK_STATES)}")
    if not evidence.strip():
        raise PortfolioError("a state change needs its evidence")
    if state in ("FIXED_IN_ASSERTIVA_BRANCH", "RETESTED_WITH_ASSERTIVA", "VERIFIED_AT_SHA") and not re.search(r"\b[0-9a-f]{7,40}\b|run[:= ]", evidence):
        raise PortfolioError(f"{state} needs a commit SHA or a run reference in the evidence")
    data = _load()
    if fid not in data["feedback"]:
        raise PortfolioError(f"no feedback {fid}")
    entry = data["feedback"][fid]
    entry["history"].append({"from": entry["state"], "to": state, "at": _now(), "evidence": evidence})
    entry["state"] = state
    _save(data)
    return entry


@_serialized
def report(include_paths: bool = False) -> dict:
    """The portfolio view: each project's status and last summary, and Assertiva feedback apart. Local paths are left
    out unless asked for (the view may be shared)."""
    data = _load()
    projects = []
    for name in sorted(data["projects"]):
        project = Project(**data["projects"][name])
        row = {**status(project), "stacks": project.stacks, "criticality": project.criticality,
               "last_summary": project.runs[-1] if project.runs else None, "audits": len(project.runs)}
        if include_paths:
            row["path"] = project.path
        elif row.get("last_summary"):
            row["last_summary"] = {k: v for k, v in row["last_summary"].items() if k != "report"}
        projects.append(row)
    return {"schema": SCHEMA, "generated_at": _now(), "projects": projects,
            "assertiva_feedback": sorted(data["feedback"].values(), key=lambda f: f["feedback_id"]),
            "note": "statuses are what each project's own evidence allows; projects are not ranked or scored against each other"}


def discover(owner: str) -> list[dict]:
    """Repositories of ``owner`` as listed by the authenticated GitHub CLI: metadata only, nothing cloned or added."""
    if not _NAME.match(owner):
        raise PortfolioError(f"{owner!r} is not a GitHub owner name")
    listed = subprocess.run(["gh", "repo", "list", owner, "--limit", "1000", "--json",
                             "name,url,visibility,isArchived,primaryLanguage,defaultBranchRef,pushedAt"],
                            capture_output=True, text=True, timeout=120, check=False)
    if listed.returncode != 0:
        raise PortfolioError("GitHub discovery needs an authenticated `gh` CLI: " + (listed.stderr.strip().splitlines() or ["?"])[-1])
    out = []
    for repo in json.loads(listed.stdout or "[]"):
        out.append({"name": repo.get("name"), "url": repo.get("url"), "visibility": (repo.get("visibility") or "").lower(),
                    "archived": repo.get("isArchived"), "language": (repo.get("primaryLanguage") or {}).get("name"),
                    "default_branch": (repo.get("defaultBranchRef") or {}).get("name"), "pushed_at": repo.get("pushedAt"),
                    "suggested_phase": "archived" if repo.get("isArchived") else "unknown"})
    return out
