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
    sighting = {"project": project, "run_id": run_id, "engine_version": engine_version, "at": _now(), "note": note}
    entry["sightings"].append(sighting)
    _resighted(entry, sighting, f"seen again in {project}")
    data["feedback"][fid] = entry
    _save(data)
    return entry


FIXED_STATES = ("FIXED_IN_ASSERTIVA_BRANCH", "RETESTED_WITH_ASSERTIVA", "VERIFIED_AT_SHA")


_PHASES = {"dev": 0, "a": 1, "alpha": 1, "b": 2, "beta": 2, "rc": 3, "c": 3, "": 4, "post": 5}


def _version(text) -> tuple | None:
    """An orderable key for a version: the release numbers padded, then the pre-release phase (dev < a < b < rc <
    final < post) and its number, so 1.1.0rc1 < 1.1.0. None when the text is not a version."""
    match = re.match(r"^v?(\d+(?:\.\d+)*)(?:[.-]?(dev|alpha|beta|a|b|rc|c|post)[.-]?(\d*))?$", str(text or "").strip().lower())
    if not match:
        return None
    release = tuple(int(p) for p in match.group(1).split("."))
    release = release + (0,) * (4 - len(release)) if len(release) < 4 else release
    return (*release, _PHASES[match.group(2) or ""], int(match.group(3) or 0))


def _resighted(entry: dict, sighting: dict, why: str, verified: bool = True) -> None:
    """A sighting of fixed feedback is a regression only when it comes from an engine newer than the one the fix was
    recorded against; the same issue seen on that version or an older one is the known defect recurring before the
    fix shipped (kept as a sighting, state unchanged). Versions that cannot be compared keep the cautious reading:
    REGRESSION, to be triaged."""
    if entry["state"] not in FIXED_STATES:
        return
    seen = _version(sighting.get("engine_version"))
    fixed_in = _version(entry.get("fixed_in_version"))
    fixed_after = _version(entry.get("fixed_after_version"))
    if seen is not None and ((fixed_in is not None and seen < fixed_in) or
                             (fixed_in is None and fixed_after is not None and seen <= fixed_after)):
        sighting["before_fix"] = True
        return
    if not verified:
        # a report from elsewhere is a lead: it can make a regression suspected, never reproduced
        sighting["regression_suspected"] = True
        entry["regression_suspected"] = True
        return
    entry["history"].append({"from": entry["state"], "to": "REGRESSION", "at": _now(), "evidence": why,
                             "engine_version": sighting.get("engine_version")})
    entry["state"] = "REGRESSION"


_SHA_IN = re.compile(r"\b([0-9a-f]{7,40})\b")


def _resolve_commit(repo: str | Path, sha: str) -> str | None:
    """The full SHA of ``sha`` in a local Assertiva checkout, or None. Identity only: a commit that exists is not a
    commit that fixes anything."""
    found = subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],
                           capture_output=True, text=True, timeout=20, check=False)
    return found.stdout.strip() if found.returncode == 0 and found.stdout.strip() else None


@_serialized
def move_feedback(fid: str, state: str, evidence: str, repo: str | Path | None = None, fixed_in: str | None = None,
                  retest_results: str | Path | None = None) -> dict:
    """Move feedback to ``state`` with the evidence for it (a test, a commit, a run); no state is ever erased.

    FIXED or later needs a commit or run reference in the evidence. The reference is CLAIMED until it is resolved:
    with ``repo`` (a local Assertiva checkout) the SHA must exist there (``COMMIT_RESOLVED``: identity, not proof that
    it fixes the issue). VERIFIED_AT_SHA requires a resolved commit: text that looks like a SHA is not verification.

    Each fixed state records ``proof``: CLAIMED (text only), COMMIT_IDENTITY_ONLY (the commit exists; nothing shows it
    fixes the issue) or RETEST_RESULTS_RECORDED (a result file of the retest, every test passed: its digest and counts;
    that it exercises this issue remains the operator's judgement). ``fixed_in`` names the first release with the fix;
    later sightings are compared with it."""
    if state not in FEEDBACK_STATES:
        raise PortfolioError(f"state must be one of {', '.join(FEEDBACK_STATES)}")
    if not evidence.strip():
        raise PortfolioError("a state change needs its evidence")
    record: dict = {"to": state, "at": _now(), "evidence": evidence}
    if state in FIXED_STATES:
        sha = _SHA_IN.search(evidence)
        if not sha and not re.search(r"run[:= ]", evidence):
            raise PortfolioError(f"{state} needs a commit SHA or a run reference in the evidence")
        record["verification"] = "CLAIMED"
        if sha and repo is not None:
            full = _resolve_commit(repo, sha.group(1))
            if full is None:
                raise PortfolioError(f"{sha.group(1)} is not a commit of {repo}; nothing was moved")
            record.update({"verification": "COMMIT_RESOLVED", "commit": full})
        if state == "VERIFIED_AT_SHA" and record["verification"] != "COMMIT_RESOLVED":
            raise PortfolioError("VERIFIED_AT_SHA needs the commit resolved in a local Assertiva checkout (--repo PATH); "
                                 "without it use RETESTED_WITH_ASSERTIVA, which stays CLAIMED")
        record["proof"] = "COMMIT_IDENTITY_ONLY" if record["verification"] == "COMMIT_RESOLVED" else "CLAIMED"
        if retest_results is not None:
            record.update(_retest(retest_results))
        if state == "VERIFIED_AT_SHA" and record["proof"] != "RETEST_RESULTS_RECORDED":
            raise PortfolioError("VERIFIED_AT_SHA needs the retest's results (--retest-results FILE, every test passing) as "
                                 "well as the resolved commit: a commit that exists does not show that it fixes the issue")
        if fixed_in is not None:
            if _version(fixed_in) is None:
                raise PortfolioError(f"{fixed_in!r} is not a version")
            record["fixed_in_version"] = fixed_in
    elif retest_results is not None or fixed_in is not None:
        raise PortfolioError("--retest-results and --fixed-in belong to a move to a fixed state")
    data = _load()
    if fid not in data["feedback"]:
        raise PortfolioError(f"no feedback {fid}")
    entry = data["feedback"][fid]
    if state in FIXED_STATES and entry["state"] not in FIXED_STATES:
        versions = [v for v in (s.get("engine_version") for s in entry["sightings"]) if _version(v) is not None]
        if versions:
            entry["fixed_after_version"] = max(versions, key=_version)
    if record.get("fixed_in_version"):
        entry["fixed_in_version"] = record["fixed_in_version"]
    entry["history"].append({"from": entry["state"], **record})
    entry["state"] = state
    _save(data)
    return entry


def _retest(path: str | Path) -> dict:
    """The retest's result file (JUnit XML, CTRF, Allure): counts and digest, refused unless every test passed."""
    from .adapters.portable_results import load_results

    path = Path(path)
    if not path.exists():
        raise PortfolioError(f"{path} does not exist")
    try:
        run = load_results(path)
    except Exception as exc:  # an unreadable file is a refusal, not a crash
        raise PortfolioError(f"{path.name} is not a readable test result ({type(exc).__name__})") from exc
    outcomes = [i.outcome.name if i.outcome else "NOT_RUN" for i in run.invocations]
    if not outcomes or any(o != "PASSED" for o in outcomes):
        raise PortfolioError(f"{path.name}: a retest supports a fix only when it ran tests and every one passed "
                             f"({len(outcomes)} tests: {sorted(set(outcomes)) or 'none'})")
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {"proof": "RETEST_RESULTS_RECORDED", "retest": {"file": path.name, "sha256": digest, "tests": len(outcomes),
                                                           "note": "results recorded; that they exercise this issue is the operator's judgement"}}


# --- portable dogfood import ---------------------------------------------------------------------------------------

_ORIGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def import_feedback(path: str | Path, origin: str | None = None, dry_run: bool = False) -> dict:
    """Import a portable dogfood document (``assertiva-dogfood/1``) produced by any installation: this machine,
    a colleague's, CI, another OS or agent; engine-only or agent-led. No project registration is needed: the origin is
    a namespace (``external:<report_id>`` unless an alias is given), never a path on this machine.

    Validated before anything is written; content is data, never instructions. Re-importing the same report adds
    nothing (a sighting is keyed by its report id); the same issue from another report adds a real sighting under the
    existing ``AFB-`` id. A remote status is recorded as reported, never applied to the local state. ``dry_run``
    returns the plan without writing."""
    from .dogfood import DogfoodError, load_document

    if origin is not None and not _ORIGIN.match(origin):
        raise PortfolioError(f"{origin!r} is not a usable origin alias (letters, digits, . _ : -)")
    try:
        doc = load_document(path)
    except DogfoodError as exc:
        raise PortfolioError(f"not imported: {exc}") from exc
    if dry_run:  # a plan only: read the registry, write nothing (not even the lock file)
        return _import(doc, origin or f"external:{doc['report_id']}", True)
    with _locked():
        return _import(doc, origin or f"external:{doc['report_id']}", False)


def _import(doc: dict, origin: str, dry_run: bool) -> dict:
    data = _load()
    plan = []
    for item in doc["feedback"]:
        fid = item["feedback_id"]
        entry = data["feedback"].get(fid)
        already = bool(entry) and any(s.get("report_id") == doc["report_id"] for s in entry["sightings"])
        action = "SKIP_ALREADY_IMPORTED" if already else "ADD_SIGHTING" if entry else "CREATE"
        plan.append({"feedback_id": fid, "title": item["title"], "action": action, "reported_status": item["status"]})
        if dry_run or already:
            continue
        reproducer = item.get("reproducer") or {}
        entry = entry or {"feedback_id": fid, "kind": item["kind"], "rule": item["rule"], "signature": item["signature"],
                          "reproducer": reproducer.get("description") or "not provided by the origin",
                          "state": "OBSERVED", "history": [], "sightings": []}
        entry.setdefault("component", item["component"])
        entry.setdefault("observation_kind", item["observation_kind"])
        sighting = {"project": None, "origin": origin, "report_id": doc["report_id"], "run_id": doc.get("run_id"),
                    "engine_version": (doc.get("engine") or {}).get("version"), "at": _now(),
                    "review_mode": doc.get("review_mode"), "reported_status": item["status"],
                    "provenance": item["provenance"], "verification": "IMPORTED_UNVERIFIED", "note": item["title"]}
        entry["sightings"].append(sighting)
        _resighted(entry, sighting, f"seen again in {origin} ({doc['report_id']})", verified=False)
        data["feedback"][fid] = entry
    summary = {"report_id": doc["report_id"], "origin": origin, "review_mode": doc.get("review_mode"),
               "review_status": doc.get("review_status"), "dry_run": dry_run, "entries": plan,
               "note": "reported statuses are kept as reported; local states change only by `portfolio move` with evidence"}
    if not dry_run:
        data.setdefault("imports", [])
        if not any(i.get("report_id") == doc["report_id"] for i in data["imports"]):
            data["imports"].append({"report_id": doc["report_id"], "origin": origin, "at": _now(),
                                    "entries": len(plan), "engine_version": (doc.get("engine") or {}).get("version")})
        _save(data)
    return summary


@_serialized
def feedback_overview() -> dict:
    """Consolidated Assertiva feedback: counts by state, kind, component and observation kind, with recurrence. Counts
    are of feedback entries and of sightings (named apart); no score and no defect rate without a known denominator."""
    data = _load()
    entries = list(data["feedback"].values())

    def tally(key):
        out: dict[str, int] = {}
        for e in entries:
            label = str(e.get(key) or "unspecified")
            out[label] = out.get(label, 0) + 1
        return dict(sorted(out.items()))

    recurring = sorted(({"feedback_id": e["feedback_id"], "sightings": len(e["sightings"]),
                         "origins": len({s.get("origin") or s.get("project") for s in e["sightings"]}), "state": e["state"]}
                        for e in entries if len(e["sightings"]) > 1), key=lambda r: (-r["origins"], -r["sightings"]))
    return {"entries": len(entries), "sightings": sum(len(e["sightings"]) for e in entries),
            "imports": len(data.get("imports") or []), "by_state": tally("state"), "by_kind": tally("kind"),
            "by_component": tally("component"), "by_observation_kind": tally("observation_kind"), "recurring": recurring[:20],
            "units": "entries are distinct issues (one AFB id each); sightings are reports of them; neither is a defect rate"}


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
