"""TCC-A11: nested package scripts form a graph; a script CI reaches twice runs twice (cost, not new evidence)."""

import json

from assertiva.adapters.package_scripts import script_graph
from assertiva.verification import discover_surface, surface_findings

from conftest import write

SCRIPTS = {"test": "npm run test:unit && npm run test:integration", "test:unit": "node --test test/unit",
           "test:integration": "npm run test:mqtt && node --test test/integration", "test:mqtt": "node --test test/mqtt",
           "loop:a": "npm run loop:b", "loop:b": "npm run loop:a", "lint": "eslint ."}


def test_the_graph_has_direct_calls_and_transitive_reach_and_stops_on_cycles():
    graph = script_graph(SCRIPTS)
    assert graph["test"]["calls"] == ["test:unit", "test:integration"]
    assert graph["test"]["reaches"] == ["test:unit", "test:integration", "test:mqtt"]
    assert graph["loop:a"]["reaches"] == ["loop:b"] and graph["lint"] == {"calls": [], "reaches": []}


def project(root, steps):
    write(root / "package.json", json.dumps({"name": "app", "scripts": SCRIPTS}))
    write(root / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n" + steps)
    return root


def repetition(root):
    return next((f for f in surface_findings(discover_surface(root)) if f.code == "NESTED_SCRIPT_REPETITION"), None)


def test_ci_running_a_parent_and_its_child_repeats_the_shared_scripts(tmp_path):
    found = repetition(project(tmp_path, "      - run: npm test\n      - run: npm run test:integration\n"))
    assert found is not None and found.severity == "info"
    assert set(found.evidence["repeated"]) == {"test:integration", "test:mqtt"}


def test_ci_running_disjoint_scripts_repeats_nothing(tmp_path):
    # negative control: two different gates are not repetition
    assert repetition(project(tmp_path, "      - run: npm test\n      - run: npm run lint\n")) is None
