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
    """Why the tool must not write ``target`` under ``root``, or None. The tool rewrites the file in place, so every
    component from the root to the file must be a real directory or file (no symlink or junction: a link in a copy
    can point back outside it, and a write through it changes the outside), and the resolved file must lie under the
    resolved root. Checked on the project and again on the copy the tool runs in."""
    from assertiva.workspace import is_link

    rel = Path(target)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or rel.suffix != ".py":
        return "not a Python file path relative to the project"
    current = root
    for part in rel.parts:
        current = current / part
        if is_link(current):
            return f"{current.relative_to(root).as_posix()} is a link: a write through it can reach outside the copy"
    if not current.is_file():
        return "not a file in the project"
    try:
        current.resolve().relative_to(root.resolve())
    except ValueError:
        return "resolves outside the project"
    return None


def run(state_root: str | Path, python: str, targets: list[str], test_paths: list[str], timeout_s: float = 60.0,
        budget_s: float = 3600.0) -> MutationRun:
    """Mutate ``targets`` (files relative to ``state_root``) and run the project's pytest for each mutant."""
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
            test_command = [_posix(python), "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *test_paths]
            baseline = run_command(test_command, copy, timeout_s=budget_s)
            if not baseline.ok:
                result.error = f"the tests do not pass on this state before mutation ({baseline.summary()}); no mutant was run"
                return result
            config, db = tmp / "mutation.toml", tmp / "session.sqlite"
            result.config = {"timeout_s": float(timeout_s), "test_command": [_posix(part) for part in test_command[1:]],
                             "distributor": "local", "operators": "Cosmic Ray defaults", "max_mutants": MAX_MUTANTS}
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
