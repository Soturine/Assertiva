"""Python/pytest impact edges: imports (E3), pytest-declared fixture scope and configuration (E1),
declarations, base-test materialization, helpers and naming (E4).

Imports are resolved only to project files, the way Python would find them from the project root,
a ``src`` layout, or the test file's rootdir-less base directory (pytest's default import mode).
A computed dynamic import is an unknown, never a guess.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path, PurePosixPath

from assertiva.impact import ImpactContribution, ImpactEdge, Relation, UnknownRelation

_CONFIGS = ("pytest.ini", ".pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg")
_BUILD = ("pyproject.toml", "setup.py", "setup.cfg", "MANIFEST.in")
_TEST_DIRS = {"tests", "test", "testing"}
_DYNAMIC = {"import_module", "__import__", "run_module"}
_UNRESOLVABLE = {"spec_from_file_location", "run_path", "load_source", "SourceFileLoader"}


MODULE_UNIT = "<module>"


def _fixture(node: ast.AST) -> tuple[bool, bool, str | None]:
    """(is a fixture, is autouse, requested name when ``name=`` overrides the function name)."""
    for decorator in getattr(node, "decorator_list", ()):
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        name = target.attr if isinstance(target, ast.Attribute) else getattr(target, "id", None)
        if name != "fixture":
            continue
        keywords = {k.arg: k.value for k in decorator.keywords} if isinstance(decorator, ast.Call) else {}
        autouse = "autouse" in keywords and not (isinstance(keywords["autouse"], ast.Constant) and keywords["autouse"].value is False)
        alias = keywords.get("name")
        return True, autouse, alias.value if isinstance(alias, ast.Constant) and isinstance(alias.value, str) else None
    return False, False, None


def conftest_units(tree: ast.Module) -> dict[str, tuple[str, object, str]]:
    """Units of a conftest.py: name -> (kind, node(s), requested name).

    ``global`` units (module-level code, ``pytest_*`` hooks, autouse fixtures) apply to every test
    in scope; a ``fixture`` applies to tests that request it; a ``helper`` to its users.
    """
    units: dict[str, tuple[str, object, str]] = {}
    module: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fixture, autouse, alias = _fixture(node)
            kind = "global" if node.name.startswith("pytest_") or autouse else ("fixture" if fixture else "helper")
            units[node.name] = (kind, node, alias or node.name)
        else:
            module.append(node)
    units[MODULE_UNIT] = ("global", module, MODULE_UNIT)
    return units


def _digest(nodes) -> str:
    nodes = nodes if isinstance(nodes, list) else [nodes]
    return hashlib.sha256("\n".join(ast.dump(n) for n in nodes).encode()).hexdigest()[:16]


def _requested_fixtures(tree: ast.Module) -> tuple[set[str], bool]:
    """Fixture names a test file may request (parameters, usefixtures, getfixturevalue); True if dynamic."""
    names: set[str] = set()
    dynamic = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            names |= {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", None)
            literals = [a.value for a in node.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            if name == "usefixtures":
                names |= set(literals)
                dynamic |= len(literals) != len(node.args)
            elif name == "getfixturevalue":
                names |= set(literals)
                dynamic |= not literals
            if any(k.arg == "indirect" for k in node.keywords):
                dynamic = True
    return names, dynamic


def _is_test(rel: str) -> bool:
    name = PurePosixPath(rel).name
    return name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


class _Project:
    def __init__(self, root: Path, files: list[str]):
        self.root = root
        self.py = {f for f in files if f.endswith(".py")}
        self.tests = {f for f in self.py if _is_test(f)}
        self.test_dirs = {str(PurePosixPath(t).parent) for t in self.tests} - {"."}
        # projects in subdirectories (monorepos): their root and src layout are import roots too
        self.project_dirs = sorted({str(PurePosixPath(f).parent) for f in files
                                    if PurePosixPath(f).name in ("pyproject.toml", "setup.py") and "/" in f})

    def has(self, rel: str) -> bool:
        return rel in self.py

    def base_dir(self, rel: str) -> str:
        """First ancestor directory without ``__init__.py`` (pytest prepends it to sys.path)."""
        directory = PurePosixPath(rel).parent
        while str(directory) not in (".", "") and self.has(f"{directory}/__init__.py"):
            directory = directory.parent
        return "" if str(directory) == "." else str(directory)

    def roots(self, rel: str) -> list[str]:
        roots = ["", "src", *(r for d in self.project_dirs for r in (d, f"{d}/src")), self.base_dir(rel)]
        return list(dict.fromkeys(r for r in roots if r == "" or any(f.startswith(r + "/") for f in self.py)))

    @staticmethod
    def _join(root: str, *parts: str) -> str:
        return "/".join(p for p in (root, *parts) if p)

    def candidates(self, root: str, dotted: str) -> list[str]:
        parts = dotted.split(".")
        return [self._join(root, *parts[:-1], parts[-1] + ".py"), self._join(root, *parts, "__init__.py")]

    def resolve(self, dotted: str, roots: list[str]) -> list[str]:
        """Project files executed by importing ``dotted`` (the module and its parent packages)."""
        found = []
        for root in roots:
            hit = [c for c in self.candidates(root, dotted) if self.has(c)]
            if hit:
                parts = dotted.split(".")
                parents = [self._join(root, *parts[:i], "__init__.py") for i in range(1, len(parts))]
                found += hit + [p for p in parents if self.has(p)]
        return list(dict.fromkeys(found))

    def module_names(self, rel: str) -> set[str]:
        path = PurePosixPath(rel)
        parts = list(path.with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names = {".".join(parts)}
        for root in self.roots(rel):
            prefix = PurePosixPath(root).parts if root else ()
            if tuple(parts[: len(prefix)]) == prefix and len(parts) > len(prefix):
                names.add(".".join(parts[len(prefix):]))
        return names

    def test_side(self, rel: str) -> bool:
        path = PurePosixPath(rel)
        return rel in self.tests or path.name == "conftest.py" or str(path.parent) in self.test_dirs \
            or bool(_TEST_DIRS & set(path.parts[:-1]))


class PythonImpactAdapter:
    adapter_id = "python-impact"

    def impact(self, root: Path, revision: str, files: list[str]) -> ImpactContribution:
        project = _Project(Path(root), files)
        out = ImpactContribution(tests=set(project.tests), nodes=set(project.py))
        if not project.py:
            return out

        def edge(source, target, relation, tier, provenance, *limitations):
            out.edges.append(ImpactEdge(source, target, relation, revision, tier, provenance, tuple(limitations)))

        configs = [c for c in _CONFIGS if (project.root / c).is_file()]
        out.nodes |= set(configs)
        trees: dict[str, ast.Module] = {}
        for rel in sorted(project.py):
            try:
                trees[rel] = ast.parse((project.root / rel).read_text(encoding="utf-8"), filename=rel)
            except (SyntaxError, UnicodeDecodeError, OSError) as exc:
                out.unknowns.append(UnknownRelation(rel, f"the file could not be parsed ({type(exc).__name__}); its dependencies are unknown",
                                                    revision, "python ast"))
        units = {rel: conftest_units(tree) for rel, tree in trees.items() if PurePosixPath(rel).name == "conftest.py"}
        self._conftest_units(project, units, edge, out)
        for rel, tree in trees.items():
            imported = self._imports(project, rel, tree, edge, out, revision)
            for name, defined_in in imported.items():  # `from conftest import helper`: the unit, not the whole file
                for target in defined_in:
                    if target in units and name in units[target] and target != rel:
                        edge(rel, f"{target}::{name}", Relation.USES_HELPER, "E3", "imports a name defined in conftest.py")
            if rel in project.tests:
                self._declarations(rel, tree, edge)
                requested, dynamic = _requested_fixtures(tree)
                for conftest in self._scope(project, rel):
                    edge(rel, conftest, Relation.DEPENDS_ON_FIXTURE, "E1", "pytest conftest.py scoping (fixtures and hooks apply to tests below it)")
                    for name, (kind, _, alias) in units.get(conftest, {}).items():
                        unit = f"{conftest}::{name}"
                        if kind == "global":
                            edge(rel, unit, Relation.DEPENDS_ON_FIXTURE, "E1", "module code, hooks and autouse fixtures apply to every test in scope")
                        elif dynamic:
                            edge(rel, unit, Relation.DEPENDS_ON_FIXTURE, "E1", "fixtures requested dynamically",
                                 "a computed getfixturevalue/usefixtures or indirect parametrization may request any fixture")
                        elif kind == "fixture" and alias in requested:
                            edge(rel, unit, Relation.DEPENDS_ON_FIXTURE, "E1", "fixture requested by name")
                for config in configs:
                    edge(rel, config, Relation.USES_CONFIG, "E1", "pytest configuration discovery (rootdir ini files)",
                         "the file may hold no pytest settings; any change to it is treated as a configuration change")
                stem = PurePosixPath(rel).stem.removeprefix("test_").removesuffix("_test")
                for module in sorted(m for m in project.py - project.tests if PurePosixPath(m).stem == stem):
                    edge(rel, module, Relation.TESTS, "E4", "naming convention (test_<module>.py)", "a name match is not evidence that the test exercises the module")
        if any((project.root / b).is_file() for b in ("setup.py",)) or "pyproject.toml" in configs:
            for manifest in (b for b in _BUILD if (project.root / b).is_file()):
                edge("artifact:python-distribution", manifest, Relation.USES_ARTIFACT, "E1", "PEP 517 / setuptools build configuration")
        return out

    @staticmethod
    def _scope(project: _Project, rel: str) -> list[str]:
        """conftest.py files that apply to ``rel``: its directory and every ancestor up to the root."""
        found, directory = [], PurePosixPath(rel).parent
        while True:
            conftest = f"{directory}/conftest.py" if str(directory) != "." else "conftest.py"
            if project.has(conftest) and conftest != rel:
                found.append(conftest)
            if str(directory) in (".", ""):
                return found
            directory = directory.parent

    def _conftest_units(self, project: _Project, units: dict, edge, out: ImpactContribution) -> None:
        for conftest, members in units.items():
            out.units[conftest] = {name: _digest(node) for name, (_, node, _) in members.items()}
            out.nodes |= {f"{conftest}::{name}" for name in members}
            visible = [c for c in [conftest, *self._scope(project, conftest)] if c in units]
            for name, (kind, node, _) in members.items():
                nodes = node if isinstance(node, list) else [node]
                loaded = {n.id for part in nodes for n in ast.walk(part) if isinstance(n, ast.Name)}
                for other in sorted(loaded & set(members) - {name}):
                    edge(f"{conftest}::{name}", f"{conftest}::{other}", Relation.USES_HELPER, "E3", "same-file reference")
                if kind in ("fixture", "global") and not isinstance(node, list) and not isinstance(node, ast.ClassDef):
                    params = {a.arg for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
                    for owner in visible:
                        for other, (other_kind, _, alias) in units[owner].items():
                            if other_kind == "fixture" and alias in params and (owner, other) != (conftest, name):
                                edge(f"{conftest}::{name}", f"{owner}::{other}", Relation.DEPENDS_ON_FIXTURE, "E1", "fixture requested by a fixture")

    def unit_digests(self, path: str, text: str) -> dict[str, str] | None:
        """Per-unit digests of a conftest.py (to compare revisions); None for other files or unparseable text."""
        if PurePosixPath(path).name != "conftest.py":
            return None
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return None
        return {name: _digest(node) for name, (_, node, _) in conftest_units(tree).items()}

    @staticmethod
    def _declarations(rel: str, tree: ast.Module, edge) -> None:
        provenance = "pytest default collection rules (test_* functions, Test* classes)"
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                edge(f"{rel}::{node.name}", rel, Relation.DECLARES, "E1", provenance, "static: native collection is authoritative")
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test"):
                        edge(f"{rel}::{node.name}::{item.name}", rel, Relation.DECLARES, "E1", provenance, "static: native collection is authoritative")

    @staticmethod
    def _imports(project: _Project, rel: str, tree: ast.Module, edge, out: ImpactContribution, revision: str) -> dict[str, list[str]]:
        roots = project.roots(rel)
        package = PurePosixPath(rel).parent
        imported: dict[str, list[str]] = {}  # local name -> files that define it
        targets: dict[str, list[str]] = {}  # target file -> reasons
        plugins: dict[str, None] = {}

        def unresolved(dotted: str, base_roots: list[str]) -> None:
            out.unresolved.setdefault(rel, set()).update(c for r in base_roots for c in project.candidates(r, dotted))

        def add(dotted: str, base_roots: list[str], names=(), dynamic=False) -> None:
            found = project.resolve(dotted, base_roots) if dotted else []
            if dotted and not found:
                unresolved(dotted, base_roots)
            for name in names:  # `from pkg import name`: a submodule, or a name defined in pkg
                full = f"{dotted}.{name}" if dotted else name
                sub = [f for f in project.resolve(full, base_roots) if f not in found]
                if sub:
                    imported.setdefault(name, []).append(sub[0])
                    found += sub
                else:
                    unresolved(full, base_roots)  # an attribute, or a module that no longer exists
                    if found:
                        imported.setdefault(name, []).append(found[0])
            for target in found:
                targets.setdefault(target, []).append("dynamic" if dynamic else "static")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    add(alias.name, roots)
                    imported.setdefault((alias.asname or alias.name).split(".")[0], []).extend(project.resolve(alias.name, roots)[:1])
            elif isinstance(node, ast.ImportFrom):
                names = [a.name for a in node.names if a.name != "*"]
                if node.level:
                    base = package
                    for _ in range(node.level - 1):
                        base = base.parent
                    base_root = "" if str(base) == "." else str(base)
                    if node.module:
                        add(node.module, [base_root], names)
                    else:
                        add("", [base_root], names)
                else:
                    add(node.module or "", roots, names)
            elif isinstance(node, ast.Call) and _call_name(node) in _DYNAMIC | _UNRESOLVABLE:
                literal = node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                if _call_name(node) in _DYNAMIC and literal and not node.args[0].value.startswith("."):
                    add(node.args[0].value, roots, dynamic=True)
                else:
                    out.unknowns.append(UnknownRelation(
                        rel, f"dynamic import with a computed name or path (line {node.lineno}); what it loads is unknown",
                        revision, "python ast"))

        for node in tree.body:  # pytest_plugins: modules pytest imports by name (framework-declared)
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytest_plugins" for t in node.targets):
                values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
                for value in values:
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        for target in project.resolve(value.value, roots) or []:
                            plugins.setdefault(target, None)
                        if not project.resolve(value.value, roots):
                            unresolved(value.value, roots)
                    else:
                        out.unknowns.append(UnknownRelation(rel, f"pytest_plugins entry is not a literal (line {node.lineno}); the plugin is unknown",
                                                            revision, "python ast"))
        for target in plugins:
            if target != rel:
                edge(rel, target, Relation.IMPORTS, "E1", "pytest_plugins declaration (pytest imports these modules)")
        bases = {
            base.id if isinstance(base, ast.Name) else base.value.id
            for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name.startswith("Test")
            for base in node.bases
            if isinstance(base, ast.Name) or (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name))
        }
        inherited_from = {f for name in bases for f in imported.get(name, [])}
        for target, kinds in sorted(targets.items()):
            if target == rel:
                continue
            limitations = ("loaded through a literal dynamic import",) if "static" not in kinds else ()
            if target in inherited_from:
                edge(rel, target, Relation.MATERIALIZES, "E3", "static base-class import (inherited tests materialize here)", *limitations)
            elif project.test_side(rel) and project.test_side(target):
                edge(rel, target, Relation.USES_HELPER, "E3", "static import of test support code", *limitations)
            else:
                edge(rel, target, Relation.IMPORTS, "E3", "static import resolved to a project file", *limitations)
        return imported
