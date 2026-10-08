"""Static Python test evidence shared by the Python runner adapters (pytest, unittest, Django).

Bounded AST analysis: never imports or runs project code. Every Python adapter offers it, but it describes the
project's Python tests, not a runner: callers use it once per project (``static_family``).
"""

from __future__ import annotations

from pathlib import Path


def measured_coverage(python: str, root: Path, env: dict, out_dir: Path, timeout_s: float):
    """coverage.py's JSON for a run just measured with `coverage run` (shared by the Python runners)."""
    from dataclasses import replace

    from assertiva.process import run_command

    from .coverage_reports import load_coverage_report

    report = out_dir / "coverage.json"
    run_command([python, "-m", "coverage", "json", "-q", "-o", str(report)], root, env=env, timeout_s=timeout_s)
    if not report.exists():
        return None
    summary = load_coverage_report(report)
    return replace(summary, scope="project coverage configuration") if summary.error is None else None


class PythonStatic:
    static_family = "python"

    def static_audit(self, root: str | Path, coverage_json: str | Path | None = None):
        """Bounded static (AST) audit: never imports or runs project code."""
        from assertiva.pytest_audit import audit_pytest_project

        return audit_pytest_project(root, coverage_json)

    def declared_matrix(self, root: str | Path) -> dict[str, dict]:
        """Lowest Python version the project declares it supports (``requires-python``)."""
        import re
        import tomllib

        try:
            spec = tomllib.loads((Path(root) / "pyproject.toml").read_text(encoding="utf-8")).get("project", {}).get("requires-python")
        except (OSError, ValueError):
            return {}
        match = re.search(r">=\s*(\d+\.\d+)", spec or "")
        return {"python": {"values": [match.group(1)], "source": f"pyproject.toml requires-python {spec}"}} if match else {}

    def review_candidates(self, root: str | Path) -> list[dict]:
        from assertiva.pytest_audit import review_candidates

        return review_candidates(root)

    def static_signals(self, root: str | Path) -> dict[str, int]:
        """Static (E3) oracle / negative-path signals from the bounded AST analysis."""
        from assertiva.pytest_audit import audit_pytest_project

        from assertiva.pytest_audit import is_negative_path, lacks_contract_detail

        tests = audit_pytest_project(root).tests
        return {
            "weak_oracle_tests": sum(test.smoke_like for test in tests),
            "broad_error_expectations": sum("BROAD_ERROR_EXPECTATION" in t.assertion_kinds for t in tests),
            "error_status_only_tests": sum(t.negative_dims == ("PROTOCOL_STATUS",) for t in tests),
            "expected_error_contracts": sum("EXPECTED_ERROR_CONTRACT" in t.assertion_kinds for t in tests),
            "negative_path_tests": sum(is_negative_path(t) for t in tests),
            "negative_paths_without_contract_detail": sum(lacks_contract_detail(t) for t in tests),
            "negative_paths_with_state_after_rejection": sum("STATE_AFTER_REJECTION" in t.negative_dims for t in tests),
        }

    def static_negative_paths(self, root: str | Path) -> dict[str, list[str]]:
        """Negative-path test id -> observable failure-contract dimensions (static, E3)."""
        from assertiva.pytest_audit import audit_pytest_project, is_negative_path

        return {t.node_id: list(t.negative_dims) for t in audit_pytest_project(root).tests if is_negative_path(t)}

