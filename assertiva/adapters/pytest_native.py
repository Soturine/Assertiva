"""Native pytest adapter: collection and execution evidence from pytest itself.

Runs the project's own pytest in a subprocess with a small recording plugin. Native
collection is authoritative for the runnable set; static AST inventory stays useful
for provenance but is a different, weaker kind of evidence.

Running native collection imports project code. Callers decide whether execution is
permitted and must run it inside a disposable copy, never in the original project.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.coverage import load_coverage_json
from assertiva.models import CoverageSummary, Outcome, RunEvidence, TestInvocation
from assertiva.verification import SupportLevel

from .base import AdapterCapability

_PLUGIN_MODULE = "assertiva_pytest_evidence"
_PLUGIN_SOURCE = Path(__file__).with_name("_pytest_evidence_plugin.py")
_CONFIG_MARKERS = ("pytest.ini", "conftest.py")
_REPORT_OPTIONS = {"--junitxml", "--junit-xml", "--html", "--cov-report", "--result-log", "--report-log"}
_SECTION_MARKERS = {"pyproject.toml": "[tool.pytest", "setup.cfg": "[tool:pytest]", "tox.ini": "[pytest]"}


def _declaration(item: dict) -> tuple[str, bool]:
    nodeid, qualname, declared_file = item["nodeid"], item.get("qualname"), item.get("declared_file")
    if not qualname or not declared_file:
        return nodeid, False
    declaration = f"{declared_file}::{qualname.replace('.', '::')}"
    owner = qualname.rsplit(".", 1)[0] if "." in qualname else None
    inherited = item.get("cls") is not None and owner != item["cls"]
    inherited = inherited or declared_file != nodeid.split("::", 1)[0]
    return declaration, inherited


def _outcome(reports: dict[str, dict]) -> Outcome:
    setup, call, teardown = reports.get("setup"), reports.get("call"), reports.get("teardown")
    if setup and setup["outcome"] == "failed":
        return Outcome.ERROR
    if setup and setup["outcome"] == "skipped":
        return Outcome.XFAILED if setup["wasxfail"] else Outcome.SKIPPED
    if not call:
        return Outcome.NOT_RUN
    if call["outcome"] == "failed":
        return Outcome.FAILED
    if call["outcome"] == "skipped":
        return Outcome.XFAILED if call["wasxfail"] else Outcome.SKIPPED
    if teardown and teardown["outcome"] == "failed":
        return Outcome.ERROR
    return Outcome.XPASSED if call["wasxfail"] else Outcome.PASSED


class PytestNativeAdapter:
    adapter_id = "pytest-native"

    def __init__(self, python: str | None = None, timeout_s: float = 900.0):
        self.python = python or sys.executable
        self.timeout_s = timeout_s

    def supports(self, root: Path) -> SupportLevel:
        from assertiva.pytest_audit import has_pytest_surface

        root = Path(root)
        if any((root / name).is_file() for name in _CONFIG_MARKERS) or has_pytest_surface(root):
            return SupportLevel.SUPPORTED
        for name, marker in _SECTION_MARKERS.items():
            path = root / name
            if path.is_file() and marker in path.read_text(encoding="utf-8", errors="replace"):
                return SupportLevel.SUPPORTED
        return SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        supported = SupportLevel.SUPPORTED
        return (
            AdapterCapability("native_collection", supported),
            AdapterCapability("stable_invocation_ids", supported),
            AdapterCapability("parameterized_invocations", supported),
            AdapterCapability("inherited_materialization", supported),
            AdapterCapability("skip_xfail_xpass", supported),
            AdapterCapability("marker_keyword_path_filters", supported),
            AdapterCapability("coverage", SupportLevel.UNKNOWN, "requires pytest-cov/coverage.py in the target environment"),
        )

    def static_audit(self, root: str | Path, coverage_json: str | Path | None = None):
        """Bounded static (AST) audit: never imports or runs project code."""
        from assertiva.pytest_audit import audit_pytest_project

        return audit_pytest_project(root, coverage_json)

    def static_signals(self, root: str | Path) -> dict[str, int]:
        """Static (E3) oracle / negative-path signals from the bounded AST analysis."""
        from assertiva.pytest_audit import audit_pytest_project

        tests = audit_pytest_project(root).tests
        return {
            "weak_oracle_tests": sum(test.smoke_like for test in tests),
            "broad_error_expectations": sum("BROAD_ERROR_EXPECTATION" in t.assertion_kinds for t in tests),
            "error_status_only_tests": sum("ERROR_STATUS_ONLY" in t.assertion_kinds for t in tests),
            "expected_error_contracts": sum("EXPECTED_ERROR_CONTRACT" in t.assertion_kinds for t in tests),
        }

    def reproduction_args(self, check) -> list[str] | None:
        """pytest arguments that reproduce a delivery check, or None if this adapter cannot."""
        if check.tool != "pytest" or not check.command or "${{" in check.command:
            return None
        if check.metadata.get("working_directory"):
            return None
        args, skip = [], False
        for token in check.metadata.get("runner_args", ()):
            if skip:
                skip = False
                continue
            if token in _REPORT_OPTIONS:
                skip = True
                continue
            if token.split("=", 1)[0] in _REPORT_OPTIONS:
                continue
            args.append(token)
        return args

    def collect(self, root: str | Path, args: list[str] | None = None) -> RunEvidence:
        return self._invoke(Path(root), ["--collect-only", *(args or [])], mode="collect")

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        return self._invoke(Path(root), list(args or []), mode="execute", coverage=coverage)

    def _has_module(self, module: str, env: dict) -> bool:
        try:
            return subprocess.run([self.python, "-c", f"import {module}"], env=env, capture_output=True, stdin=subprocess.DEVNULL, timeout=60).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _invoke(self, root: Path, args: list[str], mode: str, coverage: bool = False) -> RunEvidence:
        with tempfile.TemporaryDirectory(prefix="assertiva-pytest-") as tmp:
            plugin_dir = Path(tmp)
            (plugin_dir / f"{_PLUGIN_MODULE}.py").write_text(_PLUGIN_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
            evidence_file = plugin_dir / "evidence.jsonl"
            env = dict(os.environ)
            env.pop("PYTEST_CURRENT_TEST", None)
            env["ASSERTIVA_EVIDENCE_FILE"] = str(evidence_file)
            # Bytecode is read from and written to a prefix outside the tree: nothing lands in
            # the project, and a copied __pycache__ (which carries the original's file paths)
            # is never loaded. The prefix is stable so interpreter/site-packages bytecode is reused.
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            env["PYTHONPYCACHEPREFIX"] = str(Path(tempfile.gettempdir()) / "assertiva-pycache")
            env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(plugin_dir), env.get("PYTHONPATH")]))
            env["COVERAGE_FILE"] = str(plugin_dir / ".coverage")
            pytest_args = ["-p", _PLUGIN_MODULE, "-p", "no:cacheprovider", "-q", *args]
            measure_coverage = coverage and self._has_module("coverage", env)
            if measure_coverage:
                command = [self.python, "-m", "coverage", "run", "--branch", "-m", "pytest", *pytest_args]
            else:
                command = [self.python, "-m", "pytest", *pytest_args]
            evidence = RunEvidence(adapter_id=self.adapter_id, mode=mode, status=StageStatus.UNKNOWN, command=command)
            if coverage and not measure_coverage:
                evidence.limitations.append("coverage.py is not available in the target interpreter; coverage was not measured")
            started = time.monotonic()
            try:
                completed = subprocess.run(
                    command, cwd=root, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                    encoding="utf-8", errors="replace", timeout=self.timeout_s,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                evidence.status = StageStatus.BLOCKED
                evidence.limitations.append(f"pytest could not be executed: {exc}")
                return evidence
            evidence.wall_clock_s = round(time.monotonic() - started, 3)
            evidence.exit_code = completed.returncode
            records = [json.loads(line) for line in evidence_file.read_text(encoding="utf-8").splitlines()] if evidence_file.exists() else []
            if measure_coverage and records:
                evidence.coverage = self._coverage_json(root, env, plugin_dir)
                if evidence.coverage is None:
                    evidence.limitations.append("coverage.py ran but produced no reportable data")

        self._normalize(evidence, records)
        if not records and completed.returncode != 5:
            evidence.status = StageStatus.BLOCKED
            tail = (completed.stderr or completed.stdout).strip().splitlines()[-3:]
            evidence.limitations.append("pytest produced no native evidence: " + " | ".join(tail))
        return evidence

    def _coverage_json(self, root: Path, env: dict, out_dir: Path) -> CoverageSummary | None:
        report = out_dir / "coverage.json"
        try:
            subprocess.run(
                [self.python, "-m", "coverage", "json", "-q", "-o", str(report)],
                cwd=root, env=env, capture_output=True, stdin=subprocess.DEVNULL, timeout=self.timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if not report.exists():
            return None
        summary = load_coverage_json(report)
        return CoverageSummary(summary.line_percent, summary.branch_percent, "coverage.py json (project coverage configuration)")

    def _normalize(self, evidence: RunEvidence, records: list[dict]) -> None:
        reports: dict[str, dict[str, dict]] = {}
        for record in records:
            if record["type"] == "collect_error":
                evidence.collection_errors.append(record["nodeid"] or "<session>")
            elif record["type"] == "deselected":
                evidence.deselected.append(record["nodeid"])
            elif record["type"] == "report":
                reports.setdefault(record["nodeid"], {})[record["when"]] = record

        for record in (r for r in records if r["type"] == "item"):
            declaration, inherited = _declaration(record)
            nodeid, params = record["nodeid"], record.get("params_id")
            materialization = nodeid[: -len(params) - 2] if params and nodeid.endswith(f"[{params}]") else nodeid
            item_reports = reports.get(nodeid, {})
            outcome = _outcome(item_reports) if evidence.mode == "execute" else None
            message = next((r["message"] for r in item_reports.values() if r.get("message")), None)
            evidence.invocations.append(
                TestInvocation(
                    invocation_id=nodeid,
                    declaration_id=declaration,
                    materialization_id=materialization,
                    parameters_id=params,
                    markers=tuple(record.get("markers") or ()),
                    outcome=outcome,
                    duration_s=round(sum(r["duration"] for r in item_reports.values()), 6) if item_reports else None,
                    inherited=inherited,
                    custom=record.get("qualname") is None,
                    message=message,
                    source_paths=tuple(dict.fromkeys(filter(None, [nodeid.split("::", 1)[0], record.get("declared_file")]))),
                )
            )

        if any(inv.custom for inv in evidence.invocations):
            evidence.limitations.append(
                "custom collected items: declaration provenance and oracle analysis are unavailable for them"
            )
        if any("<locals>" in inv.declaration_id for inv in evidence.invocations):
            evidence.limitations.append("dynamically generated tests: declaration is a runtime factory, not a source definition")

        bad = {Outcome.FAILED, Outcome.ERROR}
        if evidence.collection_errors or any(inv.outcome in bad for inv in evidence.invocations):
            evidence.status = StageStatus.FAIL
        elif evidence.exit_code == 5 or not evidence.invocations:
            evidence.status = StageStatus.UNKNOWN
            evidence.limitations.append("no tests were collected; this is not evidence of a passing suite")
        elif evidence.exit_code == 0:
            evidence.status = StageStatus.PASS
        elif evidence.exit_code == 1:
            evidence.status = StageStatus.FAIL
        else:
            evidence.status = StageStatus.BLOCKED
            evidence.limitations.append(f"pytest exited with code {evidence.exit_code}")
