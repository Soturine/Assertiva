"""Bounded, non-interactive subprocess execution with timing and timeout provenance."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_LIMIT = 4000


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


def run_command(command: list[str], cwd: str | Path, env: dict | None = None, timeout_s: float = 900.0) -> CommandResult:
    started = time.monotonic()
    result = CommandResult(
        command=[str(c) for c in command], cwd=str(cwd),
        started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), duration_s=0.0, timeout_s=timeout_s,
    )
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
    result.duration_s = round(time.monotonic() - started, 3)
    return result
