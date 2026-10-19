"""The Cosmic Ray integration: its dump format, imported dumps, and the refusals that keep a run honest."""

from __future__ import annotations

import json
import sys

from assertiva.adapters import cosmic_ray
from assertiva.adapters.mutation import cosmic_ray_dump, load_mutation_report, run_mutation_tool
from assertiva.evidence import StateEvidence, attach_mutation
from assertiva.models import MutantStatus as S

from conftest import write


def _line(occurrence, result, operator="core/ReplaceBinaryOperator_Add_Mul"):
    item = {"job_id": f"j{occurrence}", "mutations": [{"module_path": "pkg\\calc.py", "operator_name": operator, "occurrence": occurrence,
                                                       "start_pos": [2, 13], "end_pos": [2, 14], "definition_name": "add"}]}
    return json.dumps([item, result])


DUMP = "\n".join([
    _line(0, {"worker_outcome": "normal", "test_outcome": "killed", "output": "F"}),
    _line(1, {"worker_outcome": "normal", "test_outcome": "killed", "output": "timeout"}),
    _line(2, {"worker_outcome": "normal", "test_outcome": "survived", "output": "."}),
    _line(3, {"worker_outcome": "normal", "test_outcome": "incompetent", "output": "Traceback"}),
    _line(4, {"worker_outcome": "no-test", "test_outcome": None, "output": None}),
    _line(5, {"worker_outcome": "exception", "test_outcome": None, "output": "boom"}),
    _line(6, None),
]) + "\n"


def test_each_cosmic_ray_outcome_keeps_its_meaning():
    mutants = cosmic_ray_dump(DUMP)
    assert [m.status for m in mutants] == [S.KILLED, S.TIMEOUT, S.SURVIVED, S.ERROR, S.NO_COVERAGE, S.ERROR, S.UNKNOWN]
    assert mutants[0].mutant_id == "pkg/calc.py:core/ReplaceBinaryOperator_Add_Mul:0" and mutants[0].line == 2
    assert not any(m.killed_by for m in mutants)  # the tool names no killing test


def test_an_imported_dump_is_evidence_but_never_tied_to_a_state(tmp_path):
    report = write(tmp_path / "dump.jsonl", DUMP)
    run = load_mutation_report(report)
    assert run.error is None and run.tool == "Cosmic Ray" and run.count(S.SURVIVED) == 1 and run.count(S.UNKNOWN) == 1
    attached = attach_mutation(StateEvidence("current", "copy"), run, tmp_path)
    assert attached.matches_state is None and not attached.orchestrated


def test_targets_outside_the_project_or_not_python_are_refused_before_anything_runs(tmp_path):
    write(tmp_path / "calc.py", "def add(a, b):\n    return a + b\n")
    write(tmp_path / "notes.txt", "x")
    for targets in ([], ["../calc.py"], ["notes.txt"], [str(tmp_path / "calc.py")], ["missing.py"]):
        run = cosmic_ray.run(tmp_path, sys.executable, targets, test_paths=[])
        assert run.error and "mutation targets" in run.error and not run.mutants, targets


def test_a_missing_tool_is_blocked_with_the_reason_never_installed(tmp_path, monkeypatch):
    write(tmp_path / "calc.py", "def add(a, b):\n    return a + b\n")
    monkeypatch.setattr(cosmic_ray, "module_available", lambda python, module: False)
    run = cosmic_ray.run(tmp_path, sys.executable, ["calc.py"], test_paths=[])
    assert "not installed" in run.error and "does not install" in run.error


def test_a_project_no_integrated_tool_runs_gets_an_explained_error(tmp_path):
    write(tmp_path / "package.json", '{"devDependencies": {"vitest": "5.0.3"}}')
    write(tmp_path / "src" / "a.test.js", "test('a', () => {})\n")
    run = run_mutation_tool(tmp_path, sys.executable, ["src/a.js"])
    assert run.error and "no integrated mutation tool" in run.error


def _state(label, statuses, *, tied=True, orchestrated=True, controls=()):
    from assertiva.models import MutantRecord, MutationRun

    run = MutationRun(source="run", tool="Cosmic Ray", orchestrated=orchestrated, targets=("calc.py",), matches_state=True if tied else None,
                      mutants=[MutantRecord(mutant_id=f"calc.py:op:{i}", status=s, native_status=s.value, path="calc.py", line=2)
                               for i, s in enumerate(statuses)])
    state = StateEvidence(label, "copy")
    state.mutation, state.negative_controls = [run], list(controls)
    return state


def test_protection_compares_only_breaks_executed_and_tied_on_both_states():
    from assertiva.candidate import CandidateChangeKind, CandidateTestChange
    from assertiva.evidence import ControlOutcome, NegativeControlResult
    from assertiva.improve import protection_delta

    change = [CandidateTestChange(change_id="tests/test_calc.py", path="tests/test_calc.py", kind=CandidateChangeKind.MODIFY, reason="r")]
    before_controls = [NegativeControlResult("c1", "claim", ControlOutcome.SURVIVED, "tests stayed green")]
    after_controls = [NegativeControlResult("c1", "claim", ControlOutcome.KILLED, "detected by tests/test_calc.py::test_edge")]
    baseline = _state("baseline", [S.SURVIVED, S.KILLED, S.SURVIVED], controls=before_controls)
    candidate = _state("candidate", [S.KILLED, S.SURVIVED, S.SURVIVED], controls=after_controls)
    delta = protection_delta(baseline, candidate, before_controls, change)
    assert {e["id"] for e in delta["gained"]} == {"c1", "calc.py:op:0"}
    assert [e["id"] for e in delta["lost"]] == ["calc.py:op:1"] and [e["id"] for e in delta["still_undetected"]] == ["calc.py:op:2"]
    assert next(e for e in delta["gained"] if e["id"] == "c1")["detected_by"] == "tests/test_calc.py::test_edge"
    untied = protection_delta(_state("baseline", [S.SURVIVED], tied=False), _state("candidate", [S.KILLED]), [], change)
    assert untied["gained"] == [] and untied["not_compared"]  # an untied baseline proves no difference
    imported = protection_delta(_state("baseline", [S.SURVIVED], orchestrated=False), _state("candidate", [S.KILLED], orchestrated=False), [], change)
    assert imported["gained"] == [] and imported["compared"] == []
