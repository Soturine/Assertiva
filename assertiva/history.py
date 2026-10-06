"""Revision-aware assurance history: a local SQLite store plus the stability, duration and
failure-fingerprint semantics computed from it.

History enriches audit/improve; it is never a precondition. It keeps only evidence useful later
(revision, environment identity, adapter, invocation outcomes, durations, attempts, selection
reasons, failure fingerprints, artifact identity, coverage and qualification summaries), never
stdout, attachments, raw reports or secrets. Set ``ASSERTIVA_HISTORY=off`` to disable it.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePath

from .models import Outcome, RunEvidence
from .process import redact

SCHEMA_VERSION = 1
MIN_FLAKY_FAILURES = 2  # a single failure never makes a test flaky
MIN_STABLE_SAMPLES = 3
MIN_P50_SAMPLES = 5
MIN_P95_SAMPLES = 20
_FAILING = {Outcome.FAILED.value, Outcome.ERROR.value}
_PASSING = {Outcome.PASSED.value, Outcome.XFAILED.value}

_SCHEMA = """
CREATE TABLE states (
    id INTEGER PRIMARY KEY, recorded_at TEXT NOT NULL, workflow TEXT NOT NULL, state TEXT NOT NULL,
    revision TEXT NOT NULL, vcs_revision TEXT, selection TEXT, qualification TEXT, coverage TEXT, artifacts TEXT
);
CREATE TABLE runs (
    id INTEGER PRIMARY KEY, state_id INTEGER NOT NULL REFERENCES states(id), adapter TEXT NOT NULL,
    environment TEXT NOT NULL, environment_label TEXT, status TEXT NOT NULL, wall_clock_s REAL
);
CREATE TABLE invocations (
    run_id INTEGER NOT NULL REFERENCES runs(id), invocation_id TEXT NOT NULL, declaration_id TEXT, outcome TEXT,
    duration_s REAL, attempt INTEGER NOT NULL, attempts INTEGER, selection_reason TEXT, fingerprint TEXT, failure_signature TEXT
);
CREATE INDEX invocations_by_id ON invocations(invocation_id);
"""


class Stability(str, Enum):
    OBSERVED_UNSTABLE_CURRENT_RUN = "OBSERVED_UNSTABLE_CURRENT_RUN"  # failed and passed within this run (reruns/retries)
    HISTORICALLY_FLAKY = "HISTORICALLY_FLAKY"  # same revision and environment: repeated failures and passes
    CONSISTENT_FAILURE = "CONSISTENT_FAILURE"
    ENVIRONMENT_SPECIFIC = "ENVIRONMENT_SPECIFIC"  # same revision fails in one environment, passes in another
    NO_INSTABILITY_OBSERVED = "NO_INSTABILITY_OBSERVED"  # not proof of stability
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def classify_attempts(outcomes) -> Stability:
    """Stability of one invocation within a single run (first execution plus reruns/retries)."""
    values = [o.value if isinstance(o, Outcome) else o for o in outcomes]
    if len(values) < 2 or None in values:
        return Stability.INSUFFICIENT_EVIDENCE
    if all(v in _FAILING for v in values):
        return Stability.CONSISTENT_FAILURE
    if any(v in _FAILING for v in values):
        return Stability.OBSERVED_UNSTABLE_CURRENT_RUN
    return Stability.NO_INSTABILITY_OBSERVED if len(set(values)) == 1 else Stability.INSUFFICIENT_EVIDENCE


@dataclass(frozen=True)
class Observation:
    state_id: int
    revision: str
    environment: str
    outcome: str | None
    duration_s: float | None
    attempt: int
    attempts: int | None
    fingerprint: str | None


def classify(observations: list[Observation], revision: str, current_state: int | None = None) -> tuple[Stability, str]:
    """Stability of one invocation at ``revision`` from recorded observations (current run included)."""
    current = [o for o in observations if o.state_id == current_state]
    if current and (classify_attempts([o.outcome for o in current]) is Stability.OBSERVED_UNSTABLE_CURRENT_RUN
                    or any((o.attempts or 1) > 1 and o.outcome in _PASSING for o in current)):
        return Stability.OBSERVED_UNSTABLE_CURRENT_RUN, "failed and passed within this run; the failure is kept as evidence"
    same = [o for o in observations if o.revision == revision and o.outcome is not None]
    by_env: dict[str, list[int]] = {}
    for o in same:
        fails, passes = by_env.setdefault(o.environment, [0, 0])
        retried = (o.attempts or 1) > 1 and o.outcome in _PASSING  # a pass after failed attempts counts as both
        by_env[o.environment] = [fails + (o.outcome in _FAILING or retried), passes + (o.outcome in _PASSING)]
    for env, (fails, passes) in by_env.items():
        if fails >= MIN_FLAKY_FAILURES and passes:
            return Stability.HISTORICALLY_FLAKY, f"same revision and environment: {fails} failing and {passes} passing observations"
    failing_envs = [e for e, (f, p) in by_env.items() if f >= MIN_FLAKY_FAILURES and not p]
    passing_envs = [e for e, (f, p) in by_env.items() if p and not f]
    if failing_envs and passing_envs:
        return Stability.ENVIRONMENT_SPECIFIC, f"fails in {len(failing_envs)} environment(s), passes in {len(passing_envs)} at this revision"
    fails = sum(f for f, _ in by_env.values())
    passes = sum(p for _, p in by_env.values())
    if fails >= MIN_FLAKY_FAILURES and not passes:
        return Stability.CONSISTENT_FAILURE, f"{fails} failing observations at this revision, none passing"
    if passes >= MIN_STABLE_SAMPLES and not fails:
        return Stability.NO_INSTABILITY_OBSERVED, f"{passes} passing observations at this revision; not proof of stability"
    return Stability.INSUFFICIENT_EVIDENCE, f"{fails} failing and {passes} passing observations at this revision"


def duration_summary(samples: list[float]) -> dict:
    """p50/p95 (nearest rank) only when the sample is large enough; never an invented statistic."""
    values = sorted(s for s in samples if s is not None)

    def rank(q):
        return values[max(math.ceil(q * len(values)) - 1, 0)]

    return {
        "samples": len(values),
        "p50": rank(0.5) if len(values) >= MIN_P50_SAMPLES else None,
        "p95": rank(0.95) if len(values) >= MIN_P95_SAMPLES else None,
    }


_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_NORMALIZE = (
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "<TS>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<ID>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<ADDR>"),
    (re.compile(r"(?:[A-Za-z]:)?[\\/](?:[^\s:'\"\\/<>]+[\\/])+([^\s:'\"\\/<>]+)"), r"\1"),  # paths -> file name
    (re.compile(r"\b[0-9a-fA-F]{12,}\b"), "<HEX>"),
    (re.compile(r"\b\d{6,}\b"), "<N>"),
    (re.compile(r"\b\d+(?:\.\d+)?\s?(?:ms|s)\b"), "<DUR>"),
)
_TYPE = re.compile(r"\b([A-Z][A-Za-z0-9_.]*(?:Error|Exception|Failure|Exit|Timeout))\b")
_LOCATION = re.compile(r"\b([\w.-]+\.(?:py|js|cjs|mjs|ts|tsx|java|kt)):(\d+)")


def fingerprint(message: str | None, stage: str = "run") -> tuple[str, str] | None:
    """(fingerprint, readable signature) of a failure: deterministic, conservative, no model involved.

    Signals: collection/run stage, exception/assertion type, first source location, the first
    message line with timestamps, ids, addresses, temporary paths and durations normalized.
    """
    if not message:
        return None
    text = redact(_ANSI.sub("", message))
    for pattern, replacement in _NORMALIZE:
        text = pattern.sub(replacement, text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    first = re.sub(r"\s+", " ", lines[0])[:160] if lines else ""
    kind = _TYPE.search(text)
    kind = kind.group(1).rsplit(".", 1)[-1] if kind else ("AssertionError" if re.search(r"\bassert", text) else "UNKNOWN")
    location = _LOCATION.search(text)
    where = f"{location.group(1)}:{location.group(2)}" if location else ""
    digest = hashlib.sha256("|".join((stage, kind, where, first)).encode()).hexdigest()[:16]
    return digest, f"[{stage}] {kind}{' at ' + where if where else ''}: {first}"[:200]


def environment_identity(run: RunEvidence) -> tuple[str, str]:
    executable = run.command[0] if run.command else run.adapter_id
    label = f"{platform.system()}-{platform.machine()} {PurePath(executable).name}"
    return hashlib.sha256(f"{platform.system()}|{platform.machine()}|{executable}".encode()).hexdigest()[:12], label


class HistoryError(RuntimeError):
    """The history store cannot be used; callers continue without it."""


class HistoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            self.db.executescript(_SCHEMA)
            self.db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.db.commit()
        elif version != SCHEMA_VERSION:
            self.db.close()
            raise HistoryError(f"history schema {version} is not supported by this version (expects {SCHEMA_VERSION})")

    @classmethod
    def for_project(cls, root: str | Path) -> HistoryStore | None:
        """The project's store, or None when disabled. Raises HistoryError when unusable."""
        if os.environ.get("ASSERTIVA_HISTORY", "").lower() in ("0", "off", "false", "no"):
            return None
        from .workspace import state_dir

        try:
            return cls(state_dir(root, "history") / "history.sqlite3")
        except (OSError, sqlite3.Error, ValueError) as exc:
            raise HistoryError(f"history store unavailable: {exc}") from exc

    def close(self) -> None:
        self.db.close()

    def record(self, workflow: str, state: str, revision: str, vcs_revision: str | None, runs: list[RunEvidence],
               selection: dict | None = None, qualification: dict | None = None, coverage: dict | None = None,
               artifacts: list | None = None, attempt: int = 1, selection_reasons: dict[str, str] | None = None) -> int:
        def blob(value):
            return json.dumps(value, sort_keys=True) if value else None

        with self.db:
            state_id = self.db.execute(
                "INSERT INTO states (recorded_at, workflow, state, revision, vcs_revision, selection, qualification, coverage, artifacts)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), workflow, state, revision, vcs_revision,
                 blob(selection), blob(qualification), blob(coverage), blob(artifacts)),
            ).lastrowid
            for run in runs:
                environment, label = environment_identity(run)
                run_id = self.db.execute(
                    "INSERT INTO runs (state_id, adapter, environment, environment_label, status, wall_clock_s) VALUES (?, ?, ?, ?, ?, ?)",
                    (state_id, run.adapter_id, environment, label, run.status.value, run.wall_clock_s),
                ).lastrowid
                rows = []
                for inv in run.invocations:
                    failing = inv.outcome in (Outcome.FAILED, Outcome.ERROR)
                    fp = fingerprint(inv.message) if failing else None
                    source = (inv.source_paths or ("",))[0]
                    rows.append((run_id, inv.invocation_id, inv.declaration_id, inv.outcome.value if inv.outcome else None,
                                 inv.duration_s, attempt, getattr(inv, "attempts", None), (selection_reasons or {}).get(source),
                                 fp[0] if fp else None, fp[1] if fp else None))
                self.db.executemany("INSERT INTO invocations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        return state_id

    def add_attempts(self, state_id: int, attempt_outcomes: dict[str, list[tuple]]) -> None:
        """Later attempts (reruns) of invocations already recorded in ``state_id``, kept beside the first outcome."""
        with self.db:
            for invocation_id, attempts in attempt_outcomes.items():
                row = self.db.execute(
                    "SELECT i.run_id, i.declaration_id FROM invocations i JOIN runs r ON r.id = i.run_id"
                    " WHERE r.state_id = ? AND i.invocation_id = ? AND i.attempt = 1", (state_id, invocation_id)).fetchone()
                if row is None:
                    continue
                for number, (outcome, duration, message) in enumerate(attempts, start=2):
                    value = outcome.value if isinstance(outcome, Outcome) else outcome
                    fp = fingerprint(message) if value in _FAILING else None
                    self.db.execute("INSERT INTO invocations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                    (row[0], invocation_id, row[1], value, duration, number, None, None,
                                     fp[0] if fp else None, fp[1] if fp else None))

    def observations(self, invocation_ids) -> dict[str, list[Observation]]:
        found: dict[str, list[Observation]] = {}
        ids = list(dict.fromkeys(invocation_ids))
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            query = (
                "SELECT i.invocation_id, s.id, s.revision, r.environment, i.outcome, i.duration_s, i.attempt, i.attempts, i.fingerprint"
                " FROM invocations i JOIN runs r ON r.id = i.run_id JOIN states s ON s.id = r.state_id"
                f" WHERE i.invocation_id IN ({','.join('?' * len(chunk))}) ORDER BY s.id"
            )
            for row in self.db.execute(query, chunk):
                found.setdefault(row[0], []).append(Observation(*row[1:]))
        return found

    def fingerprint_count(self, value: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM invocations WHERE fingerprint = ?", (value,)).fetchone()[0]

    def state_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM states").fetchone()[0]


def record_state(root, workflow: str, state: str, revision: str, vcs_revision: str | None, runs: list[RunEvidence],
                 reruns: dict[str, list[tuple]] | None = None, **summaries) -> dict:
    """Record one measured state and return its history summary; history problems never fail the caller."""
    try:
        store = HistoryStore.for_project(root)
    except HistoryError as exc:
        return {"enabled": False, "limitations": [str(exc)]}
    if store is None:
        return {"enabled": False, "limitations": ["history is disabled (ASSERTIVA_HISTORY)"]}
    try:
        state_id = store.record(workflow, state, revision, vcs_revision, runs, **summaries)
        if reruns:
            store.add_attempts(state_id, reruns)
        return summarize(store, state_id, revision, runs)
    except sqlite3.Error as exc:
        return {"enabled": False, "limitations": [f"history could not be written: {exc}"]}
    finally:
        store.close()


def summarize(store: HistoryStore, state_id: int, revision: str, runs: list[RunEvidence], limit: int = 50) -> dict:
    """History evidence for the invocations of one recorded state (for reports)."""
    invocations = [inv for run in runs for inv in run.invocations]
    observed = store.observations(inv.invocation_id for inv in invocations)
    entries, timings = [], []
    for inv in invocations:
        history = observed.get(inv.invocation_id, [])
        stability, note = classify(history, revision, current_state=state_id)
        timing = duration_summary([o.duration_s for o in history])
        fp = fingerprint(inv.message) if inv.outcome in (Outcome.FAILED, Outcome.ERROR) else None
        if timing["p50"] is not None:
            timings.append({"invocation_id": inv.invocation_id, **timing})
        if stability in (Stability.NO_INSTABILITY_OBSERVED, Stability.INSUFFICIENT_EVIDENCE) and not fp:
            continue
        entries.append({
            "invocation_id": inv.invocation_id, "stability": stability.value, "note": note, "observations": len(history),
            "fingerprint": fp[0] if fp else None, "failure_signature": fp[1] if fp else None,
            "fingerprint_occurrences": store.fingerprint_count(fp[0]) if fp else 0,
        })
    return {
        "enabled": True, "store": str(store.path), "states_recorded": store.state_count(),
        "invocations": entries[:limit], "durations": sorted(timings, key=lambda t: -(t["p95"] or t["p50"]))[:10],
        "limitations": ["history covers only runs recorded on this machine",
                        "a single failure is never called flaky; percentiles need enough samples"],
    }
