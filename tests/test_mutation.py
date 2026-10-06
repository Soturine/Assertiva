"""Mutation evidence: normalized from existing tools, never invented."""

import json
import re
import sys
from pathlib import Path

import pytest

from assertiva.adapters.mutation import load_mutation_report
from assertiva.candidate import DeltaState, QualificationCheck, StageStatus
from assertiva.improve import discard_session, qualify_candidate, start_improve
from assertiva.models import MutantStatus

from conftest import write

CALC = "def add(a, b):\n    return a + b\n"


def mte(path, mutants, source=CALC, framework=None):
    report = {"schemaVersion": "2", "thresholds": {"high": 80, "low": 60}, "files": {"calc.py": {"language": "python", "source": source, "mutants": mutants}}}
    if framework:
        report["framework"] = framework
    path.write_text(json.dumps(report), encoding="utf-8")
    return path


def mutant(i, status, **extra):
    return {"id": str(i), "mutatorName": "ArithmeticOperator", "location": {"start": {"line": 2, "column": 14}, "end": {"line": 2, "column": 15}}, "status": status, **extra}


def test_mutation_testing_elements_report_is_normalized(tmp_path):
    report = mte(
        tmp_path / "mutation.json",
        [
            mutant(1, "Killed", killedBy=["tests/test_calc.py::test_add"], replacement="-", duration=12),
            mutant(2, "Survived", replacement="*"),
            mutant(3, "NoCoverage"),
            mutant(4, "Timeout"),
            mutant(5, "CompileError"),
            mutant(6, "Ignored"),
        ],
        framework={"name": "StrykerJS", "version": "8.0.0"},
    )
    run = load_mutation_report(report)
    assert run.error is None and run.per_mutant
    assert (run.tool, run.tool_version) == ("StrykerJS", "8.0.0")
    assert run.count(MutantStatus.KILLED) == 1 and run.count(MutantStatus.SURVIVED) == 1
    assert run.count(MutantStatus.NO_COVERAGE) == 1 and run.count(MutantStatus.TIMEOUT) == 1
    assert run.count(MutantStatus.ERROR) == 1 and run.count(MutantStatus.IGNORED) == 1
    killed = run.mutants[0]
    assert (killed.path, killed.line, killed.operator, killed.replacement) == ("calc.py", 2, "ArithmeticOperator", "-")
    assert killed.killed_by == ("tests/test_calc.py::test_add",) and killed.duration_ms == 12
    assert run.mutants[4].native_status == "CompileError"


def test_missing_optional_fields_stay_unknown(tmp_path):
    run = load_mutation_report(mte(tmp_path / "m.json", [mutant(1, "Survived")]))
    [record] = run.mutants
    assert record.replacement is None and record.killed_by == () and record.duration_ms is None
    assert run.tool is None and run.tool_version is None


def test_unrecognized_status_is_preserved_as_unknown(tmp_path):
    run = load_mutation_report(mte(tmp_path / "m.json", [mutant(1, "Pending"), mutant(2, "SomeFutureStatus")]))
    assert [m.status for m in run.mutants] == [MutantStatus.UNKNOWN, MutantStatus.UNKNOWN]
    assert [m.native_status for m in run.mutants] == ["Pending", "SomeFutureStatus"]


@pytest.mark.parametrize("content", ["{not json", json.dumps({"files": "nope"}), "<html></html>"])
def test_malformed_or_unsupported_report_is_an_error_not_evidence(tmp_path, content):
    path = tmp_path / "broken.json"
    path.write_text(content, encoding="utf-8")
    run = load_mutation_report(path)
    assert run.error
    assert run.mutants == [] and run.total == 0


def test_pit_xml_report_is_normalized(tmp_path):
    path = tmp_path / "mutations.xml"
    path.write_text(
        "<?xml version='1.0' encoding='UTF-8'?><mutations partial='false'>"
        "<mutation detected='true' status='KILLED' numberOfTestsRun='2'><sourceFile>Calc.java</sourceFile>"
        "<mutatedClass>com.example.Calc</mutatedClass><mutatedMethod>add</mutatedMethod><methodDescription>(II)I</methodDescription>"
        "<lineNumber>7</lineNumber><mutator>org.pitest.mutationtest.engine.gregor.mutators.MathMutator</mutator>"
        "<indexes><index>5</index></indexes><blocks><block>0</block></blocks>"
        "<killingTest>com.example.CalcTest.[engine:junit-jupiter]/[method:adds()]</killingTest>"
        "<description>Replaced integer addition with subtraction</description></mutation>"
        "<mutation detected='false' status='SURVIVED' numberOfTestsRun='2'><sourceFile>Calc.java</sourceFile>"
        "<mutatedClass>com.example.Calc</mutatedClass><mutatedMethod>sign</mutatedMethod><methodDescription>(I)I</methodDescription>"
        "<lineNumber>11</lineNumber><mutator>ConditionalsBoundaryMutator</mutator><indexes><index>3</index></indexes>"
        "<blocks><block>1</block></blocks><killingTest/><description>changed conditional boundary</description></mutation>"
        "<mutation detected='true' status='TIMED_OUT' numberOfTestsRun='1'><sourceFile>Calc.java</sourceFile>"
        "<mutatedClass>com.example.Calc</mutatedClass><mutatedMethod>loop</mutatedMethod><methodDescription>()V</methodDescription>"
        "<lineNumber>20</lineNumber><mutator>NegateConditionalsMutator</mutator><indexes><index>1</index></indexes>"
        "<blocks><block>0</block></blocks><killingTest/><description>negated conditional</description></mutation>"
        "</mutations>",
        encoding="utf-8",
    )
    run = load_mutation_report(path)
    assert run.tool == "PIT" and run.per_mutant
    assert [m.status for m in run.mutants] == [MutantStatus.KILLED, MutantStatus.SURVIVED, MutantStatus.TIMEOUT]
    first = run.mutants[0]
    assert first.path == "com/example/Calc.java" and first.line == 7
    assert first.killed_by == ("com.example.CalcTest.[engine:junit-jupiter]/[method:adds()]",)
    assert run.mutants[1].killed_by == ()
    assert run.mutants[2].native_status == "TIMED_OUT"
    assert any("revision" in item for item in run.limitations)


def test_aggregate_only_report_has_counts_but_no_mutant_identity(tmp_path):
    path = tmp_path / "mutmut-cicd-stats.json"
    path.write_text(json.dumps({"killed": 8, "survived": 2, "total": 12, "no_tests": 1, "skipped": 0, "suspicious": 1, "timeout": 0, "check_was_interrupted_by_user": 0, "segfault": 0}))
    run = load_mutation_report(path)
    assert run.tool == "mutmut" and not run.per_mutant and run.mutants == []
    assert run.count(MutantStatus.KILLED) == 8 and run.count(MutantStatus.SURVIVED) == 2
    assert run.count(MutantStatus.NO_COVERAGE) == 1 and run.count(MutantStatus.UNKNOWN) == 1
    assert any("per-mutant" in item for item in run.limitations)


def test_core_modules_do_not_branch_on_mutation_tools():
    import assertiva

    core = Path(assertiva.__file__).parent  # the code under test, installed or source
    for name in ("candidate.py", "evidence.py", "improve.py", "verification.py", "workspace.py", "report.py", "models.py"):
        text = (core / name).read_text(encoding="utf-8").lower()
        assert not re.search(r"stryker|pitest|\bpit\b|mutmut|cosmic", text), name


# --- qualification -----------------------------------------------------------------

def stage(q):
    return next(s for s in q.checks if s.check is QualificationCheck.MUTATION_OR_NEGATIVE_CONTROLS)


def delta(q, name):
    return next(d for d in q.metric_deltas if d.name == name)


@pytest.fixture
def session(calc_project):
    session = start_improve(calc_project, python=sys.executable)
    yield session
    discard_session(session)


@pytest.mark.integration
def test_survivor_appears_in_qualification_even_with_high_score(session, tmp_path):
    killed = [mutant(i, "Killed") for i in range(19)]
    baseline = mte(tmp_path / "b.json", [mutant(i, "Killed") for i in range(18)] + [mutant(90, "Survived"), mutant(91, "Survived")])
    candidate = mte(tmp_path / "c.json", killed + [mutant(91, "Survived", replacement="a * b")])
    q = qualify_candidate(session, mutation_reports={"baseline": baseline, "candidate": candidate}).qualification
    result = stage(q)
    assert result.status is StageStatus.FAIL  # 95% detected, but a mutant still survives
    assert "MUTATION_SURVIVOR" in result.summary and "calc.py:2" in result.summary
    assert delta(q, "mutation_survived").state is DeltaState.IMPROVED
    assert delta(q, "mutation_killed").state is DeltaState.IMPROVED


@pytest.mark.integration
def test_all_mutants_killed_passes_stage(session, tmp_path):
    report = mte(tmp_path / "c.json", [mutant(1, "Killed"), mutant(2, "Timeout")])
    q = qualify_candidate(session, mutation_reports={"candidate": report}).qualification
    assert stage(q).status is StageStatus.PASS
    assert delta(q, "mutation_killed").state is DeltaState.UNKNOWN  # no baseline report: not invented


@pytest.mark.integration
def test_report_for_other_source_is_stale_not_pass(session, tmp_path):
    report = mte(tmp_path / "c.json", [mutant(1, "Killed")], source="def add(a, b):\n    return b + a\n")
    q = qualify_candidate(session, mutation_reports={"candidate": report}).qualification
    assert stage(q).status is StageStatus.UNKNOWN
    assert any("does not match" in item for item in stage(q).limitations)


@pytest.mark.integration
def test_unreadable_report_blocks_instead_of_passing(session, tmp_path):
    broken = tmp_path / "c.json"
    broken.write_text("{", encoding="utf-8")
    q = qualify_candidate(session, mutation_reports={"candidate": broken}).qualification
    assert stage(q).status is StageStatus.BLOCKED


@pytest.mark.integration
def test_mutation_report_and_negative_controls_coexist(session, tmp_path):
    from assertiva.evidence import NegativeControl

    control = NegativeControl("mul", "calc.py", "return a + b", "return a * b", "add() returns the sum")
    report = mte(tmp_path / "c.json", [mutant(1, "Killed")])
    q = qualify_candidate(session, negative_controls=[control], mutation_reports={"candidate": report}).qualification
    result = stage(q)
    assert result.status is StageStatus.FAIL  # the control survives even though every mutant was killed
    assert "NEGATIVE_CONTROL_SURVIVED" in result.summary


@pytest.mark.integration
def test_different_mutant_sets_make_counts_contextual(session, tmp_path):
    baseline = mte(tmp_path / "b.json", [mutant(1, "Killed")])
    candidate = mte(tmp_path / "c.json", [mutant(1, "Killed"), mutant(2, "Killed")])
    q = qualify_candidate(session, mutation_reports={"baseline": baseline, "candidate": candidate}).qualification
    assert delta(q, "mutation_killed").state is DeltaState.CHANGED


# --- user-facing surfaces ------------------------------------------------------------

def test_audit_ingests_mutation_report_and_lists_survivors(calc_project, tmp_path, capsys):
    from assertiva import cli

    report = mte(tmp_path / "m.json", [mutant(1, "Killed"), mutant(2, "Survived", replacement="a * b")])
    code = cli.main(["audit", str(calc_project), "--mutation-report", str(report), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    finding = next(f for f in payload["findings"] if f["code"] == "MUTATION_SURVIVORS")
    assert finding["evidence"]["survivors"] == ["calc.py:2 ArithmeticOperator (a * b)"]
    assert payload["states"]["current"]["metrics"]["mutation_survived"]["value"] == 1
    assert "mutation-evidence" in Path(payload["report_path"]).read_text(encoding="utf-8")


def test_audit_reports_unreadable_mutation_report(calc_project, tmp_path, capsys):
    from assertiva import cli

    broken = tmp_path / "m.json"
    broken.write_text("{", encoding="utf-8")
    cli.main(["audit", str(calc_project), "--mutation-report", str(broken), "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert any(f["code"] == "MUTATION_REPORT_UNREADABLE" for f in payload["findings"])
    assert "mutation_killed" not in payload["states"]["current"]["metrics"]


@pytest.mark.integration
def test_improve_cli_accepts_state_targeted_mutation_reports(calc_project, tmp_path, capsys):
    from assertiva import cli

    report = mte(tmp_path / "c.json", [mutant(1, "Killed")])
    cli.main(["improve", str(calc_project), "--python", sys.executable, "--output", "json"])
    capsys.readouterr()
    cli.main(["improve", str(calc_project), "--python", sys.executable, "--mutation-report", f"candidate={report}", "--output", "json"])
    payload = json.loads(capsys.readouterr().out)
    stage = next(c for s in payload["candidate_qualification"]["stages"] for c in s["checks"] if c["check"] == "MUTATION_OR_NEGATIVE_CONTROLS")
    assert stage["status"] == "PASS"
    assert cli.main(["improve", str(calc_project), "--mutation-report", "elsewhere=x.json"]) == 2
    cli.main(["improve", str(calc_project), "--discard"])
