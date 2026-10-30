"""Portfolio assurance MVP: register projects of different stacks (and a legacy one), audit them through the ordinary
audit, keep project findings and Assertiva feedback apart, and say CURRENT/STALE/BLOCKED/UNKNOWN from evidence only."""

import json
import sys

import pytest

from assertiva import cli, portfolio
from assertiva.workspace import tree_fingerprint

from conftest import commit_all, git, write


def run(capsys, *args):
    code = cli.main(["portfolio", "--output", "json", *args])
    out, err = capsys.readouterr()
    return code, (json.loads(out) if out.strip() else None), err


def python_project(root):
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "test_calc.py", "from calc import add\n\ndef test_add():\n    assert add(2, 2) == 4\n")
    git(root, "init", "-q")
    commit_all(root)
    return root


def node_project(root):
    write(root / "package.json", json.dumps({"name": "cart", "scripts": {"test": "node --test"}}))
    write(root / "test" / "cart.test.js", "const test = require('node:test');\ntest('x', () => {});\n")
    return root


def legacy_project(root):
    write(root / "build.gradle", "apply plugin: 'java'\n")
    write(root / "src" / "test" / "java" / "AppTest.java", "public class AppTest { @Test public void t() {} }\n")
    return root


def test_three_stacks_and_a_legacy_project_register_without_being_changed(tmp_path, capsys, assertiva_home):
    roots = {"calc": python_project(tmp_path / "calc"), "cart": node_project(tmp_path / "cart"),
             "old-app": legacy_project(tmp_path / "old-app")}
    before = {name: tree_fingerprint(root) for name, root in roots.items()}
    for name, root in roots.items():
        extra = ["--phase", "legacy", "--need", "JDK 8 and Gradle 4"] if name == "old-app" else []
        code, payload, err = run(capsys, "add", str(root), *extra)
        assert code == 0, err
    code, listing, _ = run(capsys, "list")
    rows = {p["name"]: p for p in listing["projects"]}
    assert {p: rows[p]["status"] for p in rows} == {"calc": "UNKNOWN", "cart": "UNKNOWN", "old-app": "UNKNOWN"}
    assert rows["old-app"]["needs"] == ["JDK 8 and Gradle 4"] and rows["old-app"]["phase"] == "legacy"
    assert any(s["name"] == "runner:node-test" for s in rows["cart"]["stacks"])
    assert "path" not in rows["calc"]  # paths are left out of a shareable view
    assert {name: tree_fingerprint(root) for name, root in roots.items()} == before


@pytest.mark.integration
def test_an_audit_through_the_portfolio_is_current_until_the_project_moves(tmp_path, capsys, assertiva_home):
    root = python_project(tmp_path / "calc")
    run(capsys, "add", str(root))
    code, summary, err = run(capsys, "audit", "calc", "--execute", "--python", sys.executable)
    assert code == 0, err
    assert summary["executed"] and summary["tests_status"] == "PASS" and summary["units"]["invocations"] == 1
    assert summary["units"]["static_definitions"] == 1 and summary["revision"]
    assert portfolio.status(portfolio.get("calc"))["status"] == "CURRENT"
    write(root / "calc.py", "def add(a, b):\n    return a - b\n")
    commit_all(root)
    assert portfolio.status(portfolio.get("calc"))["status"] == "STALE"


def test_a_static_audit_is_not_a_test_run(tmp_path, capsys, assertiva_home):
    root = python_project(tmp_path / "calc")
    run(capsys, "add", str(root))
    code, summary, _ = run(capsys, "audit", "calc")
    assert summary["executed"] is False and summary["tests_status"] == "NOT_RUN"
    assert portfolio.status(portfolio.get("calc"))["last_real_execution"] is None


def test_assertiva_feedback_is_deduplicated_kept_apart_and_needs_evidence_to_close(tmp_path, capsys, assertiva_home):
    run(capsys, "add", str(python_project(tmp_path / "calc")))
    args = ["feedback", "calc", "--kind", "FALSE_POSITIVE", "--rule", "SWALLOWED_EXCEPTION",
            "--signature", "try: f(); assert False; except ValueError: pass", "--reproducer", "tests/test_oracle_calibration.py"]
    _, first, _ = run(capsys, *args)
    _, again, _ = run(capsys, *args)
    assert first["feedback_id"] == again["feedback_id"] and len(again["sightings"]) == 2
    code, _, err = run(capsys, "move", first["feedback_id"], "FIXED_IN_ASSERTIVA_BRANCH", "--evidence", "trust me")
    assert code == 2 and "commit SHA" in err  # no closing on assertion alone
    code, moved, _ = run(capsys, "move", first["feedback_id"], "FIXED_IN_ASSERTIVA_BRANCH", "--evidence", "fixed in 3a821ac")
    assert code == 0 and moved["history"][-1]["evidence"] == "fixed in 3a821ac"
    _, seen, _ = run(capsys, *args)  # seen again after the fix: a regression, history kept
    assert seen["state"] == "REGRESSION" and [h["to"] for h in seen["history"]] == ["FIXED_IN_ASSERTIVA_BRANCH", "REGRESSION"]
    report = portfolio.report()
    assert report["assertiva_feedback"][0]["rule"] == "SWALLOWED_EXCEPTION"
    assert all("feedback" not in p for p in report["projects"])  # project rows carry no Assertiva feedback


def test_the_page_escapes_everything_and_names_no_paths(tmp_path, capsys, assertiva_home):
    root = python_project(tmp_path / "calc")
    run(capsys, "add", str(root), "--criticality", "<script>alert(1)</script>")
    run(capsys, "feedback", "calc", "--kind", "MISSING_ANALYSIS", "--rule", "X", "--signature", "<img src=x onerror=alert(1)>",
        "--reproducer", "synthetic")
    page = tmp_path / "portfolio.html"
    code, _, _ = run(capsys, "report", "--html", str(page))
    text = page.read_text(encoding="utf-8")
    assert code == 0 and "<img src=x" not in text and "&lt;img src=x" in text and "<script" not in text
    assert str(root) not in text and str(tmp_path) not in text


def test_bad_names_and_projects_inside_assertiva_home_are_refused(tmp_path, capsys, assertiva_home):
    code, _, err = run(capsys, "add", str(python_project(tmp_path / "calc")), "--name", "../escape")
    assert code == 2 and "name" in err
    assert run(capsys, "audit", "missing")[0] == 2
