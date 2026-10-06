"""Conservative test selection: the smallest reasonable evidence set, widened whenever impact is not proven.

Every case here is one where a naive selector (same-name tests, direct imports only, or
"no edge found = nothing to run") would miss a regression."""

import subprocess
import sys

import pytest

from assertiva.impact import build_impact_graph
from assertiva.selection import Confidence, FileChange, Trigger, changed_files, select_tests

from conftest import write
from test_impact import BASE, project

ALL = {"tests/test_calc.py", "tests/test_service.py"}


def select(root, *changes, **kwargs):
    graph = build_impact_graph(root)
    return select_tests(graph, [c if isinstance(c, FileChange) else FileChange(c, "M") for c in changes],
                        revision=graph.revision, **kwargs)


def triggers(selection):
    return {w.trigger for w in selection.widening}


def test_transitive_dependency_is_selected_with_its_proof(tmp_path):
    selection = select(project(tmp_path, BASE), "calc.py")
    assert set(selection.selected) == ALL  # a same-name selector would miss tests/test_service.py
    reason = selection.selected["tests/test_service.py"][0]
    assert reason.tier == "E3" and reason.path == ("tests/test_service.py -IMPORTS-> service.py", "service.py -IMPORTS-> calc.py")
    assert selection.confidence is Confidence.PROVEN_PATHS and not selection.widening


def test_unaffected_tests_are_not_selected_and_say_why(tmp_path):
    root = project(tmp_path, {**BASE, "tax.py": "RATE = 1\n", "tests/test_tax.py": "from tax import RATE\n\ndef test_rate():\n    assert RATE\n"})
    selection = select(root, "tax.py")
    assert set(selection.selected) == {"tests/test_tax.py"}
    assert set(selection.not_selected) == ALL and "no proven path" in selection.not_selected["tests/test_calc.py"]


def test_changed_tests_always_run(tmp_path):
    selection = select(project(tmp_path, BASE), "tests/test_calc.py")
    assert set(selection.selected) == {"tests/test_calc.py"}
    assert selection.selected["tests/test_calc.py"][0].reason == "the test file itself changed"


def test_shared_fixture_change_widens_to_its_scope(tmp_path):
    root = project(tmp_path, {
        **BASE, "tests/conftest.py": "import pytest\n\n@pytest.fixture\ndef rate():\n    return 1\n",
        "other/test_other.py": "def test_other():\n    assert True\n",
    })
    selection = select(root, "tests/conftest.py")
    assert Trigger.SHARED_FIXTURE in triggers(selection)
    assert set(selection.selected) == ALL and "other/test_other.py" not in selection.selected


def test_test_helper_and_base_class_changes_reach_their_users(tmp_path):
    root = project(tmp_path, {
        "tests/base.py": "class BaseCase:\n    def test_contract(self):\n        assert self.make()\n",
        "tests/helpers.py": "def order():\n    return {'id': 1}\n",
        "tests/test_orders.py": "from base import BaseCase\nfrom helpers import order\n\nclass TestOrders(BaseCase):\n    def make(self):\n        return order()\n",
        "tests/test_misc.py": "def test_misc():\n    assert True\n",
    })
    assert set(select(root, "tests/helpers.py").selected) == {"tests/test_orders.py"}
    assert set(select(root, "tests/base.py").selected) == {"tests/test_orders.py"}


@pytest.mark.parametrize("config", ["pytest.ini", "pyproject.toml"])
def test_framework_or_build_configuration_widens_to_the_full_suite(tmp_path, config):
    root = project(tmp_path, {**BASE, config: "[pytest]\n" if config == "pytest.ini" else "[project]\nname = 'x'\n",
                              "tax.py": "RATE = 1\n", "tests/test_tax.py": "def test_rate():\n    assert True\n"})
    selection = select(root, config)
    assert selection.full and Trigger.CONFIGURATION in triggers(selection)
    assert selection.confidence is Confidence.FULL_SUITE


def test_dynamic_import_widens_and_never_claims_total_confidence(tmp_path):
    root = project(tmp_path, {
        **BASE,
        "plugins/__init__.py": "", "plugins/alpha.py": "NAME = 'alpha'\n",
        "loader.py": "import importlib\n\ndef load(name):\n    return importlib.import_module('plugins.' + name)\n",
        "tests/test_loader.py": "from loader import load\n\ndef test_load():\n    assert load('alpha').NAME == 'alpha'\n",
    })
    selection = select(root, "plugins/alpha.py")
    # no static edge reaches tests/test_loader.py: a graph-only selector would run nothing relevant
    assert "tests/test_loader.py" in selection.selected
    assert selection.selected["tests/test_loader.py"][0].trigger is Trigger.UNKNOWN_RELATION
    assert Trigger.UNKNOWN_RELATION in triggers(selection)
    assert [u.node for u in selection.unknown_dependencies] == ["loader.py"]


def test_selector_never_claims_total_confidence_when_an_unknown_path_exists(tmp_path):
    root = project(tmp_path, {
        **BASE,
        "loader.py": "import importlib\n\ndef load(name):\n    return importlib.import_module(name)\n",
        "tests/test_loader.py": "from loader import load\n\ndef test_load():\n    assert load('calc')\n",
    })
    graph = build_impact_graph(root)
    for change in ("calc.py", "service.py", "tests/test_calc.py", "loader.py"):
        selection = select_tests(graph, [FileChange(change, "M")], revision=graph.revision)
        assert selection.confidence is not Confidence.PROVEN_PATHS, change
        assert selection.unknown_dependencies, change


def test_unknown_not_reachable_from_any_test_does_not_block_proof(tmp_path):
    root = project(tmp_path, {**BASE, "scripts/tool.py": "import importlib\nimportlib.import_module(input())\n"})
    selection = select(root, "calc.py")
    assert selection.confidence is Confidence.PROVEN_PATHS and set(selection.selected) == ALL


def test_framework_declared_plugin_modules_are_dependencies(tmp_path):
    root = project(tmp_path, {
        **BASE, "fixtures/__init__.py": "", "fixtures/money.py": "import pytest\n\n@pytest.fixture\ndef cents():\n    return 100\n",
        "tests/conftest.py": "pytest_plugins = ['fixtures.money']\n",
    })
    selection = select(root, "fixtures/money.py")
    assert set(selection.selected) == ALL  # reached through conftest's pytest_plugins declaration


def test_deleted_or_renamed_module_selects_its_former_users(tmp_path):
    files = dict(BASE)
    files["pricing.py"] = files.pop("calc.py")
    root = project(tmp_path, files)
    selection = select(root, FileChange("pricing.py", "R", old_path="calc.py"))
    assert set(selection.selected) == ALL
    assert any("deleted or renamed" in r.reason for r in selection.selected["tests/test_calc.py"])


@pytest.mark.parametrize("path", ["tests/data/prices.json", "README.md", "web/app.js"])
def test_changes_no_adapter_can_map_widen_to_the_full_suite(tmp_path, path):
    root = project(tmp_path, {**BASE, path: "{}\n"})
    selection = select(root, path)
    assert selection.full and Trigger.UNMAPPED_CHANGE in triggers(selection)


def test_no_proven_path_is_never_no_test_needed(tmp_path):
    root = project(tmp_path, {**BASE, "unused.py": "def f():\n    return 1\n"})
    selection = select(root, "unused.py")
    assert selection.full and Trigger.NO_PROVEN_PATH in triggers(selection)
    assert selection.fallback


def test_heuristic_only_relation_is_not_proof(tmp_path):
    root = project(tmp_path, {"calc.py": "def add(a, b):\n    return a + b\n",
                              "tests/test_calc.py": "def test_add():\n    assert True\n",
                              "tests/test_other.py": "def test_other():\n    assert True\n"})
    selection = select(root, "calc.py")
    assert selection.full and Trigger.NO_PROVEN_PATH in triggers(selection)  # E4 alone never narrows the run
    assert any(r.tier == "E4" for r in selection.selected["tests/test_calc.py"])


def test_stale_graph_widens_to_the_full_suite(tmp_path):
    graph = build_impact_graph(project(tmp_path, BASE))
    selection = select_tests(graph, [FileChange("calc.py", "M")], revision="a-different-tree")
    assert selection.full and Trigger.STALE_GRAPH in triggers(selection)


def test_no_change_is_not_nothing_to_run(tmp_path):
    selection = select(project(tmp_path, BASE))
    assert selection.full and Trigger.NO_CHANGES in triggers(selection)


def test_known_failures_always_run(tmp_path):
    root = project(tmp_path, {**BASE, "tax.py": "RATE = 1\n", "tests/test_tax.py": "from tax import RATE\n\ndef test_rate():\n    assert RATE\n"})
    selection = select(root, "tax.py", must_run={"tests/test_calc.py"})
    assert set(selection.selected) == {"tests/test_tax.py", "tests/test_calc.py"}


def test_selection_has_provenance(tmp_path):
    graph = build_impact_graph(project(tmp_path, BASE))
    selection = select_tests(graph, [FileChange("calc.py", "M")], revision=graph.revision, base="HEAD~1")
    assert selection.revision == graph.revision and selection.base == "HEAD~1"
    assert any("selected tests passed" in lim for lim in selection.limitations)


def test_changes_come_from_git_including_uncommitted_and_renames(tmp_path):
    root = project(tmp_path, BASE)
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)
    subprocess.run([*git, "mv", "calc.py", "pricing.py"], cwd=root, check=True, capture_output=True)
    write(root / "service.py", "from pricing import add\n")
    write(root / "new_module.py", "X = 1\n")
    changes = {(c.path, c.status, c.old_path) for c in changed_files(root, "HEAD")}
    assert ("pricing.py", "R", "calc.py") in changes and ("service.py", "M", None) in changes
    assert ("new_module.py", "A", None) in changes
    with pytest.raises(ValueError):
        changed_files(root, "no-such-revision")


# --- through the audit: no new command, an explicit selected-set claim ------------------------

def _repo(root):
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "base"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)
    return root


def test_audit_reports_selection_without_running(tmp_path):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    root = _repo(project(tmp_path, {**BASE, "tax.py": "RATE = 1\n", "tests/test_tax.py": "from tax import RATE\n\ndef test_rate():\n    assert RATE\n"}))
    write(root / "tax.py", "RATE = 2\n")
    report = run_audit(root, changed_since="HEAD")
    selection = report["test_selection"]
    assert set(selection["selected"]) == {"tests/test_tax.py"} and selection["confidence"] == "PROVEN_PATHS"
    assert selection["counts"] == {"selected": 1, "not_selected": 2, "mapped": 3}
    assert any("selected tests passed" in lim for lim in report["claim_boundary"]["limitations"])
    html = render_html(report)
    assert "Impact-based test selection" in html and "tests/test_tax.py" in html


def test_unknown_base_revision_widens_instead_of_failing(tmp_path):
    from assertiva.audit import run_audit

    root = _repo(project(tmp_path, BASE))
    selection = run_audit(root, changed_since="no-such-revision")["test_selection"]
    assert selection["full"] and selection["widening"][0]["trigger"] == "CHANGES_UNKNOWN"


@pytest.mark.integration
def test_audit_executes_only_the_selected_set_and_says_so(tmp_path):
    from assertiva.audit import run_audit

    root = _repo(project(tmp_path, {**BASE, "tax.py": "RATE = 1\n", "tests/test_tax.py": "from tax import RATE\n\ndef test_rate():\n    assert RATE\n"}))
    write(root / "tax.py", "RATE = 0\n")  # a regression the selected test catches
    report = run_audit(root, execute=True, python=sys.executable, changed_since="HEAD")
    [run] = report["states"]["current"]["runs"]
    assert run["invocations"] == 1 and run["status"] == "FAIL"
    assert any("selected-set run: 1 of 3" in item for item in report["claim_boundary"]["observed"])
    assert any("2 mapped test files were not run" in item for item in report["claim_boundary"]["not_evidenced"])


def test_pytest_subset_keeps_the_full_runs_rootdir():
    from assertiva.adapters.pytest_native import PytestNativeAdapter

    # explicit paths would otherwise move rootdir (and conftest discovery) to their common ancestor
    assert PytestNativeAdapter().selection_args(["pkg/b/test_b.py", "pkg/a/test_a.py", "web/x.test.js"]) == [
        "--rootdir=.", "pkg/a/test_a.py", "pkg/b/test_b.py"]
    assert PytestNativeAdapter().selection_args(["web/x.test.js"]) == []


# --- conftest.py: explicit fixtures vs autouse/hooks/module code --------------------------------

CONFTEST = (
    "import pytest\n\n\ndef make_row():\n    return {'id': 1}\n\n\n"
    "@pytest.fixture\ndef row():\n    return make_row()\n\n\n"
    "@pytest.fixture\ndef clock():\n    return 0\n\n\n"
    "@pytest.fixture(autouse=True)\ndef env(monkeypatch):\n    monkeypatch.setenv('X', '1')\n\n\n"
    "def pytest_configure(config):\n    pass\n"
)
FIXTURE_PROJECT = {
    **BASE,
    "tests/conftest.py": CONFTEST,
    "tests/test_rows.py": "def test_row(row):\n    assert row['id'] == 1\n",
    "tests/test_clock.py": "def test_clock(clock):\n    assert clock == 0\n",
    "tests/test_dynamic.py": "def test_any(request):\n    name = 'clo' + 'ck'\n    assert request.getfixturevalue(name) == 0\n",
}


def select_conftest(tmp_path, new_conftest):
    from assertiva.adapters.python_impact import PythonImpactAdapter

    root = project(tmp_path, {**FIXTURE_PROJECT, "tests/conftest.py": new_conftest})
    graph = build_impact_graph(root)
    before = PythonImpactAdapter().unit_digests("tests/conftest.py", CONFTEST)
    return select_tests(graph, [FileChange("tests/conftest.py", "M")], revision=graph.revision,
                        previous_units={"tests/conftest.py": before})


EVERY = {"tests/test_calc.py", "tests/test_service.py", "tests/test_rows.py", "tests/test_clock.py", "tests/test_dynamic.py"}


def test_changed_fixture_selects_only_tests_that_request_it(tmp_path):
    selection = select_conftest(tmp_path, CONFTEST.replace("return 0", "return 1"))
    assert set(selection.selected) == {"tests/test_clock.py", "tests/test_dynamic.py"}  # dynamic request may use any fixture


def test_changed_helper_reaches_fixtures_that_use_it(tmp_path):
    selection = select_conftest(tmp_path, CONFTEST.replace("{'id': 1}", "{'id': 2}"))
    assert set(selection.selected) == {"tests/test_rows.py", "tests/test_dynamic.py"}


@pytest.mark.parametrize("change", [
    ("monkeypatch.setenv('X', '1')", "monkeypatch.setenv('X', '2')"),  # autouse fixture
    ("def pytest_configure(config):\n    pass", "def pytest_configure(config):\n    config.x = 1"),  # hook
    ("import pytest\n", "import pytest\nimport os\n"),  # module-level code
])
def test_autouse_hooks_and_module_code_reach_every_test_in_scope(tmp_path, change):
    assert set(select_conftest(tmp_path, CONFTEST.replace(*change)).selected) == EVERY


def test_removed_fixture_falls_back_to_the_whole_scope(tmp_path):
    selection = select_conftest(tmp_path, CONFTEST.replace("@pytest.fixture\ndef clock():\n    return 0\n\n\n", ""))
    assert set(selection.selected) == EVERY and Trigger.SHARED_FIXTURE in triggers(selection)


def test_conftest_units_are_compared_against_the_base_revision(tmp_path):
    root = _repo(project(tmp_path, FIXTURE_PROJECT))
    write(root / "tests/conftest.py", CONFTEST.replace("return 0", "return 1"))
    from assertiva.selection import select_changes

    assert set(select_changes(root, "HEAD").selected) == {"tests/test_clock.py", "tests/test_dynamic.py"}
