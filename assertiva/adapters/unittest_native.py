"""Native unittest and Django test evidence: the project's own runner, with a recording result class.

`python -m unittest ARGS` and `manage.py test ARGS` run as the project declares them (arguments from its CI when
one declaration exists), through `_unittest_evidence.py` copied next to the run: per-test outcomes (pass, fail,
error, skip, expected failure, unexpected success), subtests as parameter invocations, inherited methods, module
load errors as collection errors, and class/module fixture failures. Nothing is simulated from the exit code: a run
that records no test is UNKNOWN or BLOCKED, never a pass. Running it executes project code; callers run it in a
disposable copy, never in the project.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import Outcome, RunEvidence, TestInvocation
from assertiva.process import execution_refusal, module_available, run_command
from assertiva.verification import SupportLevel

from .base import AdapterCapability
from .python_discovery import declared_runners, python_runners
from .python_static import PythonStatic, measured_coverage

_MODULE = "assertiva_unittest_evidence"
_SOURCE = Path(__file__).with_name("_unittest_evidence.py")
_OUTCOMES = {"passed": Outcome.PASSED, "failed": Outcome.FAILED, "error": Outcome.ERROR, "skipped": Outcome.SKIPPED,
             "xfailed": Outcome.XFAILED, "xpassed": Outcome.XPASSED}
_RANK = [Outcome.ERROR, Outcome.FAILED, Outcome.XPASSED, Outcome.PASSED, Outcome.XFAILED, Outcome.SKIPPED]
_COSMETIC = {"-v", "-q", "--verbose", "--quiet", "-b", "--buffer", "--locals", "--noinput", "--no-input", "--force-color",
             "--no-color", "--timing"}
_COSMETIC_WITH_VALUE = {"-v", "--verbosity", "--durations"}


def _worst(outcomes: list[Outcome]) -> Outcome:
    return min(outcomes, key=_RANK.index)


def _strip_cosmetic(args: list[str]) -> list[str]:
    out, skip = [], False
    for i, arg in enumerate(args):
        if skip:
            skip = False
            continue
        if arg in _COSMETIC_WITH_VALUE and i + 1 < len(args) and args[i + 1].isdigit():
            skip = True
            continue
        if arg in _COSMETIC or arg.startswith(("--verbosity=", "--durations=")) or (arg.startswith("-v") and set(arg[1:]) == {"v"}):
            continue
        out.append(arg)
    return out


def normalize(records: list[dict], adapter_id: str, exit_code: int | None) -> RunEvidence:
    """Records written by the recording result -> run evidence (no execution)."""
    run = RunEvidence(adapter_id=adapter_id, mode="execute", status=StageStatus.UNKNOWN, exit_code=exit_code)
    items: dict[str, dict] = {}
    own: dict[str, list[dict]] = {}
    subtests: dict[str, list[dict]] = {}
    for record in records:
        kind = record.get("type")
        if kind == "session":
            run.metadata["session"] = {k: v for k, v in record.items() if k != "type"}
        elif kind == "item":
            items.setdefault(record["id"], record)
        elif kind == "load_error":
            name = record["id"].removeprefix("unittest.loader._FailedTest.")
            run.collection_errors.append(name)
            run.metadata.setdefault("error_sources", {})[name] = name.replace(".", "/") + ".py"
            run.metadata.setdefault("load_errors", {})[name] = record.get("message")
        elif kind == "fixture":
            outcome = _OUTCOMES.get(record.get("outcome"), Outcome.ERROR)
            run.invocations.append(TestInvocation(
                invocation_id=record["description"], declaration_id=record["description"], materialization_id=record["description"],
                outcome=outcome, message=record.get("message"), custom=True))
        elif kind == "outcome":
            (subtests if record.get("subtest") is not None else own).setdefault(record["id"], []).append(record)
    for test_id, item in items.items():
        cls, method, path = item.get("cls") or "", item.get("method") or "", item.get("file") or ""
        materialization = f"{path}::{cls.replace('.', '::')}::{method}" if path and method else test_id
        declared_by = item.get("declared_by") or cls
        declaration = f"{item.get('declared_file') or path}::{declared_by.replace('.', '::')}::{method}" if path and method else test_id
        sources = tuple(dict.fromkeys(filter(None, [path, item.get("declared_file")])))
        base = dict(declaration_id=declaration, materialization_id=materialization, inherited=declared_by != cls, source_paths=sources)
        mine = [_OUTCOMES.get(r["outcome"], Outcome.ERROR) for r in own.get(test_id, [])]
        subs = subtests.get(test_id, [])
        if subs:
            for record in subs:
                params = record["subtest"]
                run.invocations.append(TestInvocation(
                    invocation_id=f"{materialization}[{params}]", parameters_id=params, outcome=_OUTCOMES.get(record["outcome"], Outcome.ERROR),
                    duration_s=record.get("duration"), message=record.get("message"), **base))
            if any(o is not Outcome.PASSED for o in mine):  # failure outside the subtests, or a skip of the whole test
                bad = next(r for r in own[test_id] if _OUTCOMES.get(r["outcome"]) is not Outcome.PASSED)
                run.invocations.append(TestInvocation(invocation_id=materialization, outcome=_worst(mine), duration_s=bad.get("duration"),
                                                      message=bad.get("message"), **base))
            continue
        record = own.get(test_id, [{}])[-1]
        run.invocations.append(TestInvocation(
            invocation_id=materialization, outcome=_worst(mine) if mine else Outcome.NOT_RUN, duration_s=record.get("duration"),
            message=record.get("message"), **base))
    outcomes = {inv.outcome for inv in run.invocations}
    if any(inv.outcome is Outcome.XPASSED for inv in run.invocations):
        run.limitations.append("unittest counts an unexpected success (expectedFailure that passed) as a failure of the run")
    if run.collection_errors or outcomes & {Outcome.FAILED, Outcome.ERROR, Outcome.XPASSED}:
        run.status = StageStatus.FAIL
    elif not run.invocations or outcomes <= {Outcome.SKIPPED, Outcome.NOT_RUN}:
        run.status = StageStatus.UNKNOWN
        run.limitations.append("no test was executed; this is not evidence of a passing suite")
    elif exit_code == 0:
        run.status = StageStatus.PASS
    else:
        run.status = StageStatus.BLOCKED
        run.limitations.append(f"the runner exited with code {exit_code} although no recorded test failed")
    return run


class _RecordingRunner(PythonStatic):
    """Shared execution for runners driven through the recording result."""

    adapter_id = "unittest"

    def __init__(self, python: str | None = None, timeout_s: float = 900.0):
        self.python = python or sys.executable
        self.timeout_s = timeout_s

    def _declared_args(self, root: Path) -> tuple[list[str], str | None]:
        """Arguments of the project's single declared invocation of this runner (otherwise the defaults)."""
        commands = sorted(set(declared_runners(root).get(self.runner, [])))
        if len(commands) == 1:
            args = self._args_from(commands[0])
            if args is not None:
                return args, commands[0]
        return self.default_args(), None

    def _command(self, root: Path, args: list[str], plugin_dir: Path, coverage: bool) -> list[str]:
        raise NotImplementedError

    def collect_limit(self) -> str:
        return ""

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        root = Path(root)
        refusal = execution_refusal()
        if refusal:
            return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[refusal])
        declared_from = None
        if args is None:
            args, declared_from = self._declared_args(root)
        with tempfile.TemporaryDirectory(prefix=f"assertiva-{self.adapter_id}-") as tmp:
            plugin_dir = Path(tmp)
            (plugin_dir / f"{_MODULE}.py").write_text(_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
            evidence_file = plugin_dir / "evidence.jsonl"
            env = dict(os.environ)
            env["ASSERTIVA_EVIDENCE_FILE"] = str(evidence_file)
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            env["PYTHONPYCACHEPREFIX"] = str(Path(tempfile.gettempdir()) / "assertiva-pycache")
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(plugin_dir), env.get("PYTHONPATH")]))
            env["COVERAGE_FILE"] = str(plugin_dir / ".coverage")
            measure = coverage and module_available(self.python, "coverage")
            command = self._command(root, list(args), plugin_dir, measure)
            evidence = RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.UNKNOWN, command=command)
            if declared_from:
                evidence.metadata["arguments_from"] = declared_from
            result = run_command(command, root, env=env, timeout_s=self.timeout_s)
            evidence.wall_clock_s = result.duration_s
            if result.error or result.timed_out:
                evidence.status = StageStatus.BLOCKED
                evidence.limitations.append(f"{self.adapter_id} could not be executed: {result.summary()}")
                return evidence
            records = [json.loads(line) for line in evidence_file.read_text(encoding="utf-8").splitlines()] if evidence_file.exists() else []
            coverage_summary = measured_coverage(self.python, root, env, plugin_dir, self.timeout_s) if measure and records else None
        run = normalize(records, self.adapter_id, result.returncode)
        sources = run.metadata.get("error_sources", {})
        for name in list(sources):  # unittest names a module relative to its start directory
            suffix = name.replace(".", "/") + ".py"
            found = sorted(p.relative_to(root).as_posix() for p in root.rglob(Path(suffix).name)
                           if p.relative_to(root).as_posix().endswith(suffix))
            sources[name] = found[0] if len(found) == 1 else suffix
        run.command, run.wall_clock_s, run.coverage = command, result.duration_s, coverage_summary
        run.metadata.update(evidence.metadata)
        if coverage and not measure:
            run.limitations.append("coverage.py is not available in the target interpreter; coverage was not measured")
        if not any(r.get("type") == "session" for r in records):
            run.status = StageStatus.BLOCKED
            tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
            run.limitations.append(f"{self.adapter_id} produced no native evidence: " + " | ".join(tail))
        elif not run.invocations and not run.collection_errors and result.returncode not in (0, 5):
            run.status = StageStatus.BLOCKED
            tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
            run.limitations.append(f"{self.adapter_id} stopped before running any test: " + " | ".join(tail))
        run.limitations += [lim for lim in [self.collect_limit()] if lim]
        return run

    def reproduction_args(self, check) -> list[str] | None:
        if check.tool != self.tool or not check.command or "${{" in check.command or check.metadata.get("working_directory"):
            return None
        return self._args_from(check.command)

    def equivalent_to_default(self, args: list[str]) -> bool:
        return _strip_cosmetic(args) == _strip_cosmetic(self.default_args())

    def selection_args(self, tests: list[str]) -> list[str] | None:
        return None  # a file subset is not a stable label for these runners: the full suite runs, and says so


class UnittestAdapter(_RecordingRunner):
    adapter_id = "unittest"
    runner = "unittest"
    tool = "unittest"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if "unittest" in python_runners(root) else SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        s, u = SupportLevel.SUPPORTED, SupportLevel.UNSUPPORTED
        return (
            AdapterCapability("native_collection", s, "unittest discovery as declared; load errors are collection errors"),
            AdapterCapability("per_test_outcomes", s, "pass, fail, error, skip, expected failure, unexpected success"),
            AdapterCapability("parameterized_invocations", s, "subTest cases"),
            AdapterCapability("inherited_materialization", s),
            AdapterCapability("coverage", SupportLevel.UNKNOWN, "requires coverage.py in the target interpreter"),
            AdapterCapability("subset_selection", u, "a selected set runs the full suite"),
        )

    def default_args(self) -> list[str]:
        return ["discover"]

    def _args_from(self, command: str) -> list[str] | None:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return None
        if "unittest" not in tokens:
            return None
        return tokens[tokens.index("unittest") + 1:] or ["discover"]

    def _command(self, root: Path, args: list[str], plugin_dir: Path, coverage: bool) -> list[str]:
        module = ["-m", _MODULE, *args]
        return [self.python, "-m", "coverage", "run", "--branch", *module] if coverage else [self.python, *module]

    def collect_limit(self) -> str:
        return "unittest collects TestCase methods only; plain test functions are not run by this runner"


class DjangoAdapter(_RecordingRunner):
    adapter_id = "django"
    runner = "django"
    tool = "manage.py test"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if "django" in python_runners(root) else SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        s, u = SupportLevel.SUPPORTED, SupportLevel.UNSUPPORTED
        return (
            AdapterCapability("native_collection", s, "the project's TEST_RUNNER discovery (DiscoverRunner family)"),
            AdapterCapability("per_test_outcomes", s, "through the runner's result class; runners that do not use one give none"),
            AdapterCapability("parameterized_invocations", s, "subTest cases"),
            AdapterCapability("database", SupportLevel.UNKNOWN, "test databases need the configured backend; credentials are withheld unless passed through"),
            AdapterCapability("coverage", SupportLevel.UNKNOWN, "requires coverage.py in the target interpreter"),
            AdapterCapability("subset_selection", u, "a selected set runs the full suite"),
        )

    def default_args(self) -> list[str]:
        return []

    def _manage(self, root: Path, command: str | None = None) -> str:
        if command:
            try:
                tokens = shlex.split(command, posix=True)
            except ValueError:
                tokens = []
            found = next((t for t in tokens if t.endswith("manage.py")), None)
            if found:
                return found
        return "manage.py"

    def _args_from(self, command: str) -> list[str] | None:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return None
        index = next((i for i, t in enumerate(tokens) if t.endswith("manage.py")), None)
        if index is None or index + 1 >= len(tokens) or tokens[index + 1] != "test":
            return None
        return tokens[index + 2:]

    def _command(self, root: Path, args: list[str], plugin_dir: Path, coverage: bool) -> list[str]:
        commands = sorted(set(declared_runners(root).get("django", [])))
        manage = self._manage(root, commands[0] if len(commands) == 1 else None)
        test = [manage, "test", "--noinput", f"--testrunner={_MODULE}.DjangoRunner",
                *[a for a in args if not a.startswith("--testrunner")]]
        return [self.python, "-m", "coverage", "run", "--branch", *test] if coverage else [self.python, *test]

    def collect_limit(self) -> str:
        return ""
