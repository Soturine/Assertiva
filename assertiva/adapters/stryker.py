"""StrykerJS (JavaScript/TypeScript mutation testing), run by Assertiva on a disposable copy of the state measured.

Stryker must be installed by the project (``@stryker-mutator/core`` and the runner plugin for its test runner in its
``node_modules``); Assertiva never installs it. The run uses the project's own installed node_modules (linked into the
copy, never copied), the project's test runner through Stryker's plugin (Jest or Vitest), and options Assertiva sets:
``--disableBail`` so every detecting test is recorded, ``--incremental false`` so nothing is carried over, the JSON
reporter written outside the copy, and the files to mutate. The project's own Stryker configuration file, when present,
is kept for everything else. The report is the mutation-testing-elements JSON Assertiva already reads; it carries the
mutated sources and the tests, which tie the run to the state.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from assertiva.models import MutationRun
from assertiva.process import execution_refusal, run_command

TOOL = "StrykerJS"
KEY = "stryker"
MAX_MUTANTS = 300
_RUNNERS = {"jest": "@stryker-mutator/jest-runner", "vitest": "@stryker-mutator/vitest-runner"}
_JS_SUFFIXES = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue", ".svelte")


def _package(root: Path) -> dict:
    try:
        return json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def test_runner(root: Path) -> str | None:
    """The project's test runner Stryker can drive (Jest or Vitest), from its declared dependencies."""
    package = _package(root)
    deps = {**(package.get("dependencies") or {}), **(package.get("devDependencies") or {})}
    for runner in ("vitest", "jest"):
        if runner in deps:
            return runner
    return None


def applies(root: Path) -> bool:
    return (root / "package.json").is_file() and test_runner(root) is not None


def availability(root: Path) -> str | None:
    """Why Stryker cannot run here, or None."""
    from assertiva.adapters.jest import node_executable

    runner = test_runner(root)
    if runner is None:
        return "the project declares neither Jest nor Vitest, the runners the Stryker integration drives"
    if not (root / "node_modules" / "@stryker-mutator" / "core" / "bin" / "stryker.js").is_file():
        return "StrykerJS is not installed in the project's node_modules (@stryker-mutator/core); Assertiva does not install it"
    plugin = _RUNNERS[runner]
    if not (root / "node_modules" / Path(*plugin.split("/")) / "package.json").is_file():
        return f"the Stryker plugin for {runner} is not installed ({plugin}); Assertiva does not install it"
    if not node_executable():
        return "Node.js was not found (PATH or ASSERTIVA_NODE)"
    return None


def describe(root: Path, python: str, origin: Path) -> dict:
    """Applies to a package.json project tested with Jest or Vitest; runs with the origin's installed StrykerJS."""
    runner = test_runner(root)
    found = applies(root)
    return {"applies": found, "runner": runner, "blocked": availability(origin) if found else None,
            "why": f"package.json declares {runner}" if found else "no Jest or Vitest project"}


def execute(state_root: Path, python: str, targets: list[str], origin: Path, option: dict) -> MutationRun:
    return run(state_root, targets, origin=origin)


def unsafe_target(root: Path, target: str) -> str | None:
    """Why Stryker must not rewrite ``target`` under ``root``; see ``mutation.unsafe_target``."""
    from assertiva.adapters.mutation import unsafe_target as check

    return check(root, target, _JS_SUFFIXES)


def run(state_root: str | Path, targets: list[str], origin: str | Path | None = None, timeout_s: float = 3600.0) -> MutationRun:
    """Mutate ``targets`` (files relative to ``state_root``) with the project's StrykerJS and test runner."""
    from assertiva.adapters.jest import node_executable
    from assertiva.adapters.mutation import load_mutation_report
    from assertiva.workspace import link_installed, remove_tree, snapshot

    state_root = Path(state_root)
    origin = Path(origin or state_root)
    result = MutationRun(source=f"{TOOL} run by Assertiva on {', '.join(targets)}", tool=TOOL, orchestrated=True, targets=tuple(targets))
    refusal = execution_refusal()
    if refusal:
        result.error = refusal
        return result
    bad = {t: reason for t in targets if (reason := unsafe_target(state_root, t))}
    if not targets or bad:
        result.error = ("mutation targets must be source files inside the project, reached without links: "
                        + ("; ".join(f"{t}: {why}" for t, why in bad.items()) or "none given"))
        return result
    blocked = availability(origin)
    if blocked:
        result.error = blocked
        return result
    runner = test_runner(state_root)
    with tempfile.TemporaryDirectory(prefix="assertiva-stryker-") as tmp:
        tmp = Path(tmp)
        copy = snapshot(state_root, tmp / "state")
        try:
            link_installed(copy, origin, ["node_modules"])  # the project's installed tooling, linked, never copied
            in_copy = {t: reason for t in targets if (reason := unsafe_target(copy, t))}
            if in_copy:
                result.error = "mutation targets are not plain files in the copy: " + "; ".join(f"{t}: {why}" for t, why in in_copy.items())
                return result
            report = tmp / "mutation.json"
            own = _project_config(copy)
            config = {**own.get("values", {}),
                      # what Assertiva needs to conclude anything, over the project's own settings
                      "testRunner": runner, "plugins": [_RUNNERS[runner]], "mutate": list(targets),
                      "reporters": ["json"], "jsonReporter": {"fileName": str(report)}, "disableBail": True,
                      "incremental": False, "concurrency": 2, "tempDirName": ".stryker-tmp", "timeoutMS": 30000,
                      "cleanTempDir": "always"}
            config_file = tmp / "stryker.assertiva.json"
            config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")
            command = [node_executable(), str(copy / "node_modules" / "@stryker-mutator" / "core" / "bin" / "stryker.js"), "run", str(config_file)]
            result.config = {"test_runner": runner, "disableBail": True, "incremental": False, "concurrency": 2,
                             "timeout_ms": 30000, "max_mutants": MAX_MUTANTS, "project_config": own.get("name")}
            if own.get("ignored"):
                result.limitations.append(own["ignored"])
            executed = run_command(command, copy, timeout_s=timeout_s, output_limit=1 << 20)
            if not report.is_file():
                # Stryker refuses to start when the initial test run fails: nothing was concluded
                result.error = f"{TOOL} produced no report ({executed.summary()})"
                return result
            parsed = load_mutation_report(report)
        finally:
            remove_tree(copy)
    if parsed.error:
        result.error = parsed.error
        return result
    for field in ("mutants", "counts", "sources", "test_sources", "test_locations", "test_names", "killers_complete", "incremental", "reused", "tool_version"):
        setattr(result, field, getattr(parsed, field))
    result.limitations = [*result.limitations, *parsed.limitations, "mutants were executed by Assertiva on a disposable copy of this state",
                          "the project's installed node_modules was linked into the copy (not isolated; never copied)"]
    if len(result.mutants) > MAX_MUTANTS:
        result.limitations.append(f"{len(result.mutants)} mutants exceed the budget of {MAX_MUTANTS}; narrow the targets next time")
    if not executed.ok:
        result.limitations.append(f"{TOOL} exited with an error ({executed.summary()}); results it did not finish are UNKNOWN")
    return result


def _project_config(root: Path) -> dict:
    """The project's own Stryker settings when they can be read without running code (a JSON file); a JavaScript
    configuration would have to be executed to read, so it is named and not used."""
    for name in ("stryker.conf.json", "stryker.config.json", ".stryker.conf.json"):
        path = root / name
        if path.is_file():
            try:
                return {"name": name, "values": json.loads(path.read_text(encoding="utf-8"))}
            except ValueError:
                return {"name": name, "ignored": f"{name} could not be read as JSON; Stryker ran with Assertiva's settings only"}
    for path in sorted(root.glob("stryker.conf.*")) + sorted(root.glob("stryker.config.*")):
        return {"name": path.name, "ignored": f"{path.name} is code (reading it would run it); Stryker ran with Assertiva's settings only"}
    return {}
