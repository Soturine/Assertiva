"""Revision-scoped impact graph: only provable relations, every edge tied to a revision and an evidence tier."""

import json
from pathlib import Path

import pytest

from assertiva.impact import ImpactEdge, ImpactGraph, Relation, StaleGraphError, build_impact_graph
from assertiva.evidence import to_jsonable

from conftest import write


def project(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        write(root / rel, text)
    return root


def edges(graph, relation=None, source=None):
    return {(e.source, e.target, e.relation, e.tier) for e in graph.edges
            if (relation is None or e.relation is relation) and (source is None or e.source == source)}


BASE = {
    "calc.py": "def add(a, b):\n    return a + b\n",
    "service.py": "from calc import add\n\ndef total(items):\n    return add(sum(items), 0)\n",
    "tests/test_calc.py": "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
    "tests/test_service.py": "import service\n\ndef test_total():\n    assert service.total([1, 2]) == 3\n",
}


def test_every_edge_carries_revision_tier_and_provenance(tmp_path):
    graph = build_impact_graph(project(tmp_path, BASE))
    edge = next(e for e in graph.edges if e.source == "tests/test_calc.py" and e.target == "calc.py")
    assert edge.relation is Relation.IMPORTS and edge.tier == "E3"
    assert edge.revision == graph.revision and edge.provenance and edge.confidence is None
    assert {"tests/test_calc.py", "tests/test_service.py"} == graph.tests
    data = json.loads(json.dumps(to_jsonable(graph)))
    assert data["revision"] == graph.revision and data["edges"]


def test_direct_and_transitive_imports(tmp_path):
    graph = build_impact_graph(project(tmp_path, BASE))
    assert ("tests/test_service.py", "service.py", Relation.IMPORTS, "E3") in edges(graph)
    assert ("service.py", "calc.py", Relation.IMPORTS, "E3") in edges(graph)
    affected = graph.affected_tests({"calc.py"})
    assert set(affected) == {"tests/test_calc.py", "tests/test_service.py"}
    assert [e.target for e in affected["tests/test_service.py"]] == ["service.py", "calc.py"]  # the proving path


def test_package_imports_resolve_modules_parents_and_relative_imports(tmp_path):
    graph = build_impact_graph(project(tmp_path, {
        "src/shop/__init__.py": "",
        "src/shop/pricing.py": "from .rules import RATE\n\ndef price(x):\n    return x * RATE\n",
        "src/shop/rules.py": "RATE = 2\n",
        "tests/test_pricing.py": "from shop.pricing import price\n\ndef test_price():\n    assert price(2) == 4\n",
    }))
    assert ("tests/test_pricing.py", "src/shop/pricing.py", Relation.IMPORTS, "E3") in edges(graph)
    assert ("tests/test_pricing.py", "src/shop/__init__.py", Relation.IMPORTS, "E3") in edges(graph)
    assert ("src/shop/pricing.py", "src/shop/rules.py", Relation.IMPORTS, "E3") in edges(graph)
    assert "tests/test_pricing.py" in graph.affected_tests({"src/shop/rules.py"})


def test_shared_fixture_scope_is_declared_by_the_framework(tmp_path):
    graph = build_impact_graph(project(tmp_path, {
        "db.py": "def connect():\n    return {}\n",
        "tests/conftest.py": "import pytest\nfrom db import connect\n\n@pytest.fixture\ndef conn():\n    return connect()\n",
        "tests/unit/test_repo.py": "def test_repo(conn):\n    assert conn == {}\n",
        "other/test_elsewhere.py": "def test_x():\n    assert True\n",
    }))
    assert ("tests/unit/test_repo.py", "tests/conftest.py", Relation.DEPENDS_ON_FIXTURE, "E1") in edges(graph)
    assert set(graph.affected_tests({"db.py"})) == {"tests/unit/test_repo.py"}  # via the fixture file, not by name
    assert "other/test_elsewhere.py" not in graph.affected_tests({"tests/conftest.py"})


def test_base_test_and_helper_relations(tmp_path):
    graph = build_impact_graph(project(tmp_path, {
        "tests/base.py": "class BaseCase:\n    def test_contract(self):\n        assert self.make() is not None\n",
        "tests/helpers.py": "def fake_order():\n    return {'id': 1}\n",
        "tests/test_orders.py": "from base import BaseCase\nfrom helpers import fake_order\n\n"
                                "class TestOrders(BaseCase):\n    def make(self):\n        return fake_order()\n",
    }))
    assert ("tests/test_orders.py", "tests/base.py", Relation.MATERIALIZES, "E3") in edges(graph)
    assert ("tests/test_orders.py", "tests/helpers.py", Relation.USES_HELPER, "E3") in edges(graph)
    assert set(graph.affected_tests({"tests/base.py"})) == {"tests/test_orders.py"}


def test_framework_configuration_is_a_declared_dependency(tmp_path):
    graph = build_impact_graph(project(tmp_path, {**BASE, "pytest.ini": "[pytest]\naddopts = -q\n"}))
    assert ("tests/test_calc.py", "pytest.ini", Relation.USES_CONFIG, "E1") in edges(graph)
    assert set(graph.affected_tests({"pytest.ini"})) == graph.tests


def test_declarations_are_recorded(tmp_path):
    graph = build_impact_graph(project(tmp_path, BASE))
    assert ("tests/test_calc.py::test_add", "tests/test_calc.py", Relation.DECLARES, "E1") in edges(graph, Relation.DECLARES)


def test_dynamic_import_is_unknown_never_guessed(tmp_path):
    graph = build_impact_graph(project(tmp_path, {
        "plugins/__init__.py": "",
        "plugins/alpha.py": "NAME = 'alpha'\n",
        "loader.py": "import importlib\n\ndef load(name):\n    return importlib.import_module('plugins.' + name)\n",
        "fixed.py": "import importlib\nalpha = importlib.import_module('plugins.alpha')\n",
        "tests/test_loader.py": "from loader import load\nimport fixed\n\ndef test_load():\n    assert load('alpha').NAME == 'alpha'\n",
    }))
    [unknown] = [u for u in graph.unknowns if u.node == "loader.py"]
    assert "computed" in unknown.reason and unknown.revision == graph.revision
    assert not any(e.source == "loader.py" and e.target.startswith("plugins/") for e in graph.edges)  # no invented edge
    literal = [e for e in graph.edges if e.source == "fixed.py" and e.target == "plugins/alpha.py"]
    assert literal and literal[0].tier == "E3" and any("dynamic" in lim for lim in literal[0].limitations)
    assert graph.unknowns_reached_by("tests/test_loader.py") == [unknown]


def test_deleted_or_renamed_module_is_still_traceable(tmp_path):
    before = build_impact_graph(project(tmp_path / "a", BASE))
    renamed = dict(BASE)
    renamed["pricing.py"] = renamed.pop("calc.py")
    after = build_impact_graph(project(tmp_path / "b", renamed))
    assert before.revision != after.revision
    # the new revision has no node for calc.py, but it knows who still imports a module it cannot find
    assert "calc.py" not in after.nodes
    assert after.importers_of_missing("calc.py") == {"tests/test_calc.py", "service.py"}
    assert set(before.affected_tests({"calc.py"})) == {"tests/test_calc.py", "tests/test_service.py"}


def test_a_graph_never_answers_for_another_revision(tmp_path):
    graph = build_impact_graph(project(tmp_path, BASE))
    with pytest.raises(StaleGraphError):
        graph.require("another-revision")
    foreign = ImpactEdge("tests/test_calc.py", "calc.py", Relation.IMPORTS, "another-revision", "E3", "an older analysis")
    graph.add(foreign)
    assert foreign not in graph.edges and foreign in graph.stale
    assert any("another revision" in lim for lim in graph.limitations)


def test_naming_heuristics_are_never_facts(tmp_path):
    graph = build_impact_graph(project(tmp_path, {
        "calc.py": "def add(a, b):\n    return a + b\n",
        "tests/test_calc.py": "def test_add():\n    assert True\n",  # no import: only the name relates them
    }))
    [guess] = [e for e in graph.edges if e.relation is Relation.TESTS]
    assert (guess.source, guess.target, guess.tier) == ("tests/test_calc.py", "calc.py", "E4")
    assert guess not in graph.facts()
    assert graph.affected_tests({"calc.py"}, include_heuristic=False) == {}
    assert set(graph.affected_tests({"calc.py"})) == {"tests/test_calc.py"}


def test_unparseable_file_is_unknown(tmp_path):
    graph = build_impact_graph(project(tmp_path, {**BASE, "broken.py": "def x(:\n"}))
    assert any(u.node == "broken.py" and "parse" in u.reason for u in graph.unknowns)
