"""Jest adapter: run the project's own Jest and normalize its official ``--json`` results.

The results format is Jest's ``formatTestResults`` output (``testResults[].assertionResults[]``).
Assertiva never installs dependencies or uses ``npx``: if Node or the project's Jest is missing,
the run is BLOCKED. Running Jest executes project code, so it is subject to the execution
budget and is always done in a disposable copy by the caller.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import CoverageSummary, Outcome, RunEvidence, TestInvocation
from assertiva.process import execution_refusal, run_command
from assertiva.verification import SupportLevel

from .base import AdapterCapability
from .coverage_reports import load_coverage_report

_OUTCOMES = {
    "passed": Outcome.PASSED, "failed": Outcome.FAILED, "pending": Outcome.SKIPPED, "skipped": Outcome.SKIPPED,
    "todo": Outcome.SKIPPED, "disabled": Outcome.SKIPPED, "focused": Outcome.NOT_RUN,
}
_CONFIGS = ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.cjs", "jest.config.json")
_COSMETIC = {"--ci", "--silent", "--verbose", "--colors", "--no-colors"}
FORMAT_LIMITS = [
    "table cases (test.each) are grouped into one declaration by source location only when Jest reports locations",
    "after retries Jest reports only the final outcome and the invocation count; the first attempt's failure is not kept",
    "no static oracle or negative-path analysis exists for JavaScript tests yet; those signals are UNKNOWN",
]


def _package(root: Path) -> dict:
    try:
        return json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _relative(name: str, root: str) -> str:
    if root == "<ROOT>":  # recorded fixtures
        return name.replace("<ROOT>", "").lstrip("\\/").replace("\\", "/")
    try:
        return Path(os.path.relpath(os.path.realpath(name), os.path.realpath(root))).as_posix()
    except ValueError:
        return Path(name).as_posix()


def parse_jest_results(data: dict | str, root: str | Path) -> RunEvidence:
    """Normalize Jest's ``--json`` results into run evidence (no execution)."""
    return parse_jest_format(data, root, "jest", FORMAT_LIMITS)


def parse_jest_format(data: dict | str, root: str | Path, adapter_id: str, limits: list[str]) -> RunEvidence:
    """Jest's results format (``testResults[].assertionResults[]``), which Vitest's JSON reporter also writes."""
    run = RunEvidence(adapter_id=adapter_id, mode="execute", status=StageStatus.UNKNOWN)
    try:
        if isinstance(data, str):
            data = json.loads(data)
        files = data["testResults"]
        if not isinstance(files, list):
            raise TypeError("testResults is not a list")
    except (ValueError, KeyError, TypeError) as exc:
        run.status = StageStatus.BLOCKED
        run.limitations.append(f"{adapter_id} results could not be read: {exc}"[:300])
        return run
    run.limitations += limits
    root = str(root)
    retried = []
    for result in files:
        rel = _relative(result.get("name", ""), root)
        assertions = result.get("assertionResults") or []
        if result.get("status") == "failed" and not assertions:
            run.collection_errors.append(rel)
            run.metadata.setdefault("error_sources", {})[rel] = rel
            continue
        locations: dict[tuple, int] = {}
        for item in assertions:
            location = item.get("location") or {}
            key = (location.get("line"), location.get("column")) if location else None
            if key:
                locations[key] = locations.get(key, 0) + 1
        for item in assertions:
            location = item.get("location") or {}
            key = (location.get("line"), location.get("column")) if location else None
            name = item.get("fullName") or " ".join([*item.get("ancestorTitles", []), item.get("title", "")]).strip()
            invocation_id = f"{rel} › {name}"
            declaration = f"{rel}:{key[0]}:{key[1]}" if key else invocation_id
            status = item.get("status", "")
            messages = [m for m in item.get("failureMessages") or [] if m]
            message = messages[0][:1000] if messages else ("todo: not implemented yet" if status == "todo" else None)
            invocations = item.get("invocations") or 1
            if invocations > 1:
                retried.append(invocation_id)
                message = f"{status} after {invocations} invocations (earlier attempts failed)" + (f": {message}" if message else "")
            elif status == "passed" and messages:  # Vitest: a pass after retries keeps the earlier failures
                retried.append(invocation_id)
                invocations = None
                message = "passed after earlier failed attempts (attempt count not reported): " + message
            duration = item.get("duration")
            run.invocations.append(
                TestInvocation(
                    invocation_id=invocation_id, declaration_id=declaration, materialization_id=invocation_id,
                    parameters_id=item.get("title") if key and locations.get(key, 0) > 1 else None,
                    outcome=_OUTCOMES.get(status, Outcome.NOT_RUN), duration_s=duration / 1000 if duration is not None else None,
                    message=message, source_paths=(rel,), attempts=invocations,
                )
            )
    if retried:
        run.limitations.append("retried tests passed only after earlier failed attempts: " + ", ".join(retried[:5]))
    outcomes = {inv.outcome for inv in run.invocations}
    if run.collection_errors or outcomes & {Outcome.FAILED, Outcome.ERROR}:
        run.status = StageStatus.FAIL
    elif not run.invocations or outcomes <= {Outcome.SKIPPED, Outcome.NOT_RUN}:
        run.status = StageStatus.UNKNOWN
        run.limitations.append("no test was executed; this is not evidence of a passing suite")
    else:
        run.status = StageStatus.PASS
    return run


def _coverage(summary_file: Path) -> CoverageSummary | None:
    summary = load_coverage_report(summary_file)
    return summary if summary.error is None else None


class JestAdapter:
    adapter_id = "jest"

    def __init__(self, python: str | None = None, timeout_s: float = 900.0):
        self.timeout_s = timeout_s  # `python` is accepted for the common factory signature only

    def supports(self, root: Path) -> SupportLevel:
        root = Path(root)
        package = _package(root)
        deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        if "jest" in deps or "jest" in package or any((root / name).is_file() for name in _CONFIGS):
            return SupportLevel.SUPPORTED
        return SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        return (
            AdapterCapability("structured_results", SupportLevel.SUPPORTED),
            AdapterCapability("table_case_identity", SupportLevel.SUPPORTED, "by source location"),
            AdapterCapability("coverage", SupportLevel.SUPPORTED, "istanbul json-summary"),
            AdapterCapability("static_oracle_analysis", SupportLevel.UNSUPPORTED),
        )

    def _node(self) -> str | None:
        configured = os.environ.get("ASSERTIVA_NODE")
        if configured:
            return configured if Path(configured).is_file() else None
        return shutil.which("node")

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        root = Path(root)
        refusal = execution_refusal()
        if refusal:
            return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[refusal])
        jest = root / "node_modules" / "jest" / "bin" / "jest.js"
        if not jest.is_file():
            return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[
                "the project's Jest is not installed (node_modules/jest); Assertiva does not install dependencies"])
        node = self._node()
        if not node:
            return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED,
                               limitations=["Node.js was not found (PATH or ASSERTIVA_NODE)"])
        with tempfile.TemporaryDirectory(prefix="assertiva-jest-") as tmp:
            out, cov = Path(tmp) / "results.json", Path(tmp) / "coverage"
            command = [node, str(jest), "--json", f"--outputFile={out}", "--ci", "--testLocationInResults", "--passWithNoTests", *(args or [])]
            if coverage:
                command += ["--coverage", "--coverageReporters=json-summary", f"--coverageDirectory={cov}"]
            result = run_command(command, root, timeout_s=self.timeout_s)
            if result.error or result.timed_out or not out.is_file():
                return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, command=command,
                                   limitations=[f"Jest produced no results: {result.summary()}"], wall_clock_s=result.duration_s)
            run = parse_jest_results(out.read_text(encoding="utf-8"), root)
            run.command, run.exit_code, run.wall_clock_s = command, result.returncode, result.duration_s
            if coverage:
                run.coverage = _coverage(cov / "coverage-summary.json")
                if run.coverage is None:
                    run.limitations.append("coverage was requested but Jest produced no json-summary")
        return run

    def installed_dependencies(self) -> tuple[str, ...]:
        return ("node_modules",)  # ignored by projects, so linked into copies rather than copied

    def declared_matrix(self, root) -> dict[str, dict]:
        """Lowest Node.js major the project declares (``engines.node``)."""
        import re

        spec = (_package(Path(root)).get("engines") or {}).get("node")
        match = re.search(r"(?:>=|\^|~)?\s*(\d+)", str(spec or ""))
        return {"node": {"values": [match.group(1)], "source": f"package.json engines.node {spec}"}} if spec and match else {}

    def static_signals(self, root) -> dict[str, int]:
        return {}

    def static_negative_paths(self, root) -> dict[str, list[str]]:
        return {}

    def reproduction_args(self, check) -> list[str] | None:
        """Jest arguments reproducing a delivery check (`jest ...` or `npm test` running jest)."""
        if check.tool == "jest" and check.command and "${{" not in check.command:
            return list(check.metadata.get("runner_args", []))
        return None

    def equivalent_to_default(self, args: list[str]) -> bool:
        return all(arg in _COSMETIC for arg in args)
