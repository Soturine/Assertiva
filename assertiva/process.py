"""Bounded, non-interactive subprocess execution with timing and timeout provenance."""

from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import signal
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
    signal: str | None = None  # POSIX: the signal that ended the process
    output_sha256: str | None = None  # of the complete stdout + stderr, before truncation

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and self.error is None

    def summary(self) -> str:
        if self.error:
            return f"could not start: {self.error}"
        if self.timed_out:
            return f"timed out after {self.timeout_s}s"
        if self.signal:
            return f"ended by {self.signal} in {self.duration_s}s"
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


# --- the environment project code sees ----------------------------------------------------
# A disposable copy protects the project tree, not the machine: project code still runs as the user,
# with network access. What Assertiva can withhold is the credentials its own environment carries.
# Credential-looking variables are removed from every child environment (names are recorded, values
# never); a project lists what its tests legitimately need in `.assertiva.toml` ([execution] env).
_CREDENTIAL_NAME = re.compile(
    r"(?i)(token|secret|passw(or)?d|passphrase|credential|api[-_]?key|private[-_]?key|access[-_]?key|auth|session|cookie)"
)
_CREDENTIAL_PREFIXES = (
    "AWS_", "AZURE_", "ARM_", "GOOGLE_", "GCLOUD", "CLOUDSDK_", "GCP_", "DIGITALOCEAN_", "HEROKU_", "VAULT_", "TWINE_",
    "PYPI_", "DOCKER_", "KUBECONFIG", "SSH_AUTH_SOCK", "SSH_AGENT_PID", "GPG_", "GH_", "CI_JOB_",
    "SYSTEM_ACCESSTOKEN", "ACTIONS_RUNTIME", "ACTIONS_ID_TOKEN", "ACTIONS_CACHE",
)
_URL_WITH_PASSWORD = re.compile(r"://[^/\s:@]+:[^@\s]+@")
PASSTHROUGH: frozenset[str] = frozenset()  # set by the command from the project's configuration


def is_credential(name: str, value: str) -> bool:
    if name.startswith("ASSERTIVA_"):
        return False
    return (name.upper().startswith(_CREDENTIAL_PREFIXES) or bool(_CREDENTIAL_NAME.search(name))
            or bool(_URL_WITH_PASSWORD.search(value)))


def child_environment(env: dict) -> dict:
    """``env`` without credential-looking variables (except those the project passes through)."""
    withheld = {name for name, value in env.items() if name not in PASSTHROUGH and is_credential(name, value)}
    if withheld and _SCOPES:
        _SCOPES[-1].setdefault("__withheld__", set()).update(withheld)
    return {name: value for name, value in env.items() if name not in withheld}


@contextmanager
def passthrough(names):
    """Let the project's declared variables (``[execution] env``) reach its code during this block."""
    global PASSTHROUGH
    previous, PASSTHROUGH = PASSTHROUGH, frozenset(names)
    try:
        yield
    finally:
        PASSTHROUGH = previous


def withheld_variables() -> list[str]:
    """Names of the variables withheld from child processes in the current run."""
    return sorted(_SCOPES[-1].get("__withheld__", ())) if _SCOPES else []


# --- run-scoped capability evidence ----------------------------------------------------
# Capability probes are evidence about an environment at a moment: reused within one run,
# re-probed by the next run (a long-lived process must not remember a removed module).
_SCOPES: list[dict] = []


@contextmanager
def run_scope():
    """One run's capability evidence. Re-entrant: nested scopes share the outer run."""
    if _SCOPES:
        yield
        return
    _SCOPES.append({})
    try:
        yield
    finally:
        _SCOPES.pop()


def scoped(function):
    """Run ``function`` inside a run scope (sharing the caller's run when there is one)."""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        with run_scope():
            return function(*args, **kwargs)
    return wrapper


def _interpreter_identity(python: str) -> tuple:
    try:
        st = os.stat(python)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return ()


def module_available(python: str, module: str) -> bool:
    """Whether ``module`` imports in interpreter ``python`` (cached only within a run)."""
    key = (str(python), _interpreter_identity(str(python)), module)
    cache = _SCOPES[-1] if _SCOPES else None
    if cache is not None and key in cache:
        return cache[key]
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    available = run_command([str(python), "-c", f"import {module}"], Path.cwd(), env=env, timeout_s=60).ok
    if cache is not None:
        cache[key] = available
    return available


_SECRET_ARG = re.compile(r"(?i)((?:token|password|passwd|secret|api[-_]?key|auth)[^=:\s]*[=:])([^\s]+)")
_URL_CREDENTIALS = re.compile(r"(://[^/\s:@]+:)([^@\s]+)(@)")


def redact(text: str) -> str:
    """Hide credential-looking values (key=value, url user:password@) in recorded commands."""
    return _URL_CREDENTIALS.sub(r"\1***\3", _SECRET_ARG.sub(r"\1***", text))


def _kill_tree(proc: subprocess.Popen) -> None:
    """End the process and everything it started (its own session / process group)."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


def run_command(command: list[str], cwd: str | Path, env: dict | None = None, timeout_s: float = 900.0) -> CommandResult:
    """Run ``command`` non-interactively in its own process group, bounded by ``timeout_s``.

    The result is the command's own exit status (or the signal that ended it, a timeout or a start
    failure); a timeout ends the whole process tree, not just the direct child."""
    started = time.perf_counter()
    result = CommandResult(
        command=[str(c) for c in command], cwd=str(cwd), started_at=_now(), duration_s=0.0, timeout_s=timeout_s,
    )
    trace("command_start", command=[redact(c) for c in result.command], cwd=result.cwd, timeout_s=timeout_s)
    env = child_environment(dict(os.environ if env is None else env))
    env[DEPTH_ENV] = str(current_depth() + 1)
    if os.environ.get(TARGETS_ENV):
        env[TARGETS_ENV] = os.environ[TARGETS_ENV]
    group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    try:
        proc = subprocess.Popen(result.command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, **group)
    except OSError as exc:
        result.error = str(exc)
    else:
        try:
            out, err = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            result.timed_out = True
            _kill_tree(proc)
            try:
                out, err = proc.communicate(timeout=30)
            except subprocess.TimeoutExpired:  # a descendant that left the group still holds the pipes
                out, err = b"", b""
                for stream in (proc.stdout, proc.stderr):
                    stream.close()
                proc.wait()
        result.output_sha256 = hashlib.sha256((out or b"") + b"|" + (err or b"")).hexdigest()
        result.stdout, result.stderr = _tail(out), _tail(err)
        if not result.timed_out:
            result.returncode = proc.returncode
            if proc.returncode < 0 and os.name != "nt":
                try:
                    result.signal = signal.Signals(-proc.returncode).name
                except ValueError:
                    result.signal = f"signal {-proc.returncode}"
    result.duration_s = round(time.perf_counter() - started, 3)
    trace(
        "command_end", command=[redact(c) for c in result.command[:3]], returncode=result.returncode, timed_out=result.timed_out,
        error=result.error, signal=result.signal, duration_s=result.duration_s,
    )
    return result
