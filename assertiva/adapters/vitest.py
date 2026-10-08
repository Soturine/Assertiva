"""Vitest adapter: run the project's own Vitest (3+) and read its JSON reporter, which writes Jest's results format.

Assertiva never installs dependencies or uses ``npx``: a missing Node or Vitest is BLOCKED. The project's installed
`node_modules` is linked into the disposable copy, so the run must not write through it: caches are disabled and
the configuration is loaded with Vite's module runner (`--configLoader=runner`, Vite 6.1+, i.e. Vitest 3+) instead
of being bundled into `node_modules/.vite-temp`. Coverage uses the project's own provider when it is installed.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import RunEvidence
from assertiva.process import execution_refusal, run_command
from assertiva.verification import SupportLevel

from .base import AdapterCapability
from .coverage_reports import load_coverage_report
from .jest import _package, node_executable, parse_jest_format

_CONFIGS = tuple(f"{stem}.{ext}" for stem in ("vitest.config", "vitest.workspace", "vitest.projects")
                 for ext in ("ts", "mts", "cts", "js", "mjs", "cjs", "json"))
_COSMETIC = {"run", "--run", "--silent", "--no-color", "--color", "--passWithNoTests", "--hideSkippedTests"}
_PROVIDERS = {"@vitest/coverage-v8": "v8", "@vitest/coverage-istanbul": "istanbul"}
FORMAT_LIMITS = [
    "Vitest's JSON report does not name the project a test ran in; a file included by several projects appears once per project",
    "after retries Vitest reports the final status; a pass after failed attempts is recognized by the failure messages it keeps, the attempt count is unknown",
    "no static oracle or negative-path analysis exists for JavaScript tests yet; those signals are UNKNOWN",
]


def _version(root: Path) -> str | None:
    try:
        return json.loads((root / "node_modules" / "vitest" / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError):
        return None


class VitestAdapter:
    adapter_id = "vitest"

    def __init__(self, python: str | None = None, timeout_s: float = 900.0):
        self.timeout_s = timeout_s  # `python` is accepted for the common factory signature only

    def supports(self, root: Path) -> SupportLevel:
        root = Path(root)
        package = _package(root)
        deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        if "vitest" in deps or any((root / name).is_file() for name in _CONFIGS):
            return SupportLevel.SUPPORTED
        return SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        s, u = SupportLevel.SUPPORTED, SupportLevel.UNSUPPORTED
        return (
            AdapterCapability("structured_results", s, "JSON reporter (Jest results format)"),
            AdapterCapability("table_case_identity", s, "by source location (--includeTaskLocation)"),
            AdapterCapability("coverage", SupportLevel.UNKNOWN, "the project's installed @vitest/coverage-v8 or -istanbul, json-summary"),
            AdapterCapability("project_identity", u, "the JSON report does not name the project"),
            AdapterCapability("static_oracle_analysis", u),
        )

    def _blocked(self, reason: str, **fields) -> RunEvidence:
        return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[reason], **fields)

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        root = Path(root)
        refusal = execution_refusal()
        if refusal:
            return self._blocked(refusal)
        cli = root / "node_modules" / "vitest" / "vitest.mjs"
        version = _version(root)
        if not cli.is_file() or version is None:
            return self._blocked("the project's Vitest is not installed (node_modules/vitest); Assertiva does not install dependencies")
        major = int(version.split(".")[0]) if version.split(".")[0].isdigit() else 0
        if major < 3:
            return self._blocked(f"Vitest {version}: the adapter needs Vitest 3+ to load the configuration without writing into the project")
        node = node_executable()
        if not node:
            return self._blocked("Node.js was not found (PATH or ASSERTIVA_NODE)")
        provider = next((name for package, name in _PROVIDERS.items() if (root / "node_modules" / package).is_dir()), None)
        args = [a for a in (args or []) if a not in ("run", "watch")]
        with tempfile.TemporaryDirectory(prefix="assertiva-vitest-") as tmp:
            out, cov = Path(tmp) / "results.json", Path(tmp) / "coverage"
            command = [node, str(cli), "run", "--reporter=json", f"--outputFile={out}", "--includeTaskLocation", "--no-cache",
                       "--configLoader=runner", "--passWithNoTests", *args]
            if coverage and provider:
                command += ["--coverage.enabled", f"--coverage.provider={provider}", "--coverage.reporter=json-summary",
                            f"--coverage.reportsDirectory={cov}"]
            result = run_command(command, root, timeout_s=self.timeout_s)
            if result.error or result.timed_out or not out.is_file():
                return self._blocked(f"Vitest produced no results: {result.summary()}", command=command, wall_clock_s=result.duration_s)
            run = parse_jest_format(out.read_text(encoding="utf-8"), root, self.adapter_id, FORMAT_LIMITS)
            run.command, run.exit_code, run.wall_clock_s = command, result.returncode, result.duration_s
            run.metadata["vitest"] = version
            if coverage and provider:
                summary = load_coverage_report(cov / "coverage-summary.json")
                run.coverage = summary if summary.error is None else None
                if run.coverage is None:
                    run.limitations.append("coverage was requested but Vitest produced no json-summary")
            elif coverage:
                run.limitations.append("no Vitest coverage provider is installed (@vitest/coverage-v8 or -istanbul); coverage was not measured")
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
        """Vitest arguments reproducing a declared check (`vitest ...`, or a script that runs it)."""
        if check.tool == "vitest" and check.command and "${{" not in check.command:
            return [a for a in check.metadata.get("runner_args", []) if a not in ("run", "watch")]
        return None

    def equivalent_to_default(self, args: list[str]) -> bool:
        return all(arg in _COSMETIC or arg.startswith("--reporter") for arg in args)
