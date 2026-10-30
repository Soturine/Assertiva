"""Node.js built-in test runner adapter (`node --test`): the project's own Node runs its own test files.

Recognized when a package.json script runs `node --test` (directly or through another script) and no Jest or Vitest
is declared. The run is `node --test --test-reporter=junit` with the destination outside the copy, read with the JUnit
reader: per-test outcomes, skips and failures with their messages. Node 20.13 / 21.3 or newer is needed for the JUnit
reporter; an older or missing Node is BLOCKED, never a pass. Assertiva installs nothing (no npm install, no npx).
"""

from __future__ import annotations

import re
import shlex
import tempfile
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import Outcome, RunEvidence
from assertiva.process import execution_refusal, run_command
from assertiva.verification import SupportLevel

from .base import AdapterCapability
from .jest import _package, node_executable
from .junit import load_junit

_NODE_TEST = re.compile(r"(?:^|[\s;&|])node\b(?P<options>(?:\s+--?[\w-]+(?:=\S+)?)*)\s+--test(?=\s|$)(?P<rest>[^;&|]*)")
_OPTIONS_WITH_VALUES = {"--test-name-pattern", "--test-reporter", "--test-reporter-destination", "--test-concurrency",
                        "--test-timeout", "--test-shard", "--import", "--require", "-r", "--loader"}
FORMAT_LIMITS = [
    "results are Node's JUnit reporter output: a test's declaration is its name within its file; subtests appear as "
    "separate cases",
    "no coverage is read from the built-in runner (--experimental-test-coverage is not used)",
]


def node_test_args(command: str) -> list[str] | None:
    """The test paths and filters a `node --test ...` command gives (None when the command does not run `node --test`)."""
    match = _NODE_TEST.search(command or "")
    if not match:
        return None
    try:
        tokens = shlex.split(match.group("rest"), posix=True)
    except ValueError:
        return None
    args, skip = [], False
    for token in tokens:
        if skip:
            args.append(token)
            skip = False
        elif token.split("=", 1)[0] in ("--test-reporter", "--test-reporter-destination"):
            skip = "=" not in token  # the run sets its own reporter and destination
        elif token in _OPTIONS_WITH_VALUES:
            args.append(token)
            skip = True
        else:
            args.append(token)
    return [a for a in args if not a.startswith("--test-reporter")]


def _script_args(root: Path) -> list[str] | None:
    """The arguments of the first script that runs `node --test`, following `npm run x` one level at a time."""
    scripts = _package(root).get("scripts") or {}
    for name in ("test", *sorted(scripts)):
        if name in scripts and (args := node_test_args(str(scripts[name]))) is not None:
            return args
    return None


def _identify(run: RunEvidence, report: Path, root: Path) -> None:
    """Node's JUnit `classname` is the literal `test`: the id becomes `<file relative to the project>::<name>`, so two
    files with a test of the same name stay two tests. Left unchanged when the report and the cases do not line up."""
    import xml.etree.ElementTree as ET

    try:
        cases = list(ET.parse(report).getroot().iter("testcase"))
    except ET.ParseError:
        return
    if len(cases) != len(run.invocations):
        run.limitations.append("test files could not be matched to every case: ids use Node's class name only")
        return
    from dataclasses import replace

    identified = []
    for inv, case in zip(run.invocations, cases):
        file = case.get("file")
        try:
            rel = Path(file).resolve().relative_to(root.resolve()).as_posix() if file else None
        except ValueError:
            rel = None
        test_id = f"{rel}::{case.get('name')}" if rel else None
        identified.append(replace(inv, invocation_id=test_id, declaration_id=test_id, materialization_id=test_id,
                                  source_paths=(rel,)) if test_id else inv)
    run.invocations = identified


def _version(text: str) -> tuple[int, int]:
    match = re.match(r"v?(\d+)\.(\d+)", text.strip())
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


class NodeTestAdapter:
    adapter_id = "node-test"
    tool = "node --test"

    def __init__(self, python: str | None = None, timeout_s: float = 900.0):
        self.timeout_s = timeout_s  # `python` is accepted for the common factory signature only

    def supports(self, root: Path) -> SupportLevel:
        package = _package(Path(root))
        deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        if "jest" in deps or "vitest" in deps:
            return SupportLevel.UNSUPPORTED  # those runners have their own adapters
        return SupportLevel.SUPPORTED if _script_args(Path(root)) is not None else SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        s, u = SupportLevel.SUPPORTED, SupportLevel.UNSUPPORTED
        return (
            AdapterCapability("native_collection", s, "node --test with the project's own file arguments or default patterns"),
            AdapterCapability("per_test_outcomes", s, "pass, fail, skip and todo from Node's JUnit reporter"),
            AdapterCapability("coverage", u, "the built-in runner's coverage is not read"),
            AdapterCapability("static_oracle_analysis", SupportLevel.UNKNOWN, "the JavaScript test facts apply to node:test files"),
        )

    def _blocked(self, reason: str, **fields) -> RunEvidence:
        return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[reason], **fields)

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        root = Path(root)
        refusal = execution_refusal()
        if refusal:
            return self._blocked(refusal)
        node = node_executable()
        if not node:
            return self._blocked("Node.js was not found (PATH or ASSERTIVA_NODE)")
        probe = run_command([node, "--version"], root, timeout_s=30)
        version = _version(probe.stdout or "")
        if not probe.ok or version < (20, 13) or version[0] == 21 and version < (21, 3):
            return self._blocked(f"Node {probe.stdout.strip() or '?'}: the JUnit test reporter needs Node 20.13 / 21.3 or newer")
        declared = list(args) if args is not None else (_script_args(root) or [])
        with tempfile.TemporaryDirectory(prefix="assertiva-node-test-") as tmp:
            out = Path(tmp) / "junit.xml"
            command = [node, "--test", "--test-reporter=junit", f"--test-reporter-destination={out}", *declared]
            result = run_command(command, root, timeout_s=self.timeout_s)
            if result.error or result.timed_out:
                return self._blocked(f"node --test could not run: {result.summary()}", command=command, wall_clock_s=result.duration_s)
            if not out.is_file() or not out.read_text(encoding="utf-8", errors="replace").strip():
                return self._blocked("node --test produced no results: " + " | ".join((result.stderr or result.stdout).strip().splitlines()[-3:]),
                                     command=command, wall_clock_s=result.duration_s, exit_code=result.returncode)
            run = load_junit(out)
            _identify(run, out, root)
        run.adapter_id, run.mode, run.command = self.adapter_id, "execute", command
        run.exit_code, run.wall_clock_s = result.returncode, result.duration_s
        run.metadata["provenance"] = "ENGINE_EXECUTED"
        run.metadata["node"] = (probe.stdout or "").strip()
        run.limitations = [lim for lim in run.limitations if "not executed by Assertiva" not in lim] + FORMAT_LIMITS
        outcomes = {inv.outcome for inv in run.invocations}
        if not run.invocations or outcomes <= {Outcome.SKIPPED, Outcome.NOT_RUN}:
            run.status = StageStatus.UNKNOWN
            run.limitations.append("no test was executed; this is not evidence of a passing suite")
        elif outcomes & {Outcome.FAILED, Outcome.ERROR} or result.returncode != 0:
            run.status = StageStatus.FAIL
        else:
            run.status = StageStatus.PASS
        return run

    def installed_dependencies(self) -> tuple[str, ...]:
        return ("node_modules",)

    def declared_matrix(self, root) -> dict[str, dict]:
        from .jest import JestAdapter

        return JestAdapter().declared_matrix(root)

    def static_signals(self, root) -> dict[str, int]:
        return {}

    def static_negative_paths(self, root) -> dict[str, list[str]]:
        return {}

    def reproduction_args(self, check) -> list[str] | None:
        """Arguments of a declared `node --test ...` step (or a script that runs it)."""
        if check.tool == self.tool and check.command and "${{" not in check.command:
            return node_test_args(check.command)
        return None

    def equivalent_to_default(self, args: list[str]) -> bool:
        return False
