"""Minimal monorepo affected set: components and dependencies only where manifests declare them."""

import json

import pytest

from assertiva.components import build_component_graph
from assertiva.impact import build_impact_graph
from assertiva.selection import Confidence, FileChange, Trigger, select_tests

from conftest import write
from test_impact import project


def npm(name, deps=None):
    return json.dumps({"name": name, "version": "1.0.0", "dependencies": deps or {}})


JS = {
    "package.json": json.dumps({"name": "root", "private": True, "workspaces": ["packages/*", "apps/*"]}),
    "package-lock.json": "{}",
    "packages/core/package.json": npm("@acme/core"),
    "packages/core/index.js": "module.exports = 1;\n",
    "packages/ui/package.json": npm("@acme/ui", {"@acme/core": "workspace:*"}),
    "packages/docs/package.json": npm("@acme/docs"),
    "packages/docs/index.js": "module.exports = 'docs';\n",
    "apps/web/package.json": npm("web", {"@acme/ui": "^1.0.0", "left-pad": "1.3.0"}),
}


def affected(root, *paths):
    graph = build_component_graph(root)
    return graph.affected([FileChange(p, "M") for p in paths])


def test_declared_components_and_dependencies(tmp_path):
    graph = build_component_graph(project(tmp_path, JS))
    assert set(graph.components) == {"@acme/core", "@acme/ui", "@acme/docs", "web"}
    assert graph.components["@acme/ui"].depends_on == ("@acme/core",) and graph.components["@acme/ui"].tier == "E1"
    assert graph.components["web"].depends_on == ("@acme/ui",)  # external packages are not components
    assert graph.revision and graph.components["web"].provenance


def test_change_inside_one_package(tmp_path):
    assert set(affected(project(tmp_path, JS), "packages/docs/index.js")) == {"@acme/docs"}


def test_shared_package_reaches_its_dependents_transitively(tmp_path):
    result = affected(project(tmp_path, JS), "packages/core/index.js")
    assert set(result) == {"@acme/core", "@acme/ui", "web"}
    assert "depends on" in result["web"]


def js_select(root, path):
    graph = build_impact_graph(root)
    return select_tests(graph, [FileChange(path, "M")], revision=graph.revision, components=build_component_graph(root))


@pytest.mark.parametrize("path", ["package.json", "package-lock.json"])
def test_workspace_configuration_affects_every_component(tmp_path, path):
    root = project(tmp_path, JS)
    assert set(affected(root, path)) == {"@acme/core", "@acme/ui", "@acme/docs", "web"}
    selection = js_select(root, path)
    assert selection.full and Trigger.CONFIGURATION in {w.trigger for w in selection.widening}


def test_root_file_outside_components_widens(tmp_path):
    root = project(tmp_path, {**JS, "tsconfig.base.json": "{}"})
    assert affected(root, "tsconfig.base.json") == {}  # a fact: no component owns it
    selection = js_select(root, "tsconfig.base.json")
    assert selection.full and Trigger.UNMAPPED_CHANGE in {w.trigger for w in selection.widening}


def test_unknown_dependency_widens(tmp_path):
    files = {**JS, "packages/tool/package.json": npm("tool", {"@acme/missing": "workspace:*", "x": "file:../../vendor/x"})}
    root = project(tmp_path, files)
    graph = build_component_graph(root)
    assert len(graph.components["tool"].unknown_dependencies) == 2
    assert "unknown dependencies" in graph.affected([FileChange("packages/docs/index.js", "M")])["tool"]
    selection = js_select(root, "packages/docs/index.js")
    assert [u.node for u in selection.unknown_dependencies] == ["packages/tool"]
    assert selection.confidence is not Confidence.PROVEN_PATHS


def test_layout_without_declared_workspaces_has_no_components(tmp_path):
    graph = build_component_graph(project(tmp_path, {"package.json": npm("single"), "index.js": ""}))
    assert graph.components == {}


# --- Python packages in one repository: component knowledge narrows the test selection ---------

def py_component(name, deps=()):
    return f"[project]\nname = \"{name}\"\nversion = \"1.0\"\ndependencies = {json.dumps(list(deps))}\n"


PY = {
    "packages/a/pyproject.toml": py_component("acme-a"),
    "packages/a/src/acme_a/__init__.py": "",
    "packages/a/src/acme_a/core.py": "def value():\n    return 1\n",
    "packages/a/src/acme_a/unused.py": "X = 1\n",
    "packages/a/tests/test_core.py": "from acme_a.core import value\n\ndef test_value():\n    assert value() == 1\n",
    "packages/b/pyproject.toml": py_component("acme-b", ["Acme_A>=1.0"]),
    "packages/b/src/acme_b/__init__.py": "",
    "packages/b/src/acme_b/api.py": "from acme_a.core import value\n\ndef api():\n    return value() + 1\n",
    "packages/b/tests/test_api.py": "from acme_b.api import api\n\ndef test_api():\n    assert api() == 2\n",
    "packages/c/pyproject.toml": py_component("acme-c"),
    "packages/c/src/acme_c/__init__.py": "",
    "packages/c/src/acme_c/tool.py": "def tool():\n    return 0\n",
    "packages/c/tests/test_tool.py": "from acme_c.tool import tool\n\ndef test_tool():\n    assert tool() == 0\n",
}


def py_select(root, path):
    graph = build_impact_graph(root)
    components = build_component_graph(root)
    return select_tests(graph, [FileChange(path, "M")], revision=graph.revision, components=components)


def test_python_components_and_normalized_dependency_names(tmp_path):
    graph = build_component_graph(project(tmp_path, PY))
    assert set(graph.components) == {"acme-a", "acme-b", "acme-c"}
    assert graph.components["acme-b"].depends_on == ("acme-a",)


def test_cross_package_change_selects_dependents_only(tmp_path):
    selection = py_select(project(tmp_path, PY), "packages/a/src/acme_a/core.py")
    assert set(selection.selected) == {"packages/a/tests/test_core.py", "packages/b/tests/test_api.py"}
    assert selection.confidence is Confidence.PROVEN_PATHS
    assert set(selection.affected_components) == {"acme-a", "acme-b"}


def test_undeclared_cross_package_import_is_still_proven(tmp_path):
    files = {**PY, "packages/c/src/acme_c/tool.py": "from acme_a.core import value\n\ndef tool():\n    return value() - 1\n"}
    selection = py_select(project(tmp_path, files), "packages/a/src/acme_a/core.py")
    assert "packages/c/tests/test_tool.py" in selection.selected  # a manifest-only selector would miss this


def test_no_proven_path_inside_a_component_widens_to_its_scope_not_everything(tmp_path):
    selection = py_select(project(tmp_path, PY), "packages/a/src/acme_a/unused.py")
    assert not selection.full
    assert set(selection.selected) == {"packages/a/tests/test_core.py", "packages/b/tests/test_api.py"}
    assert Trigger.COMPONENT_DEPENDENCY in {w.trigger for w in selection.widening}
    assert selection.confidence is not Confidence.PROVEN_PATHS


def test_audit_reports_affected_components(tmp_path):
    import subprocess

    from assertiva.audit import run_audit
    from assertiva.report import render_html

    root = project(tmp_path, PY)
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)
    write(root / "packages/a/src/acme_a/core.py", "def value():\n    return 2\n")
    report = run_audit(root, changed_since="HEAD")
    assert set(report["test_selection"]["affected_components"]) == {"acme-a", "acme-b"}
    assert "Affected components" in render_html(report)


def test_stale_component_graph_widens(tmp_path):
    root = project(tmp_path, PY)
    graph = build_impact_graph(root)
    components = build_component_graph(root)
    components.revision = "another-tree"
    selection = select_tests(graph, [FileChange("packages/a/src/acme_a/core.py", "M")], revision=graph.revision, components=components)
    assert selection.full and Trigger.STALE_GRAPH in {w.trigger for w in selection.widening}
