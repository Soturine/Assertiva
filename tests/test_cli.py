import pytest
import json
import sys
from pathlib import Path

from assertiva import cli
from assertiva.workspace import tree_fingerprint

from conftest import write


def run(capsys, *args):
    code = cli.main([*args, "--python", sys.executable, "--output", "json"])
    return code, json.loads(capsys.readouterr().out)


def test_audit_unknown_project_reports_unknown_not_zero_tests(tmp_path, capsys):
    project = tmp_path / "unknown-toolchain"
    write(project / "build.custom", "verify: proprietary\n")
    code, payload = run(capsys, "audit", str(project))
    assert code == 0
    assert payload["status"] == "UNKNOWN"
    assert payload["findings"][0]["code"] == "NO_EXECUTABLE_TEST_ADAPTER_RECOGNIZED"


@pytest.mark.integration
def test_audit_does_not_modify_project_tree(calc_project, capsys, assertiva_home):
    # Adversarial fixture: executing this suite writes into the working directory,
    # and pytest normally creates caches. None of it may reach the audited project.
    write(
        calc_project / "tests" / "test_side_effect.py",
        "from pathlib import Path\n\ndef test_writes_into_cwd():\n"
        "    Path('side_effect.txt').write_text('x')\n    assert Path('side_effect.txt').read_text() == 'x'\n",
    )
    before = tree_fingerprint(calc_project)
    code, report = run(capsys, "audit", str(calc_project), "--execute")
    assert code == 0
    assert tree_fingerprint(calc_project) == before
    report_path = Path(report["report_path"])
    assert report_path.is_file() and report_path.is_relative_to(assertiva_home)
    assert report["states"]["current"]["metrics"]["test_invocations"]["value"] == 3


def test_assertiva_state_inside_project_is_refused(calc_project, capsys, monkeypatch):
    monkeypatch.setenv("ASSERTIVA_HOME", str(calc_project / ".assertiva"))
    assert cli.main(["audit", str(calc_project)]) == 2
    assert "outside the project" in capsys.readouterr().err
    assert not (calc_project / ".assertiva").exists()


def test_static_audit_states_that_tests_were_not_executed(calc_project, capsys):
    _, report = run(capsys, "audit", str(calc_project))
    assert report["states"]["current"]["runs"] == []
    assert any("not executed" in item for item in report["claim_boundary"]["limitations"])


def test_report_directory_inside_project_is_refused(calc_project, capsys):
    before = tree_fingerprint(calc_project)
    code = cli.main(["audit", str(calc_project), "--report-dir", str(calc_project / "reports")])
    assert code == 2
    assert "outside the project" in capsys.readouterr().err
    assert tree_fingerprint(calc_project) == before


@pytest.mark.integration
def test_improve_flow_is_one_command_with_explicit_approval(calc_project, capsys):
    original = tree_fingerprint(calc_project)

    code, started = run(capsys, "improve", str(calc_project))
    assert code == 0 and started["status"] == "CANDIDATE_WORKSPACE_READY"
    workspace = Path(started["candidate_workspace"])
    assert not workspace.is_relative_to(calc_project)
    write(workspace / "tests" / "test_strong.py", "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n")

    code, qualified = run(capsys, "improve", str(calc_project))
    assert code == 0 and qualified["workflow"] == "improve"
    assert qualified["states"]["applied"] is None
    assert [c["change_id"] for c in qualified["change_set"]["changes"]] == ["tests/test_strong.py"]
    assert tree_fingerprint(calc_project) == original

    code, applied = run(capsys, "improve", str(calc_project), "--approve", "tests/test_strong.py")
    assert code == 0 and applied["status"] == "APPLIED"
    assert (calc_project / "tests" / "test_strong.py").is_file()
    assert applied["states"]["applied"]["runs"][0]["status"] == "PASS"
    assert not workspace.exists()  # internal workspace is cleaned up after application


@pytest.mark.integration
def test_approve_before_qualification_is_refused(calc_project, capsys):
    run(capsys, "improve", str(calc_project))
    code = cli.main(["improve", str(calc_project), "--approve", "tests/x.py", "--python", sys.executable])
    assert code == 2
    assert "qualif" in capsys.readouterr().err
    cli.main(["improve", str(calc_project), "--discard"])


@pytest.mark.integration
def test_negative_controls_file_feeds_qualification(calc_project, tmp_path, capsys):
    controls = tmp_path / "controls.json"
    controls.write_text(json.dumps([{"control_id": "c1", "path": "calc.py", "find": "return a + b", "replace": "return a * b", "claim": "sum"}]))
    run(capsys, "improve", str(calc_project))
    _, report = run(capsys, "improve", str(calc_project), "--negative-controls", str(controls))
    stage = next(c for s in report["candidate_qualification"]["stages"] for c in s["checks"] if c["check"] == "MUTATION_OR_NEGATIVE_CONTROLS")
    assert stage["status"] == "FAIL"  # baseline suite cannot tell + from * for add(2, 2)
    cli.main(["improve", str(calc_project), "--discard"])
