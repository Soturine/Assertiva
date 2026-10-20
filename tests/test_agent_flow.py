"""The investigation an agent runs with the engine, end to end through the CLI on one reproducible project
(tests/fixtures/protection-demo, under Git): what an audit observes and records, how a later failing change is
explained by history, what a change-based selection runs first, and that nothing reaches the project without approval.
The mutation and improvement steps of the same flow are tests/test_proof_of_protection.py."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.workspace import tree_fingerprint

from conftest import git, write

pytestmark = pytest.mark.integration

DEMO = Path(__file__).parent / "fixtures" / "protection-demo"


def _run(capsys, *args) -> dict:
    capsys.readouterr()
    cli.main([*args, "--output", "json"])
    return json.loads(capsys.readouterr().out)


def test_audit_history_failure_explanation_selection_and_approval(tmp_path, capsys):
    root = tmp_path / "project"
    shutil.copytree(DEMO, root, ignore=shutil.ignore_patterns("strengthened", "negative-controls.json", "README.md"))
    write(root / ".gitignore", "__pycache__/\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    reports = tmp_path / "reports"

    # 1-4: the audit observes a green suite and names the weak oracle as a lead, not a verdict
    first = _run(capsys, "audit", str(root), "--execute", "--python", sys.executable, "--report-dir", str(reports), "--ctrf")
    assert first["history"]["enabled"] and first["exported"] == {"ctrf": "audit.ctrf.json"}
    assert any(f["code"].startswith("WEAK_ORACLE") for f in first["findings"])
    boundary = first["claim_boundary"]
    assert boundary["observed"] and boundary["limitations"] and "not_evidenced" in boundary

    # a later change breaks the product: history says it is new, where it last passed, and that the product raised
    write(root / "pricing.py", (root / "pricing.py").read_text(encoding="utf-8").replace("total_cents // 10", "total_cents // None"))
    second = _run(capsys, "audit", str(root), "--execute", "--python", sys.executable, "--report-dir", str(reports))
    failing = [e for e in second["history"]["invocations"] if e.get("novelty")]
    assert failing and all(e["novelty"] == "NEW_FAILURE" and e["passed_before_at"] for e in failing)
    assert {e["origin"] for e in failing} == {"PRODUCT"}

    # 8: the selection for that change runs the tests history says failed first
    selection = _run(capsys, "audit", str(root), "--changed-since", "HEAD", "--report-dir", str(reports))["test_selection"]
    assert selection["priority"] and selection["priority"][0]["reason"] == "failed in its last recorded run"

    # 10: nothing is applied to the project without the human's approval
    before = tree_fingerprint(root)
    workspace = Path(_run(capsys, "improve", str(root), "--python", sys.executable)["candidate_workspace"])
    write(workspace / "tests" / "test_extra.py", "def test_extra():\n    assert True\n")
    cli.main(["improve", str(root), "--discard"])
    assert tree_fingerprint(root) == before and not (root / "tests" / "test_extra.py").exists()
