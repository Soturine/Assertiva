"""Which top-level classes of a Python test module a native runner would collect (bounded, static).

pytest collects `Test*` classes and every unittest.TestCase subclass whatever its name; unittest collects
TestCase subclasses only, with methods prefixed `test`. Bases are resolved only through `import unittest
[as u]`, `from unittest import TestCase [as T]`, builtins and classes defined in the same module. Anything
else (bases imported from other modules, star imports, computed bases, metaclasses) is UNRESOLVED, never
guessed: a class is not a TestCase just because it has `test_*` methods. Native collection is authoritative.
"""

from __future__ import annotations

import ast
import builtins
from enum import Enum

TESTCASE_METHOD_PREFIX = "test"  # unittest.TestLoader.testMethodPrefix
_UNITTEST_CASES = {"TestCase", "IsolatedAsyncioTestCase"}
# Frameworks whose documented test bases are unittest.TestCase subclasses (imported by name from these modules).
_CASE_MODULES = {
    "unittest": _UNITTEST_CASES,
    "django.test": {"SimpleTestCase", "TestCase", "TransactionTestCase", "LiveServerTestCase"},
    "rest_framework.test": {"APISimpleTestCase", "APITestCase", "APITransactionTestCase", "APILiveServerTestCase"},
}


class ClassKind(str, Enum):
    TESTCASE = "TESTCASE"  # proven unittest.TestCase subclass, any name
    PYTEST_CLASS = "PYTEST_CLASS"  # `Test*` class not proven to be a TestCase (pytest naming rule)
    UNRESOLVED = "UNRESOLVED"  # base classes could not be resolved statically
    NOT_COLLECTED = "NOT_COLLECTED"


def classify_classes(tree: ast.Module) -> dict[str, ClassKind]:
    modules: set[str] = set()  # local names bound to the unittest module
    cases: set[str] = set()  # local names bound to unittest.TestCase (or a stdlib subclass)
    imported: set[str] = set()
    star = False
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "unittest":
                    modules.add(alias.asname or "unittest")
                else:
                    imported.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                star = star or alias.name == "*"
                if not node.level and alias.name in _CASE_MODULES.get(node.module or "", ()):
                    cases.add(alias.asname or alias.name)
                else:
                    imported.add(alias.asname or alias.name)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    memo: dict[str, bool | None] = {}

    def base_is_case(base: ast.expr, seen: frozenset[str]) -> bool | None:
        if isinstance(base, ast.Name):
            if base.id in cases:
                return True
            if base.id in classes and base.id not in imported:
                return is_case(base.id, seen)
            if base.id not in imported and not star and hasattr(builtins, base.id):
                return False
            return None
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and base.value.id in modules:
            return base.attr in _UNITTEST_CASES
        return None

    def is_case(name: str, seen: frozenset[str] = frozenset()) -> bool | None:
        """True: proven TestCase; False: proven not; None: unresolved."""
        if name in memo:
            return memo[name]
        if name in seen:
            return False
        node, result = classes[name], False
        for base in node.bases:
            found = base_is_case(base, seen | {name})
            if found:
                result = True
                break
            if found is None:
                result = None
        if result is False and node.keywords:  # metaclass or class kwargs: collection may differ
            result = None
        memo[name] = result
        return result

    kinds = {}
    for name in classes:
        case = is_case(name)
        if case:
            kinds[name] = ClassKind.TESTCASE
        elif name.startswith("Test"):
            kinds[name] = ClassKind.PYTEST_CLASS
        else:
            kinds[name] = ClassKind.UNRESOLVED if case is None else ClassKind.NOT_COLLECTED
    return kinds
