"""Reproducing one declared check (what CI, a hook or a script declares) in a disposable copy.

One path for audit (`--run-check`) and improve (delivery qualification). The record keeps what was
actually executed, apart from what was declared: the argv, the command's own exit status (a signal,
timeout or start failure is never a pass), duration, an output digest, the revision and environment it
ran in, its scope (per-test outcomes only through a native runner adapter) and how far it is equivalent
to the declared CI step, dimension by dimension. A local reproduction never proves that CI ran it.

DISCOVERED is not AUTHORIZED: test runners and recognized side-effect-free checks run when named;
other kinds (migrations, containers, custom or unknown commands) can change state outside the copy and
run only when authorized; deploy/publish never runs; compound shell steps are not reproduced.
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .adapters.commands import is_compound, reproduction_plan
from .candidate import StageStatus
from .models import BudgetDecision, RunEvidence
from .process import redact, run_command
from .verification import VerificationKind


@dataclass
class Reproduction:
    record: dict
    status: StageStatus
    run: RunEvidence | None = None  # per-test evidence when a native runner adapter reproduced the check
    budget: list[BudgetDecision] = field(default_factory=list)

    @property
    def executed(self) -> bool:
        return self.status is not StageStatus.NOT_RUN


def environment_identity(python: str | None) -> dict:
    return {"platform": platform.system(), "machine": platform.machine(), "python": str(python or sys.executable)}


def _platform_family(name: str) -> str | None:
    name = name.lower()
    return next((family for family, keys in (("Linux", ("ubuntu", "linux", "debian", "alpine")), ("Windows", ("windows", "win")),
                                             ("Darwin", ("macos", "darwin", "osx"))) if any(k in name for k in keys)), None)


def _parity(check, executed: str, revision: dict, status: StageStatus, adapter_id: str | None) -> list[dict]:
    """How far this local reproduction is equivalent to the declared step: one entry per dimension."""
    values = check.metadata.get("matrix_values") or {}
    local = platform.system()
    declared_os = values.get("os") or []
    families = {_platform_family(str(v)) for v in declared_os}
    if not declared_os:
        env = ("UNKNOWN", f"ran on {local}; the step does not state an operating system")
    elif len(declared_os) == 1 and families == {local}:
        env = ("SAME", f"ran on {local}; declared {declared_os[0]}")
    elif local in families:
        env = ("PARTIAL", f"ran on {local} only; declared {', '.join(map(str, declared_os))}")
    else:
        env = ("DIFFERENT", f"ran on {local}; declared {', '.join(map(str, declared_os))}")
    other = {k: v for k, v in values.items() if k != "os" and v}
    if other:
        env = (env[0] if env[0] in ("DIFFERENT", "UNKNOWN") else "PARTIAL",
               env[1] + "; declared runtimes " + ", ".join(f"{k} {'/'.join(map(str, v))}" for k, v in sorted(other.items()))
               + " were not reproduced as a matrix")
    services = check.metadata.get("services") or []
    rev = revision.get("vcs_revision")
    return [
        {"dimension": "command", "status": "SAME" if executed == "SAME" else "ADAPTED",
         "detail": "the declared command" if executed == "SAME" else executed},
        {"dimension": "selection", "status": "SAME", "detail": "the declared arguments select the tests"
         + (f" (run through the {adapter_id} adapter)" if adapter_id else "")},
        {"dimension": "revision", "status": "LOCAL",
         "detail": f"{revision.get('label', 'local tree')} {revision.get('digest', '')[:12]}" + (f" at {rev[:12]}" if rev else "")
         + (" with local changes" if revision.get("dirty") else "") + "; which revision CI ran is UNKNOWN"},
        {"dimension": "environment", "status": env[0], "detail": env[1]},
        {"dimension": "services", "status": "DIFFERENT" if services else "SAME",
         "detail": ("declared services not started: " + ", ".join(services)) if services else "no services declared"},
        {"dimension": "result", "status": "LOCAL",
         "detail": f"local {status.value}; the CI result is UNKNOWN (CI providers are never queried)"},
    ]


def _base_record(check) -> dict:
    return {"check_id": check.check_id, "kind": check.kind.value, "origin": check.origin.value, "command": check.command,
            "gate": check.gate.value}


def reproduce_check(
    check,
    copy: Callable[[], Path],
    adapters: list,
    python: str | None,
    revision: dict,
    authorized: Callable[[object], bool],
    reusable: list[RunEvidence] = (),
    authorize_hint: str = "",
) -> Reproduction:
    """Reproduce ``check`` in the disposable copy returned by ``copy()`` (created only if something runs)."""
    record = _base_record(check)
    stage = f"check:{check.check_id}"
    if check.metadata.get("matrix"):
        record["limitation"] = f"only the local environment was reproduced, not matrix {check.metadata['matrix']}"
    # a compound step (`runner | tail`, `a && b`) is never reproduced: its status is not the runner's
    runner = None if is_compound(check.command or "") else next(
        ((a, args) for a in adapters if hasattr(a, "reproduction_args") and (args := a.reproduction_args(check)) is not None), None)
    if runner:
        adapter, args = runner
        reused = next((r for r in reusable if r.adapter_id == adapter.adapter_id), None)
        if reused is not None and adapter.equivalent_to_default(args):
            run, decision = reused, BudgetDecision(stage, "REUSED", "equivalent to the run already measured (only cosmetic flags differ)")
        else:
            run, decision = adapter.run(copy(), args=args), BudgetDecision(stage, "EXECUTED", f"reproduced through the {adapter.adapter_id} adapter")
        status = run.status
        record |= {
            "status": status.value,
            "detail": ("reused the equivalent run already measured: " if decision.decision == "REUSED" else "")
                      + f"{len(run.invocations)} invocations, {len(run.collection_errors)} collection errors"
                      + (f"; exit {run.exit_code}" if run.exit_code is not None else ""),
            "scope": "per-test outcomes (native runner adapter)",
            "execution": {"via": adapter.adapter_id, "argv": [redact(str(c)) for c in run.command], "exit_code": run.exit_code,
                          "duration_s": run.wall_clock_s, "reused": decision.decision == "REUSED"},
        }
        record["parity"] = _parity(check, f"run through the {adapter.adapter_id} adapter with the declared arguments",
                                   revision, status, adapter.adapter_id)
        record["environment"] = environment_identity(python)
        return Reproduction(record, status, run, [decision])
    plan = reproduction_plan(check, python or sys.executable)
    if plan.argv is None:
        record |= {"status": StageStatus.NOT_RUN.value, "detail": plan.reason}
        return Reproduction(record, StageStatus.NOT_RUN, budget=[BudgetDecision(stage, "NOT_RUN", plan.reason)])
    if plan.needs_authorization and not authorized(check):
        reason = (f"discovered, not authorized: a {check.kind.value} check can change state outside the disposable copy "
                  f"(databases, registries, containers); it runs only when authorized{authorize_hint}")
        record |= {"status": StageStatus.NOT_RUN.value, "detail": reason, "authorization": "REQUIRED"}
        return Reproduction(record, StageStatus.NOT_RUN, budget=[BudgetDecision(stage, "NOT_RUN", reason)])
    env = dict(os.environ)
    env["PATH"] = str(Path(python or sys.executable).parent) + os.pathsep + env.get("PATH", "")
    result = run_command(list(plan.argv), copy(), env=env)
    if result.error or result.timed_out:
        status = StageStatus.BLOCKED
    else:
        status = StageStatus.PASS if result.ok else StageStatus.FAIL
    try:
        declared = shlex.split(check.command.strip(), posix=True)
    except ValueError:
        declared = []
    executable = shutil.which(plan.argv[0], path=env["PATH"]) or plan.argv[0]
    record |= {
        "status": status.value,
        "detail": result.summary(),
        "scope": "whole command: per-test outcomes are UNKNOWN",
        "execution": {"via": "command", "argv": [redact(c) for c in plan.argv], "executable": redact(executable),
                      "exit_code": result.returncode, "signal": result.signal, "timed_out": result.timed_out,
                      "start_error": result.error, "duration_s": result.duration_s, "output_sha256": result.output_sha256,
                      "output_tail": redact((result.stderr or result.stdout).strip()[-1000:])},
    }
    if plan.needs_authorization:
        record["authorization"] = "AUTHORIZED"
    same = list(plan.argv) == declared
    record["parity"] = _parity(check, "SAME" if same else f"interpreter resolved to {plan.argv[0]}", revision, status, None)
    record["environment"] = environment_identity(python)
    if check.kind is VerificationKind.TEST:
        record["limitation"] = "; ".join(filter(None, [record.get("limitation"),
                                                       "no native adapter read this runner's results: per-test outcomes are UNKNOWN"]))
    return Reproduction(record, status, budget=[BudgetDecision(stage, "EXECUTED", "reproduced as a whole command in a disposable copy")])
