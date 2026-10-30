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
    assert deps["PyYAML"]["usage"]["tests_reaching_them"] == ["tests/test_config.py"]
    assert deps["requests"]["usage"]["product_files"] == ["ledger/fetch.py"] and not deps["requests"]["usage"]["tests_reaching_them"]
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
    assert {"DEPENDENCY_LOCK_OUTSIDE_RANGE", "DEPENDENCY_USAGE_UNTESTED"} <= codes
    assert report["dependencies"]["note"].startswith("nothing was installed")
    schema = json.loads((Path(__file__).parents[1] / "schemas" / "assurance-report.schema.json").read_text(encoding="utf-8"))
    assert set(report) <= set(schema["properties"])  # the published contract lists the key (additionalProperties: false)
    for entry in report["dependencies"]["dependencies"]:
        assert set(schema["properties"]["dependencies"]["properties"]["dependencies"]["items"]["required"]) <= set(entry)
    assert tree_fingerprint(root) == before
    assert cli.main(["audit", str(root), "--output", "json"]) == 0
    assert "dependencies" not in json.loads(capsys.readouterr().out)  # opt-in only
