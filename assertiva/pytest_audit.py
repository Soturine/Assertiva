from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from .ci import CiPytestInvocation, discover_github_actions_pytest, path_selected_by_ci
from .adapters.coverage_reports import load_coverage_report
from .models import CoverageSummary, Finding, TestCompositionRelation, TestDefinition


@dataclass
class PytestAssuranceReport:
    root: Path
    tests: list[TestDefinition]
    ci_invocations: list[CiPytestInvocation]
    findings: list[Finding]
    coverage: CoverageSummary | None = None
    materializations: list[TestCompositionRelation] = field(default_factory=list)

    @property
    def smoke_like_count(self) -> int:
        return sum(test.smoke_like for test in self.tests)

    @property
    def smoke_ratio(self) -> float:
        return self.smoke_like_count / len(self.tests) if self.tests else 0.0

    @property
    def expected_error_count(self) -> int:
        return sum("EXPECTED_ERROR_CONTRACT" in test.assertion_kinds for test in self.tests)

    def has_finding(self, code: str) -> bool:
        return any(f.code == code for f in self.findings)


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


# --- negative-path dimensions (E3: deterministic AST signals, not runtime proof) ---------

NEGATIVE_DIMENSIONS = (
    "ERROR_TYPE", "MESSAGE", "MACHINE_CODE", "FIELD_OR_PATH", "STRUCTURED_CONTEXT",
    "PROTOCOL_STATUS", "STATE_AFTER_REJECTION", "ASYNC_OBSERVED",
)
_CODE = {"code", "error_code", "err_code", "errcode", "errno", "error_type", "reason_code"}
_FIELD = {"field", "fields", "path", "loc", "location", "pointer", "param", "parameter", "field_name", "attribute"}
_CONTEXT = {"errors", "details", "detail", "context", "extra", "violations"}
_MESSAGE = {"message", "msg", "args"}
_RAISES = {"raises", "assertRaises", "assertRaisesRegex"}


def _names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute):
            names.add(item.attr)
        elif isinstance(item, ast.Subscript) and isinstance(item.slice, ast.Constant) and isinstance(item.slice.value, str):
            names.add(item.slice.value)
    return names


def _refers_to(node: ast.AST, var: str | None) -> bool:
    return var is not None and any(isinstance(n, ast.Name) and n.id == var for n in ast.walk(node))


def _detail_dims(assert_node: ast.Assert, var: str | None = None) -> set[str]:
    names, found = _names(assert_node), set()
    if names & _CODE:
        found.add("MACHINE_CODE")
    if names & _FIELD:
        found.add("FIELD_OR_PATH")
    if names & _CONTEXT:
        found.add("STRUCTURED_CONTEXT")
    stringified = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "str" and any(_refers_to(a, var) for a in n.args)
        for n in ast.walk(assert_node)
    )
    if names & _MESSAGE or stringified:
        found.add("MESSAGE")
    return found


def _raises_call(expr: ast.AST) -> ast.Call | None:
    if isinstance(expr, ast.Call) and (_expr_name(expr.func) or "").split(".")[-1] in _RAISES:
        return expr
    return None


def negative_path_evidence(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    """(dimensions, specific expected error types, async failure created but never observed)."""
    dims: set[str] = set()
    error_types: list[str] = []
    is_async = isinstance(node, ast.AsyncFunctionDef)
    blocks = []  # (with node, excinfo var)
    for item in ast.walk(node):
        if isinstance(item, (ast.With, ast.AsyncWith)):
            for with_item in item.items:
                call = _raises_call(with_item.context_expr)
                if call is None:
                    continue
                var = with_item.optional_vars.id if isinstance(with_item.optional_vars, ast.Name) else None
                blocks.append((item, var))
                if is_async and any(isinstance(n, ast.Await) for stmt in item.body for n in ast.walk(stmt)):
                    dims.add("ASYNC_OBSERVED")
        if isinstance(item, ast.Call) and _raises_call(item):
            if item.args and not _is_broad_exception(item.args[0]):
                dims.add("ERROR_TYPE")
                error_types.append((_expr_name(item.args[0]) or "?").split(".")[-1])
            if any(k.arg == "match" for k in item.keywords) or (_expr_name(item.func) or "").endswith("Regex"):
                dims.add("MESSAGE")

    asserts = [n for n in ast.walk(node) if isinstance(n, ast.Assert)]
    status_negative = any(_assertion_kind(a) == "ERROR_STATUS_ONLY" for a in asserts)
    if status_negative:
        dims.add("PROTOCOL_STATUS")
        for a in asserts:
            dims |= _detail_dims(a)
    for with_node, var in blocks:
        end = getattr(with_node, "end_lineno", with_node.lineno)
        for a in asserts:
            if _refers_to(a, var):
                dims |= _detail_dims(a, var)
            elif a.lineno > end:
                dims.add("STATE_AFTER_REJECTION")

    unobserved = False
    if is_async:
        awaited = {n.id for aw in ast.walk(node) if isinstance(aw, ast.Await) for n in ast.walk(aw) if isinstance(n, ast.Name)}
        for item in ast.walk(node):
            value = item.value if isinstance(item, (ast.Assign, ast.Expr)) else None
            if isinstance(value, ast.Call) and (_expr_name(value.func) or "").split(".")[-1] in {"create_task", "ensure_future"}:
                targets = [t.id for t in getattr(item, "targets", []) if isinstance(t, ast.Name)]
                if not targets or not set(targets) & awaited:
                    unobserved = True
    if not blocks and not status_negative and not any(_raises_call(n) for n in ast.walk(node)):
        dims = set()  # not a negative-path test: detail names alone prove nothing about failures
    ordered = tuple(d for d in NEGATIVE_DIMENSIONS if d in dims)
    return ordered, tuple(dict.fromkeys(error_types)), unobserved


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


def _definition(node_id: str, rel: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> TestDefinition:
    kinds = _function_assertions(node)
    dims, error_types, unobserved = negative_path_evidence(node)
    return TestDefinition(node_id, rel, node.name, kinds, all(kind in _WEAK for kind in kinds), dims, error_types, unobserved)


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
                out.append(_definition(f"{rel}::{node.name}", rel, node))
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                        out.append(_definition(f"{rel}::{node.name}::{child.name}", rel, child))
    return out


WEAK_NEGATIVE = frozenset({"ERROR_TYPE", "PROTOCOL_STATUS"})
DETAIL = frozenset({"MACHINE_CODE", "FIELD_OR_PATH", "STRUCTURED_CONTEXT"})


def is_negative_path(test: TestDefinition) -> bool:
    return bool(test.negative_dims) or "BROAD_ERROR_EXPECTATION" in test.assertion_kinds


def lacks_contract_detail(test: TestDefinition) -> bool:
    """Negative-path test that only shows *that* something failed (type/status) or accepts any error."""
    return is_negative_path(test) and set(test.negative_dims) <= WEAK_NEGATIVE


def _negative_path_findings(tests: list[TestDefinition]) -> list[Finding]:
    findings = []
    detailed_types = {t for test in tests if DETAIL & set(test.negative_dims) for t in test.error_types}
    type_only = [
        test for test in tests
        if test.error_types and not DETAIL & set(test.negative_dims) and set(test.error_types) & detailed_types
    ]
    if type_only:
        findings.append(Finding(
            "ERROR_CONTRACT_FIELD_NOT_OBSERVED",
            "Other tests show these errors carry a machine code/field/context, but these tests only check the type.",
            {"tests": [t.node_id for t in type_only][:20], "error_types": sorted({e for t in type_only for e in t.error_types} & detailed_types)},
        ))
    raising = [t for t in tests if "ERROR_TYPE" in t.negative_dims]
    if any("STATE_AFTER_REJECTION" in t.negative_dims for t in raising):
        missing = [t.node_id for t in raising if "STATE_AFTER_REJECTION" not in t.negative_dims]
        if missing:
            findings.append(Finding(
                "STATE_AFTER_REJECTION_NOT_EVIDENCED",
                "Some tests check state after a rejection; these do not, so partial writes would go unnoticed (static E3 signal).",
                {"tests": missing[:20]},
            ))
    unobserved = [t.node_id for t in tests if t.async_unobserved]
    if unobserved:
        findings.append(Finding(
            "ASYNC_FAILURE_NOT_OBSERVED",
            "An async task is created but never awaited, so its failure cannot fail the test.",
            {"tests": unobserved[:20]},
        ))
    return findings


def audit_pytest_project(root: str | Path, coverage_json: str | Path | None = None) -> PytestAssuranceReport:
    root = Path(root)
    tests = discover_pytest_definitions(root)
    materializations = discover_pytest_composition(root)
    ci = discover_github_actions_pytest(root)
    coverage = load_coverage_report(coverage_json) if coverage_json else None
    if coverage is not None and coverage.error:
        coverage = None
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
                severity="medium",
                recommendation="Add the test suite to the delivery pipeline or record where it is enforced.",
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

    error_status_only = [test.node_id for test in tests if test.negative_dims == ("PROTOCOL_STATUS",)]
    if error_status_only:
        findings.append(
            Finding(
                "ERROR_STATUS_ONLY_SIGNAL",
                "Some negative-path tests assert only an error status; structured error details and state effects may remain unverified.",
                {"count": len(error_status_only), "tests": error_status_only[:20]},
            )
        )

    findings.extend(_negative_path_findings(tests))

    if coverage and coverage.percent('line') is not None and coverage.percent('branch') is not None:
        if coverage.percent('line') >= 90 and coverage.percent('line') - coverage.percent('branch') >= 20:
            findings.append(
                Finding(
                    "LINE_BRANCH_COVERAGE_DIVERGENCE",
                    "High line coverage materially exceeds branch coverage.",
                    {"line_percent": coverage.percent('line'), "branch_percent": coverage.percent('branch')},
                )
            )
    if coverage and coverage.percent('line') is not None and coverage.percent('line') >= 90 and weak:
        findings.append(
            Finding(
                "HIGH_COVERAGE_WEAK_ORACLE",
                "High line coverage coexists with weak oracle signals; coverage alone is insufficient evidence.",
                {"line_percent": coverage.percent('line'), "weak_oracle_tests": len(weak)},
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
