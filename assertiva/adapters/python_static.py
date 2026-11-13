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


_IDENTITY_SOURCE = Path(__file__).with_name("_session_identity.py")
IDENTITY_MODULE = "assertiva_session_identity"


def copy_identity_module(directory: Path) -> None:
    """Place the in-process identity observer next to an evidence module (outside the project)."""
    (Path(directory) / f"{IDENTITY_MODULE}.py").write_text(_IDENTITY_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")


def session_facts(evidence, record: dict, expect_installed: bool = False) -> None:
    """Code identity (AX-E02), the temp root (AG-08) and borrowed site directories (AG-09) of a run, from the record
    ``assertiva_session_identity.session_record`` wrote inside its test process (pytest, unittest and Django alike).
    Without that record nothing is verified: the identity stays UNKNOWN."""
    identity = record.get("identity")
    expected = "INSTALLED_ARTIFACT" if expect_installed else "SOURCE_TREE"
    if not isinstance(identity, dict) or not isinstance(identity.get("loaded"), int):
        status, wrong, counts = "UNKNOWN", {}, {}  # nothing recorded: never read as verified
    else:
        # the modules on the unexpected side are the evidence: outside the copy for a source run, inside it for an
        # installed-artifact run. Counts cover every loaded module; only the listed names may be truncated.
        wrong_count = identity["inside"] if expect_installed else identity["outside"]
        wrong = identity["inside_listed"] if expect_installed else identity["outside_listed"]
        if expect_installed and isinstance(identity.get("in_artifact"), int):
            # modules from neither the copy nor the artifact's environment (another installation) are wrong too
            stray = identity["outside"] - identity["in_artifact"]
            wrong_count += stray
            if stray:
                wrong = {**wrong, **{f"<{stray} module(s) outside the artifact's environment>": ""}}
        counts = {k: identity.get(k) for k in ("loaded", "inside", "outside", "names_truncated")}
        counts["unexpected"] = wrong_count
        status = ("UNKNOWN" if not identity["loaded"] else "MISMATCH" if wrong_count else expected)
    evidence.metadata["source_identity"] = {
        "expected": expected, "status": status, "modules": dict(wrong), "from_outside_the_copy": sorted(wrong),
        "loaded": counts.get("loaded"), "inspected": counts.get("loaded"),
        "unexpected": counts.get("unexpected") if counts else None,
        "names_truncated": counts.get("names_truncated"),
        "in_artifact": identity.get("in_artifact") if isinstance(identity, dict) else None,
        "basis": "OBSERVED: every module of the project's packages the test process had imported when the session "
                 "finished; listed names are bounded, counts are complete",
    }
    outside = sorted(wrong)
    if status == "MISMATCH" and not expect_installed:
        evidence.limitations.append(
            "the tests imported the project's own modules from outside the tested copy (" + ", ".join(outside[:5])
            + "): an installed copy shadows the source tree, so this run does not prove the source under test")
    evidence.metadata["temp_root"] = {"path": record.get("tempdir"), "writable": record.get("tempdir_writable")}
    if record.get("tempdir_writable") is False:
        evidence.limitations.append(f"the test process's temporary directory ({record.get('tempdir')}) is not writable: "
                                    "tests that use temporary paths fail for the machine, not for the product")
    borrowed = record.get("borrowed_site_dirs") or []
    evidence.metadata["interpreter"] = {"python": record.get("python"), "prefix": record.get("prefix"),
                                        "borrowed_site_dirs": borrowed}
    if borrowed:
        evidence.limitations.append("the interpreter also loads packages from site directories outside its own "
                                    "environment (" + ", ".join(borrowed[:3]) + "): the run's dependencies are not "
                                    "only that environment's")


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

