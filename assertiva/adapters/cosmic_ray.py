"""Cosmic Ray (Python mutation testing), run by Assertiva on a disposable copy of the state being measured.

Assertiva does not mutate code itself and does not install the tool: Cosmic Ray must be importable by the project's
interpreter (``pip install cosmic-ray`` in the environment the tests run in); otherwise the run is BLOCKED with that
reason. The tool mutates files in place, so it only ever runs inside a copy, with a configuration and session database
Assertiva writes outside that copy, and a test command Assertiva builds (the project's pytest, never a command read
from the project). The suite must pass on the copy before any mutant runs; otherwise nothing is concluded.

What the run proves: for each mutant of the named files, whether the whole test command failed (KILLED, or TIMEOUT)
or passed (SURVIVED) on this state. Cosmic Ray records no killing test, so per-test contribution is unknown; the
sources and tests it ran are recorded from the copy, which ties the run to the measured state.
"""

from __future__ import annotations

import json
import shlex
import tempfile
from pathlib import Path

from assertiva.models import MutationRun
from assertiva.process import execution_refusal, module_available, run_command

TOOL = "Cosmic Ray"
KEY = "cosmic-ray"
MAX_MUTANTS = 300  # one test-suite run per mutant: beyond this the targets must be narrowed
_LIMITS = [
    "Cosmic Ray runs the whole test command for each mutant and records no killing test: per-test contribution is unknown",
    "mutants were executed by Assertiva on a disposable copy of this state (the tool mutates files in place)",
]


def _posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def _cli(python: str, *args: str) -> list[str]:
    return [python, "-m", "cosmic_ray.cli", *args]


def _version(python: str, cwd: Path) -> str | None:
    probe = run_command([python, "-c", "import importlib.metadata as m; print(m.version('cosmic-ray'))"], cwd, timeout_s=60)
    return probe.stdout.strip() or None if probe.ok else None


def unsafe_target(root: Path, target: str) -> str | None:
    """Why Cosmic Ray must not rewrite ``target`` (a Python file) under ``root``; see ``mutation.unsafe_target``."""
    from assertiva.adapters.mutation import unsafe_target as check

    return check(root, target, (".py",))


_COMMANDS = {  # the runner the project declares, as the engine runs it with --execute; never swapped for another
    "pytest-native": ["-m", "pytest", "-x", "-q", "-p", "no:cacheprovider"],
    "unittest": ["-m", "unittest", "discover", "--failfast"],
    "django": ["manage.py", "test", "--noinput", "--failfast"],
}


def describe(root: Path, python: str, origin: Path) -> dict:
    """Applies to Python tests under one runner the project declares; never chooses a runner for it."""
    from assertiva.adapters import runner_adapters
    from assertiva.adapters.python_discovery import test_files

    runners = [a.adapter_id for a in runner_adapters(root, python) if a.adapter_id in _COMMANDS] if test_files(root) else []
    blocked = None
    if len(runners) > 1:
        blocked = (f"the project declares several Python runners ({', '.join(runners)}); keep the one to mutate with in "
                   ".assertiva.toml [tests] runners")
    elif runners and not module_available(python, "cosmic_ray"):
        blocked = f"{TOOL} is not installed in {python}; Assertiva does not install it"
    return {"applies": bool(runners), "blocked": blocked, "runner": runners[0] if len(runners) == 1 else None,
            "why": f"Python tests run by {', '.join(runners)}" if runners else "no Python tests under a supported runner"}


SELECTS_TESTS = True  # the baseline and every mutant can run only the tests the auditor names (--mutate-tests)


def execute(state_root: Path, python: str, targets: list[str], origin: Path, option: dict) -> MutationRun:
    return run(state_root, python, targets, test_paths=list(option.get("tests") or []), runner=option["runner"])


def run(state_root: str | Path, python: str, targets: list[str], test_paths: list[str], runner: str = "pytest-native",
        timeout_s: float = 60.0,
        budget_s: float = 3600.0) -> MutationRun:
    """Mutate ``targets`` (files relative to ``state_root``) and run the project's declared ``runner`` for each mutant."""
    from assertiva.adapters.mutation import cosmic_ray_dump
    from assertiva.workspace import remove_tree, snapshot

    state_root = Path(state_root)
    result = MutationRun(source=f"{TOOL} run by Assertiva on {', '.join(targets)}", tool=TOOL, orchestrated=True,
                         targets=tuple(targets), limitations=list(_LIMITS))
    refusal = execution_refusal()
    if refusal:
        result.error = refusal
        return result
    bad = {t: reason for t in targets if (reason := unsafe_target(state_root, t))}
    if not targets or bad:
        result.error = ("mutation targets must be Python files inside the project, reached without links: "
                        + ("; ".join(f"{t}: {why}" for t, why in bad.items()) or "none given"))
        return result
    if not module_available(python, "cosmic_ray"):
        result.error = (f"{TOOL} is not installed in {python}; Assertiva does not install it "
                        "(install cosmic-ray in the environment the tests run in, then rerun)")
        return result
    with tempfile.TemporaryDirectory(prefix="assertiva-mutation-") as tmp:
        tmp = Path(tmp)
        copy = snapshot(state_root, tmp / "state")
        try:
            in_copy = {t: reason for t in targets if (reason := unsafe_target(copy, t))}
            if in_copy:  # the copy must hold the targets as plain files too, or nothing is mutated
                result.error = "mutation targets are not plain files in the copy: " + "; ".join(f"{t}: {why}" for t, why in in_copy.items())
                return result
            if runner not in _COMMANDS:
                result.error = f"{TOOL} cannot run the {runner} runner"
                return result
            test_command = [_posix(python), *_COMMANDS[runner], *[_posix(t) for t in test_paths]]
            baseline = run_command(test_command, copy, timeout_s=budget_s)
            scope = "the selected tests" if test_paths else "the tests"
            if not baseline.ok:
                result.error = f"{scope} do not pass on this state before mutation ({baseline.summary()}); no mutant was run"
                return result
            if test_paths:  # AG-11: the auditor's selection, kept with the run; never presented as the whole suite
                result.config["test_selection"] = {"tests": list(test_paths), "baseline": "the selected tests passed",
                                                   "baseline_duration_s": baseline.duration_s, "whole_suite": "NOT_RUN"}
                result.limitations.append(
                    "only the selected tests ran for each mutant (" + ", ".join(test_paths[:5]) + "): a survivor may be "
                    "killed by a test outside the selection, and the rest of the suite was not run for this analysis")
            config, db = tmp / "mutation.toml", tmp / "session.sqlite"
            result.config = {**result.config, "timeout_s": float(timeout_s), "test_command": [_posix(part) for part in test_command[1:]],
                             "distributor": "local", "operators": "Cosmic Ray defaults", "max_mutants": MAX_MUTANTS,
                             "runner": runner}
            config.write_text(
                "[cosmic-ray]\n"
                f"module-path = {json.dumps([_posix(t) for t in targets])}\n"
                f"timeout = {float(timeout_s)}\n"
                "excluded-modules = []\n"
                f"test-command = {json.dumps(' '.join(shlex.quote(part) for part in test_command))}\n\n"
                "[cosmic-ray.distributor]\nname = \"local\"\n", encoding="utf-8")
            init = run_command(_cli(python, "init", str(config), str(db)), copy, timeout_s=600)
            if not init.ok:
                result.error = f"{TOOL} could not plan the mutants: {init.summary()}"
                return result
            planned = run_command(_cli(python, "dump", str(db)), copy, timeout_s=600, output_limit=1 << 26)
            count = len([line for line in planned.stdout.splitlines() if line.strip()])
            if count > MAX_MUTANTS:
                result.error = f"{count} mutants planned exceed the budget of {MAX_MUTANTS} test-suite runs; name fewer or smaller targets"
                return result
            executed = run_command(_cli(python, "exec", str(config), str(db)), copy, timeout_s=budget_s)
            dumped = run_command(_cli(python, "dump", str(db)), copy, timeout_s=600, output_limit=1 << 26)
            if not dumped.ok:
                result.error = f"{TOOL} results could not be read: {dumped.summary()}"
                return result
            result.mutants = cosmic_ray_dump(dumped.stdout)
            if not executed.ok:
                result.limitations.append(f"{TOOL} stopped before finishing ({executed.summary()}); unfinished mutants are UNKNOWN")
                result.finished = False
            else:
                result.finished = True
            result.tool_version = _version(python, copy)
            # what the run saw: the mutated files and the tests, read from the copy before it is removed
            from assertiva.adapters.python_discovery import test_files

            result.sources = {t: (copy / t).read_text(encoding="utf-8") for t in targets}
            result.test_sources = {p.relative_to(copy).as_posix(): p.read_text(encoding="utf-8", errors="replace")
                                   for p in test_files(copy)}
        finally:
            remove_tree(copy)
    from collections import Counter

    result.counts = dict(Counter(m.status.value for m in result.mutants))
    return result
