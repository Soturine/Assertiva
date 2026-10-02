from __future__ import annotations

import ast
from pathlib import Path

from .ci import discover_github_actions_pytest, path_selected_by_ci
from .coverage import load_coverage_json
from .models import Finding, PytestAssuranceReport, TestDefinition

_WEAK = {"NO_ASSERTION", "EXISTENCE_ONLY", "HTTP_STATUS_ONLY"}


def _assertion_kind(node: ast.Assert) -> str:
    test = node.test
    if isinstance(test, ast.Compare):
        if isinstance(test.left, ast.Attribute) and test.left.attr == "status_code":
            if any(isinstance(c, ast.Constant) and c.value in {200,201,202,204} for c in test.comparators):
                return "HTTP_STATUS_ONLY"
        if any(isinstance(op, (ast.Is, ast.IsNot)) for op in test.ops):
            if any(isinstance(c, ast.Constant) and c.value is None for c in test.comparators):
                return "EXISTENCE_ONLY"
    return "BEHAVIORAL_ASSERTION"


def _function_assertions(node):
    kinds = tuple(_assertion_kind(x) for x in ast.walk(node) if isinstance(x, ast.Assert))
    return kinds or ("NO_ASSERTION",)


def _test_files(root: Path):
    files = set()
    for pattern in ("test_*.py", "*_test.py"):
        files.update(root.rglob(pattern))
    return sorted(p for p in files if not any(part.startswith(".") for part in p.relative_to(root).parts))


def discover_pytest_definitions(root: str | Path) -> list[TestDefinition]:
    root = Path(root)
    out = []
    for path in _test_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(root)).replace("\\","/")
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                kinds = _function_assertions(node)
                out.append(TestDefinition(f"{rel}::{node.name}", rel, node.name, kinds, all(k in _WEAK for k in kinds)))
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        kinds = _function_assertions(child)
                        out.append(TestDefinition(f"{rel}::{node.name}::{child.name}", rel, child.name, kinds, all(k in _WEAK for k in kinds)))
    return out


def audit_pytest_project(root: str | Path, coverage_json: str | Path | None = None) -> PytestAssuranceReport:
    root = Path(root)
    tests = discover_pytest_definitions(root)
    ci = discover_github_actions_pytest(root)
    coverage = load_coverage_json(coverage_json) if coverage_json else None
    findings = []

    if not tests:
        findings.append(Finding("NO_TESTS_DISCOVERED", "No pytest-style definitions were found by bounded static inventory."))
    if tests and not ci:
        findings.append(Finding("CI_PYTEST_NOT_OBSERVED", "Pytest-style tests exist, but no pytest invocation was observed in GitHub Actions.", {"test_count": len(tests)}))
    if tests and ci:
        missing = sorted({t.path for t in tests if not path_selected_by_ci(t.path, ci)})
        if missing:
            findings.append(Finding("CI_TEST_EXECUTION_GAP", "Some discovered pytest files are outside observed GitHub Actions pytest scopes.", {"unobserved_test_files": missing}))

    weak = [t.node_id for t in tests if t.smoke_like]
    if len(tests) >= 4 and len(weak) / len(tests) >= .75:
        findings.append(Finding("SUITE_SMOKE_DOMINANT", "The suite is dominated by no-assertion, existence-only, or success-status-only checks.", {"smoke_like": len(weak), "total": len(tests), "examples": weak[:10]}))
    if weak:
        findings.append(Finding("WEAK_ORACLE_SIGNAL", "Some tests expose weak deterministic oracle signals; review them before making a broad regression claim.", {"count": len(weak), "tests": weak[:20]}))

    if coverage and coverage.line_percent is not None and coverage.branch_percent is not None:
        if coverage.line_percent >= 90 and coverage.line_percent - coverage.branch_percent >= 20:
            findings.append(Finding("LINE_BRANCH_COVERAGE_DIVERGENCE", "High line coverage materially exceeds branch coverage.", {"line_percent": coverage.line_percent, "branch_percent": coverage.branch_percent}))
    if coverage and coverage.line_percent is not None and coverage.line_percent >= 90 and weak:
        findings.append(Finding("HIGH_COVERAGE_WEAK_ORACLE", "High line coverage coexists with weak oracle signals; coverage alone is insufficient evidence.", {"line_percent": coverage.line_percent, "weak_oracle_tests": len(weak)}))

    return PytestAssuranceReport(root, tests, ci, findings, coverage)
