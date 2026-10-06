"""Bounded, non-interactive subprocess execution with timing and timeout provenance."""

from __future__ import annotations

import json
import os
import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_LIMIT = 4000
# When set, every stage and command appends start/end events here *as they happen*, so an
# interrupted or hung run still shows the stage, command, start time and timeout in flight.
TRACE_PATH: Path | None = None
_stage: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def trace(event: str, **data) -> None:
    if TRACE_PATH is None:
        return
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACE_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"event": event, "at": _now(), "stage": _stage, **data}) + "\n")


@contextmanager
def traced_stage(name: str):
    global _stage
    previous, _stage = _stage, name
    started = time.perf_counter()
    trace("stage_start")
    try:
        yield
    finally:
        trace("stage_end", duration_s=round(time.perf_counter() - started, 3))
        _stage = previous


def _tail(text: str | bytes | None) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-OUTPUT_LIMIT:]


@dataclass
class CommandResult:
    command: list[str]
    cwd: str
    started_at: str
    duration_s: float
    timeout_s: float
    returncode: int | None = None
    timed_out: bool = False
    error: str | None = None  # could not start (missing interpreter/tool)
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None

    def summary(self) -> str:
        if self.error:
            return f"could not start: {self.error}"
        if self.timed_out:
            return f"timed out after {self.timeout_s}s"
        tail = (self.stderr or self.stdout).strip().splitlines()[-3:]
        return f"exit {self.returncode} in {self.duration_s}s" + (": " + " | ".join(tail) if tail and self.returncode else "")


# --- execution budget ------------------------------------------------------------------
# Every child process inherits depth + 1. Executing project code is refused at MAX_DEPTH:
# depth 0 (a user run) may run project tests (depth 1) whose own tests may qualify small
# fixtures (depth 2); anything deeper is self-qualification amplifying cost.
MAX_DEPTH = 2
DEPTH_ENV = "ASSERTIVA_DEPTH"
TARGETS_ENV = "ASSERTIVA_ACTIVE_TARGETS"


def current_depth() -> int:
    try:
        return max(int(os.environ.get(DEPTH_ENV, "0")), 0)
    except ValueError:
        return MAX_DEPTH  # unreadable: assume the budget is spent rather than unlimited


def execution_refusal() -> str | None:
    depth = current_depth()
    if depth >= MAX_DEPTH:
        return f"execution budget: nested Assertiva depth {depth} reached the limit of {MAX_DEPTH}; project code was not executed"
    return None


def _targets() -> list[str]:
    return [t for t in os.environ.get(TARGETS_ENV, "").split("|") if t]


def is_active(kind: str, identity: str) -> bool:
    """Whether an outer run is already producing this kind of evidence for this target."""
    return f"{kind}:{identity}" in _targets()


@contextmanager
def active_target(kind: str, identity: str):
    """Mark a target as being qualified so nested runs (child processes) can detect recursion."""
    previous = os.environ.get(TARGETS_ENV)
    os.environ[TARGETS_ENV] = "|".join([*_targets(), f"{kind}:{identity}"])
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(TARGETS_ENV, None)
        else:
            os.environ[TARGETS_ENV] = previous


_MODULES: dict[tuple[str, str], bool] = {}


def module_available(python: str, module: str) -> bool:
    """Whether ``module`` imports in interpreter ``python``; probed once per interpreter."""
    key = (str(python), module)
    if key not in _MODULES:
        env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
        _MODULES[key] = run_command([str(python), "-c", f"import {module}"], Path.cwd(), env=env, timeout_s=60).ok
    return _MODULES[key]


def run_command(command: list[str], cwd: str | Path, env: dict | None = None, timeout_s: float = 900.0) -> CommandResult:
    started = time.perf_counter()
    result = CommandResult(
        command=[str(c) for c in command], cwd=str(cwd), started_at=_now(), duration_s=0.0, timeout_s=timeout_s,
    )
    trace("command_start", command=result.command, cwd=result.cwd, timeout_s=timeout_s)
    env = dict(os.environ if env is None else env)
    env[DEPTH_ENV] = str(current_depth() + 1)
    if os.environ.get(TARGETS_ENV):
        env[TARGETS_ENV] = os.environ[TARGETS_ENV]
    try:
        completed = subprocess.run(
            result.command, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL, timeout=timeout_s,
        )
        result.returncode, result.stdout, result.stderr = completed.returncode, _tail(completed.stdout), _tail(completed.stderr)
    except subprocess.TimeoutExpired as exc:
        result.timed_out, result.stdout, result.stderr = True, _tail(exc.stdout), _tail(exc.stderr)
    except OSError as exc:
        result.error = str(exc)
    result.duration_s = round(time.perf_counter() - started, 3)
    trace(
        "command_end", command=result.command[:3], returncode=result.returncode, timed_out=result.timed_out,
        error=result.error, duration_s=result.duration_s,
    )
    return result
