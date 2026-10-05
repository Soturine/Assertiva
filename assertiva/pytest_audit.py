from __future__ import annotations

import ast
from pathlib import Path

from .ci import discover_github_actions_pytest, path_selected_by_ci
from .coverage import load_coverage_json
from .models import Finding, PytestAssuranceReport, TestCompositionRelation, TestDefinition

_WEAK = {
    "NO_ASSERTION",
    "EXISTENCE_ONLY",
    "HTTP_STATUS_ONLY",
    "ERROR_STATUS_ONLY",
    "BROAD_ERROR_EXPECTATION",
}


def _expr_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expr_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _is_broad_exception(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"Exception", "BaseException"}
    if isinstance(node, ast.Attribute):
        return node.attr in {"Exception", "BaseException"}
    if isinstance(node, ast.Tuple):
        return any(_is_broad_exception(item) for item in node.elts)
    return False


def _expected_failure_kind(call: ast.Call) -> str | None:
    name = (_expr_name(call.func) or "").split(".")[-1]
    if name in {"raises", "assertRaises", "assertRaisesRegex"}:
        if not call.args or _is_broad_exception(call.args[0]):
            return "BROAD_ERROR_EXPECTATION"
        return "EXPECTED_ERROR_CONTRACT"
    if name in {"assertWarns", "assertWarnsRegex"}:
        return "EXPECTED_WARNING"
    return None


def _assertion_kind(node: ast.Assert) -> str:
    test = node.test
    if isinstance(test, ast.Compare):
        if isinstance(test.left, ast.Attribute) and test.left.attr == "status_code":
            statuses = [
                comparator.value
                for comparator in test.comparators
                if isinstance(comparator, ast.Constant)
                and isinstance(comparator.value, int)
            ]
            if any(200 <= status <= 299 for status in statuses):
                return "HTTP_STATUS_ONLY"
            if any(status >= 400 for status in statuses):
                return "ERROR_STATUS_ONLY"
        if any(isinstance(op, (ast.Is, ast.IsNot)) for op in test.ops) and any(
            isinstance(comparator, ast.Constant) and comparator.value is None
            for comparator in test.comparators
        ):
            return "EXISTENCE_ONLY"
    return "BEHAVIORAL_ASSERTION"


def _function_assertions(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    kinds = [_assertion_kind(item) for item in ast.walk(node) if isinstance(item, ast.Assert)]
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            kind = _expected_failure_kind(item)
            if kind:
                kinds.append(kind)
    normalized = tuple(dict.fromkeys(kinds))
    return normalized or ("NO_ASSERTION",)


def _test_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in ("test_*.py", "*_test.py"):
        files.update(root.rglob(pattern))
    return sorted(
        path
        for path in files
        if not any(part.startswith(".") for part in path.relative_to(root).parts)
    )


def has_pytest_surface(root: str | Path) -> bool:
    return bool(_test_files(Path(root)))


def _direct_test_methods(node: ast.ClassDef) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        item.name: item
        for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name.startswith("test_")
    }


def _base_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in node.bases:
        name = _expr_name(base)
        if name:
            names.append(name.split(".")[-1])
    return names


def _ancestor_test_methods(
    class_name: str,
    class_map: dict[str, ast.ClassDef],
    seen: tuple[str, ...] = (),
) -> dict[str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    if class_name in seen:
        return {}
    current = class_map.get(class_name)
    if current is None:
        return {}

    methods: dict[str, tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for base_name in _base_names(current):
        base = class_map.get(base_name)
        if base is None:
            continue
        for method_name, method in _direct_test_methods(base).items():
            methods.setdefault(method_name, (base_name, method))
        inherited = _ancestor_test_methods(base_name, class_map, seen + (class_name,))
        for method_name, declaration in inherited.items():
            methods.setdefault(method_name, declaration)
    return methods


def discover_pytest_composition(root: str | Path) -> list[TestCompositionRelation]:
    """Discover bounded same-file inheritance/materialization candidates.

    Native runner collection remains authoritative. Cross-module bases, dynamic class
    construction, metaclasses, plugins and complex runtime MRO behavior are outside
    this static slice.
    """
    root = Path(root)
    relations: list[TestCompositionRelation] = []
    for path in _test_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue

        rel = str(path.relative_to(root)).replace("\\", "/")
        class_map = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        for class_name, class_node in class_map.items():
            if not class_name.startswith("Test"):
                continue
            overridden = set(_direct_test_methods(class_node))
            inherited = _ancestor_test_methods(class_name, class_map)
            for method_name, (declaration_class, declaration_node) in inherited.items():
                if method_name in overridden:
                    continue
                relations.append(
                    TestCompositionRelation(
                        declaration_id=f"{rel}::{declaration_class}::{method_name}",
                        materialization_id=f"{rel}::{class_name}::{method_name}",
                        relation="MATERIALIZES_IN",
                        source_path=rel,
                        declaration_class=declaration_class,
                        materialization_class=class_name,
                        assertion_kinds=_function_assertions(declaration_node),
                        limitations=(
                            "bounded same-file static inheritance analysis",
                            "native runner collection is authoritative",
                        ),
                    )
                )
    return relations


def discover_pytest_definitions(root: str | Path) -> list[TestDefinition]:
    root = Path(root)
    out: list[TestDefinition] = []
    for path in _test_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                kinds = _function_assertions(node)
                out.append(
                    TestDefinition(
                        f"{rel}::{node.name}",
                        rel,
                        node.name,
                        kinds,
                        all(kind in _WEAK for kind in kinds),
                    )
                )
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        kinds = _function_assertions(child)
                        out.append(
                            TestDefinition(
                                f"{rel}::{node.name}::{child.name}",
                                rel,
                                child.name,
                                kinds,
                                all(kind in _WEAK for kind in kinds),
                            )
                        )
    return out


def audit_pytest_project(root: str | Path, coverage_json: str | Path | None = None) -> PytestAssuranceReport:
    root = Path(root)
    tests = discover_pytest_definitions(root)
    materializations = discover_pytest_composition(root)
    ci = discover_github_actions_pytest(root)
    coverage = load_coverage_json(coverage_json) if coverage_json else None
    findings: list[Finding] = []

    if not tests and not materializations:
        findings.append(
            Finding("NO_TESTS_DISCOVERED", "No pytest-style definitions were found by bounded static inventory.")
        )
    if (tests or materializations) and not ci:
        findings.append(
            Finding(
                "CI_PYTEST_NOT_OBSERVED",
                "Pytest-style test evidence exists, but no pytest invocation was observed in GitHub Actions.",
                {"direct_test_count": len(tests), "static_materialization_count": len(materializations)},
            )
        )
    if tests and ci:
        missing = sorted({test.path for test in tests if not path_selected_by_ci(test.path, ci)})
        if missing:
            findings.append(
                Finding(
                    "CI_TEST_EXECUTION_GAP",
                    "Some discovered pytest files are outside observed GitHub Actions pytest scopes.",
                    {"unobserved_test_files": missing},
                )
            )

    weak = [test.node_id for test in tests if test.smoke_like]
    if len(tests) >= 4 and len(weak) / len(tests) >= 0.75:
        findings.append(
            Finding(
                "SUITE_SMOKE_DOMINANT",
                "The observed direct pytest definitions are dominated by weak static oracle signals.",
                {"smoke_like": len(weak), "total": len(tests), "examples": weak[:10]},
            )
        )
    if weak:
        findings.append(
            Finding(
                "WEAK_ORACLE_SIGNAL",
                "Some direct test definitions expose weak deterministic oracle signals.",
                {"count": len(weak), "tests": weak[:20]},
            )
        )

    broad = [test.node_id for test in tests if "BROAD_ERROR_EXPECTATION" in test.assertion_kinds]
    if broad:
        findings.append(
            Finding(
                "BROAD_ERROR_EXPECTATION_SIGNAL",
                "Some tests require only a very broad exception category.",
                {"count": len(broad), "tests": broad[:20]},
            )
        )

    error_status_only = [test.node_id for test in tests if "ERROR_STATUS_ONLY" in test.assertion_kinds]
    if error_status_only:
        findings.append(
            Finding(
                "ERROR_STATUS_ONLY_SIGNAL",
                "Some negative-path tests assert only an error status; structured error details and state effects may remain unverified.",
                {"count": len(error_status_only), "tests": error_status_only[:20]},
            )
        )

    if coverage and coverage.line_percent is not None and coverage.branch_percent is not None:
        if coverage.line_percent >= 90 and coverage.line_percent - coverage.branch_percent >= 20:
            findings.append(
                Finding(
                    "LINE_BRANCH_COVERAGE_DIVERGENCE",
                    "High line coverage materially exceeds branch coverage.",
                    {"line_percent": coverage.line_percent, "branch_percent": coverage.branch_percent},
                )
            )
    if coverage and coverage.line_percent is not None and coverage.line_percent >= 90 and weak:
        findings.append(
            Finding(
                "HIGH_COVERAGE_WEAK_ORACLE",
                "High line coverage coexists with weak oracle signals; coverage alone is insufficient evidence.",
                {"line_percent": coverage.line_percent, "weak_oracle_tests": len(weak)},
            )
        )

    return PytestAssuranceReport(
        root=root,
        tests=tests,
        ci_invocations=ci,
        findings=findings,
        coverage=coverage,
        materializations=materializations,
    )
