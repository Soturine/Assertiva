"""Execution budget: expensive evidence is bounded, reused when equivalent, and never PASS when refused."""

import json
import sys
from pathlib import Path

import pytest

from assertiva import process
from assertiva.candidate import QualificationStage, StageStatus

from conftest import write

REPO = Path(__file__).resolve().parents[1]


def test_depth_is_propagated_to_child_processes(tmp_path, monkeypatch):
    monkeypatch.setenv("ASSERTIVA_DEPTH", "1")
    result = process.run_command([sys.executable, "-c", "import os; print(os.environ['ASSERTIVA_DEPTH'])"], tmp_path)
    assert result.stdout.strip() == "2"


def test_budget_exhaustion_is_not_pass(calc_project, monkeypatch):
    from assertiva.evidence import measure

    monkeypatch.setenv("ASSERTIVA_DEPTH", str(process.MAX_DEPTH))
    state = measure(calc_project, "current", "isolated-project-copy", sys.executable)
    assert [run.status for run in state.runs] == [StageStatus.BLOCKED]
    assert "depth" in state.runs[0].limitations[0]
    [decision] = [d for d in state.budget if d.stage == "tests"]
    assert decision.decision == "BLOCKED" and "depth" in decision.reason


@pytest.mark.integration
def test_nested_assertiva_execution_is_bounded(tmp_path):
    """A project whose test audits itself with --execute: recursion must stop at the depth budget."""
    root = tmp_path / "self-auditing"
    out = tmp_path / "levels"
    out.mkdir()
    write(root / "conftest.py", "")
    write(
        root / "tests" / "test_self.py",
        "import json, os, subprocess, sys\nfrom pathlib import Path\n\n"
        "def test_audits_itself():\n"
        f"    env = dict(os.environ, PYTHONPATH=r'{REPO}')\n"
        "    result = subprocess.run([sys.executable, '-m', 'assertiva.cli', 'audit', str(Path.cwd()), '--execute',\n"
        "                             '--python', sys.executable, '--output', 'json'], capture_output=True, text=True, env=env, timeout=120)\n"
        "    assert result.returncode == 0, result.stderr\n"
        f"    Path(r'{out}', 'depth-' + os.environ['ASSERTIVA_DEPTH']).write_text(result.stdout)\n",
    )
    from assertiva.audit import run_audit

    base = process.current_depth()  # 0 normally, 1 when this suite itself runs under a self-dogfood
    report = run_audit(root, execute=True, python=sys.executable)
    assert report["states"]["current"]["runs"][0]["status"] == "PASS"
    levels = sorted(p.name for p in out.iterdir())
    # bounded: one self-audit per level up to the budget, never beyond it
    assert levels == [f"depth-{d}" for d in range(base + 1, process.MAX_DEPTH + 1)]
    deepest = json.loads((out / f"depth-{process.MAX_DEPTH}").read_text())
    assert deepest["states"]["current"]["runs"][0]["status"] == "BLOCKED"
    assert deepest["execution_budget"]["depth"] == process.MAX_DEPTH


@pytest.mark.artifact
def test_artifact_qualification_does_not_recurse(tmp_path):
    """The artifact's own tests qualify the same artifact again: the nested attempt is refused."""
    from test_artifact import make_package

    from assertiva.adapters.python_package import PythonPackageAdapter

    root = make_package(tmp_path / "recursive")
    write(
        root / "tests" / "test_qualifies_itself.py",
        "import sys\nfrom pathlib import Path\n\n"
        f"sys.path.insert(0, r'{REPO}')\n"
        "from assertiva.adapters.python_package import PythonPackageAdapter\n\n"
        "def test_nested_qualification_is_refused():\n"
        "    evidence = PythonPackageAdapter(python=sys.executable).qualify(Path.cwd())\n"
        "    assert evidence.status.value == 'BLOCKED', evidence\n"
        "    # refused as recursion of the same target (or by the depth budget when nested deeper)\n"
        "    assert 'recursive' in evidence.limitations[0] or 'execution budget' in evidence.limitations[0]\n",
    )
    evidence = PythonPackageAdapter(python=sys.executable).qualify(root)
    tests = next(c for c in evidence.checks if c.name == "tests")
    assert evidence.status is StageStatus.PASS, evidence
    assert "2 invocations" in tests.detail  # the nested attempt ran and was refused, it did not recurse


@pytest.mark.integration
def test_equivalent_evidence_is_not_reexecuted_without_reason(calc_project, tmp_path):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    write(calc_project / ".github" / "workflows" / "ci.yml", "on: [push]\njobs:\n  t:\n    steps:\n      - run: pytest -q\n")
    session = start_improve(calc_project, python=sys.executable)
    try:
        write(session.workspace / "tests" / "test_new.py", "def test_new():\n    assert 2 + 2 == 4\n")
        process.TRACE_PATH = tmp_path / "trace.jsonl"
        try:
            result = qualify_candidate(session, stability_reruns=0)
        finally:
            process.TRACE_PATH = None
    finally:
        discard_session(session)
    events = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
    in_pipeline = [e for e in events if e["event"] == "command_start" and e["stage"] == "PIPELINE_EQUIVALENT"]
    assert not any("pytest" in " ".join(e["command"]) for e in in_pipeline)
    pipeline = next(s for s in result.qualification.stages if s.stage is QualificationStage.PIPELINE_EQUIVALENT)
    assert pipeline.status is StageStatus.PASS
    assert any("reused" in note for note in pipeline.limitations)
    assert any(d.decision == "REUSED" and "pytest -q" in d.reason for d in result.budget)


@pytest.mark.integration
def test_widening_records_reason(calc_project):
    from assertiva.audit import run_audit

    report = run_audit(calc_project, execute=True, python=sys.executable)
    decisions = {d["stage"]: d for d in report["execution_budget"]["decisions"]}
    assert decisions["tests"]["decision"] == "EXECUTED"
    assert "--execute" in decisions["tests"]["reason"]


def test_fast_feedback_does_not_claim_full_qualification(calc_project):
    from assertiva.audit import run_audit

    report = run_audit(calc_project)
    budget = report["execution_budget"]
    assert budget["level"] == "static"
    decisions = {d["stage"]: d for d in budget["decisions"]}
    assert decisions["tests"]["decision"] == "NOT_RUN"
    assert report["states"]["current"]["runs"] == []
    assert not any("qualif" in item.lower() for item in report["claim_boundary"]["observed"])


def test_report_shows_execution_budget_decisions(calc_project):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    html = render_html(run_audit(calc_project))
    assert 'id="budget"' in html and "NOT_RUN" in html and "audit --execute" in html
