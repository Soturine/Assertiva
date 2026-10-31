"""Dependency & migration assurance MVP: declared vs locked vs installed are kept apart, usage is read statically,
nothing is installed or looked up, and readiness never claims READY without an executed upgrade."""

import json
import sys
from pathlib import Path

from assertiva import cli
from assertiva.dependencies import _satisfies_npm, inventory
from assertiva.workspace import tree_fingerprint

from conftest import write


def python_project(root):
    write(root / "pyproject.toml", '[project]\nname = "ledger"\nversion = "1"\ndependencies = ["PyYAML>=6", "requests>=2,<3", "rich"]\n')
    write(root / "uv.lock", 'version = 1\n[[package]]\nname = "pyyaml"\nversion = "6.0.2"\n\n[[package]]\nname = "requests"\nversion = "3.1.0"\n')
    write(root / "ledger" / "__init__.py", "")
    write(root / "ledger" / "config.py", "import yaml\n\ndef load(text):\n    return yaml.safe_load(text)\n")
    write(root / "ledger" / "fetch.py", "import requests\n")
    write(root / "tests" / "test_config.py", "from ledger.config import load\n\ndef test_load():\n    assert load('a: 1') == {'a': 1}\n")
    return root


def js_project(root):
    write(root / "package.json", json.dumps({"name": "app", "dependencies": {"left-pad": "^1.3.0", "lodash": "~4.17.0"},
                                             "devDependencies": {"jest": "29.7.0"}}))
    write(root / "package-lock.json", json.dumps({"lockfileVersion": 3, "packages": {
        "": {}, "node_modules/left-pad": {"version": "1.3.0"}, "node_modules/lodash": {"version": "4.18.1"},
        "node_modules/jest": {"version": "29.7.0"}}}))
    write(root / "node_modules" / "left-pad" / "package.json", json.dumps({"version": "1.2.0"}))
    return root


def by_name(data):
    return {d["name"]: d for d in data["dependencies"]}


def test_python_declared_locked_and_usage_are_kept_apart(tmp_path):
    deps = by_name(inventory(python_project(tmp_path / "py")))
    assert deps["PyYAML"]["lock_state"] == "LOCK_SATISFIES_RANGE" and deps["PyYAML"]["locked"] == "6.0.2"
    assert deps["requests"]["lock_state"] == "LOCK_OUTSIDE_RANGE"  # 3.1.0 is outside <3
    assert deps["rich"]["lock_state"] == "NOT_LOCKED"
    assert deps["PyYAML"]["usage"]["tests_importing_directly"] == ["tests/test_config.py"]
    assert deps["requests"]["usage"]["product_files"] == ["ledger/fetch.py"] and not deps["requests"]["usage"]["tests_importing_directly"] and not deps["requests"]["usage"]["tests_reaching_transitively"]
    assert all(d["migration_readiness"] != "READY" for d in deps.values())  # nothing upgraded: never READY


def test_js_ranges_lock_and_installed_drift(tmp_path):
    deps = by_name(inventory(js_project(tmp_path / "js")))
    assert deps["left-pad"]["lock_state"] == "LOCK_SATISFIES_RANGE"
    assert deps["left-pad"]["install_state"] == "INSTALLED_DIFFERS_FROM_LOCK"  # 1.2.0 installed, 1.3.0 locked
    assert deps["lodash"]["lock_state"] == "LOCK_OUTSIDE_RANGE"  # ~4.17.0 does not accept 4.18.1
    assert deps["jest"]["install_state"] == "NOT_INSTALLED_HERE" and deps["jest"]["migration_readiness"] == "UNKNOWN"


def test_npm_range_rules_decide_only_what_they_can():
    assert _satisfies_npm("1.4.2", "^1.3.0") and not _satisfies_npm("2.0.0", "^1.3.0")
    assert _satisfies_npm("0.2.5", "^0.2.1") and not _satisfies_npm("0.3.0", "^0.2.1")
    assert _satisfies_npm("4.17.9", "4.17.x") and _satisfies_npm("5.0.0", ">=4")
    assert _satisfies_npm("1.0.0", "1 || 2") is None and _satisfies_npm("1.0.0", "github:a/b") is None


def test_vulnerabilities_are_unknown_not_an_empty_list(tmp_path):
    data = inventory(js_project(tmp_path / "js"))
    assert data["vulnerabilities"]["status"] == "UNKNOWN" and "OSV-Scanner" in data["vulnerabilities"]["reuse"]


def test_the_audit_option_adds_the_inventory_and_findings_without_touching_the_project(tmp_path, capsys, assertiva_home):
    root = python_project(tmp_path / "py")
    before = tree_fingerprint(root)
    assert cli.main(["audit", str(root), "--dependencies", "--python", sys.executable, "--output", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    codes = {f["code"] for f in report["findings"]}
    assert {"DEPENDENCY_LOCK_OUTSIDE_RANGE", "DEPENDENCY_USAGE_NOT_REACHED_STATICALLY"} <= codes
    assert report["dependencies"]["note"].startswith("nothing was installed")
    schema = json.loads((Path(__file__).parents[1] / "schemas" / "assurance-report.schema.json").read_text(encoding="utf-8"))
    assert set(report) <= set(schema["properties"])  # the published contract lists the key (additionalProperties: false)
    for entry in report["dependencies"]["dependencies"]:
        assert set(schema["properties"]["dependencies"]["properties"]["dependencies"]["items"]["required"]) <= set(entry)
    assert tree_fingerprint(root) == before
    assert cli.main(["audit", str(root), "--output", "json"]) == 0
    assert "dependencies" not in json.loads(capsys.readouterr().out)  # opt-in only


# --- CP-F3: what static imports can and cannot say ------------------------------------------------------------------

def usage_project(root):
    write(root / "pyproject.toml", '[project]\nname = "ledger"\nversion = "1"\n'
          'dependencies = ["PyYAML>=6", "requests>=2", "rich", "simplejson", "pluggy-extra"]\n'
          '[project.entry-points."ledger.plugins"]\nextra = "pluggy_extra:plugin"\n')
    write(root / "ledger" / "__init__.py", "")
    write(root / "ledger" / "config.py", "import yaml as y\n\ndef load(text):\n    return y.safe_load(text)\n")
    write(root / "ledger" / "api.py", "from .config import load\n\ndef handle(text):\n    return load(text)\n")  # relative
    write(root / "ledger" / "net.py", "import requests\n\ndef fetch(url):\n    return requests.get(url)\n")
    write(root / "ledger" / "report.py", "from rich import print as rprint\n\ndef show(x):\n    rprint(x)\n\ndef total(xs):\n    return sum(xs)\n")
    write(root / "ledger" / "codec.py", "import importlib\n\ndef dumps(x):\n    return importlib.import_module('simplejson').dumps(x)\n")
    write(root / "tests" / "test_api.py", "from ledger.api import handle\n\ndef test_handle():\n    assert handle('a: 1') == {'a': 1}\n")
    write(root / "tests" / "test_report.py", "from ledger.report import total\n\ndef test_total():\n    assert total([1, 2]) == 3\n")
    return root


def test_a_dependency_reached_only_through_another_project_module_is_reached(tmp_path):
    deps = by_name(inventory(usage_project(tmp_path / "u")))
    yaml_usage = deps["PyYAML"]["usage"]
    assert yaml_usage["tests_importing_directly"] == [] and yaml_usage["tests_reaching_transitively"] == ["tests/test_api.py"]


def test_importing_code_that_uses_a_dependency_is_never_called_exercised(tmp_path):
    deps = by_name(inventory(usage_project(tmp_path / "u")))
    rich = deps["rich"]["usage"]  # the test imports ledger.report but calls total(), not show()
    assert rich["tests_importing_directly"] == ["tests/test_report.py"] and rich["exercised"] == "UNKNOWN"
    assert deps["rich"]["migration_readiness"] == "READY_WITH_GAPS" and "not shown to exercise" in deps["rich"]["readiness_basis"]


def test_no_static_path_is_not_a_claim_that_no_test_reaches_it(tmp_path):
    data = inventory(usage_project(tmp_path / "u"))
    deps = by_name(data)
    assert deps["requests"]["usage"]["tests_reaching_transitively"] == []
    from assertiva.dependencies import findings

    [found] = [f for f in findings(data) if f.code == "DEPENDENCY_USAGE_NOT_REACHED_STATICALLY"]
    assert [d["name"] for d in found.evidence["dependencies"]] == ["requests"]
    assert "dynamic" in found.evidence["limitations"] and found.evidence["basis"] == "STATIC"
    assert not any(f.code == "DEPENDENCY_USAGE_UNTESTED" for f in findings(data))  # the overclaiming code is gone


def test_dynamic_and_plugin_uses_are_inferred_or_unknown_never_reported_unreached(tmp_path):
    data = inventory(usage_project(tmp_path / "u"))
    deps = by_name(data)
    assert deps["simplejson"]["usage"]["dynamic_imports"] == ["ledger/codec.py"]  # literal import_module("simplejson")
    assert deps["simplejson"]["usage"]["dynamic_basis"] == "INFERRED"
    assert deps["pluggy-extra"]["migration_readiness"] == "UNKNOWN"  # an entry point, no import: not claimed either way
    from assertiva.dependencies import findings

    reported = [d["name"] for f in findings(data) if f.code == "DEPENDENCY_USAGE_NOT_REACHED_STATICALLY" for d in f.evidence["dependencies"]]
    assert "simplejson" not in reported and "pluggy-extra" not in reported
