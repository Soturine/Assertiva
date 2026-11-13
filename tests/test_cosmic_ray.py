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


def _junction_or_symlink(target, link):
    """A directory link the current user can create: a junction on Windows, a symlink elsewhere."""
    import os

    if os.name == "nt":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def test_a_target_reached_through_a_link_is_refused_before_anything_runs(tmp_path, monkeypatch):
    # 0.8.0 reproduction: a target under a directory junction to outside the project was rewritten 16 times by the
    # tool during one run (restored only because the tool restores files after each mutant)
    outside = tmp_path / "outside"
    write(outside / "calc.py", "def add(a, b):\n    return a + b\n")
    write(outside / "deep" / "more.py", "x = 1\n")
    project = tmp_path / "project"
    write(project / "pkg" / "own.py", "y = 2\n")
    _junction_or_symlink(outside, project / "lib")
    _junction_or_symlink(outside / "deep", project / "pkg" / "deep")
    ran = []
    monkeypatch.setattr(cosmic_ray, "run_command", lambda *a, **k: ran.append(a))
    for target in ("lib/calc.py", "pkg/deep/more.py"):
        result = cosmic_ray.run(project, sys.executable, [target], test_paths=[])
        assert result.error and "is a link" in result.error and not result.mutants, target
    assert ran == []  # refused before the suite, the planner or the tool ran
    assert cosmic_ray.unsafe_target(project, "pkg/own.py") is None


def test_a_link_that_appears_only_in_the_copy_is_refused_too(tmp_path, monkeypatch):
    write(tmp_path / "project" / "calc.py", "def add(a, b):\n    return a + b\n")
    monkeypatch.setattr(cosmic_ray, "module_available", lambda python, module: True)
    real = cosmic_ray.unsafe_target
    calls = []

    def copy_is_linked(root, target):
        calls.append(root)
        return real(root, target) if len(calls) == 1 else "calc.py is a link: a write through it can reach outside the copy"

    monkeypatch.setattr(cosmic_ray, "unsafe_target", copy_is_linked)
    monkeypatch.setattr(cosmic_ray, "run_command", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    result = cosmic_ray.run(tmp_path / "project", sys.executable, ["calc.py"], test_paths=[])
    assert "not plain files in the copy" in result.error


def test_suite_level_detection_never_names_changed_files_as_detectors_and_unequal_code_is_not_compared():
    from assertiva.candidate import CandidateChangeKind, CandidateTestChange
    from assertiva.improve import protection_delta

    change = [CandidateTestChange(change_id="tests/test_calc.py", path="tests/test_calc.py", kind=CandidateChangeKind.MODIFY, reason="r")]
    baseline, candidate = _state("baseline", [S.SURVIVED, S.SURVIVED]), _state("candidate", [S.KILLED, S.ERROR])
    delta = protection_delta(baseline, candidate, [], change)
    [gain] = delta["gained"]
    assert gain["attribution"] == "SUITE" and "detected_by" not in gain and gain["changed_files"] == ["tests/test_calc.py"]
    assert [e["id"] for e in delta["not_comparable"]] == ["calc.py:op:1"]  # an error is not a detection or a miss
    baseline.mutation[0].sources, candidate.mutation[0].sources = {"calc.py": "a"}, {"calc.py": "b"}
    shifted = protection_delta(baseline, candidate, [], change)
    assert shifted["gained"] == [] and "mutated code differs" in shifted["not_compared"][0]


def test_an_executed_run_with_errored_mutants_does_not_pass_globally():
    from assertiva.candidate import StageStatus
    from assertiva.improve import _mutation_stage

    candidate = _state("candidate", [S.KILLED] + [S.ERROR] * 20)
    candidate.mutation[0].counts = {"KILLED": 1, "ERROR": 20}
    result = _mutation_stage(candidate)
    assert result.status is StageStatus.UNKNOWN and "ended in error" in result.summary  # 0.8.0: PASS, "all 1 evaluated"


def test_the_inputs_digest_changes_with_the_mutated_code_or_the_tests():
    from assertiva.models import MutationRun

    a = MutationRun(source="r", sources={"calc.py": "x"}, test_sources={"tests/t.py": "y"})
    assert a.inputs_digest == MutationRun(source="other", sources={"calc.py": "x"}, test_sources={"tests/t.py": "y"}).inputs_digest
    assert a.inputs_digest != MutationRun(source="r", sources={"calc.py": "x"}, test_sources={"tests/t.py": "z"}).inputs_digest
    assert MutationRun(source="r").inputs_digest is None


def test_mutants_are_compared_by_a_stable_identity_and_collisions_are_not_guessed():
    from assertiva.candidate import CandidateChangeKind, CandidateTestChange
    from assertiva.improve import protection_delta

    change = [CandidateTestChange(change_id="t.js", path="t.js", kind=CandidateChangeKind.MODIFY, reason="r")]
    baseline, candidate = _state("baseline", [S.SURVIVED, S.SURVIVED]), _state("candidate", [S.KILLED, S.KILLED])
    # the tool numbers mutants per run: the same two mutants come back with swapped numbers
    for m, number, ident in zip(baseline.mutation[0].mutants, ("0", "1"), ("a.js:3:5:op:x", "a.js:7:1:op:y")):
        object.__setattr__(m, "mutant_id", number); object.__setattr__(m, "stable_id", ident)
    for m, number, ident in zip(candidate.mutation[0].mutants, ("1", "0"), ("a.js:3:5:op:x", "a.js:7:1:op:y")):
        object.__setattr__(m, "mutant_id", number); object.__setattr__(m, "stable_id", ident)
    object.__setattr__(candidate.mutation[0].mutants[0], "killed_by", ("7",))
    candidate.mutation[0].test_names, candidate.mutation[0].test_locations = {"7": "the threshold is inclusive"}, {"7": "src/p.test.js"}
    delta = protection_delta(baseline, candidate, [], change)
    assert {e["id"] for e in delta["gained"]} == {"a.js:3:5:op:x", "a.js:7:1:op:y"}
    named = next(e for e in delta["gained"] if e["id"] == "a.js:3:5:op:x")
    assert named["attribution"] == "TEST" and named["detected_by"] == "the threshold is inclusive (src/p.test.js)"
    object.__setattr__(candidate.mutation[0].mutants[1], "stable_id", "a.js:3:5:op:x")  # a collision
    collided = protection_delta(baseline, candidate, [], change)
    assert collided["gained"] == [] and all(e["reason"] == "its identity is not unique in the run" for e in collided["not_comparable"])


def test_a_tied_runs_survivors_show_the_original_line_and_the_change():
    from assertiva.models import MutantRecord, MutationRun
    from assertiva.report import survivor_sites

    run = MutationRun(source="x", sources={"calc.py": "def add(a, b):\n    return a + b\n"}, matches_state=True,
                      mutants=[MutantRecord("m", S.SURVIVED, "Survived", path="calc.py", line=2, operator="ArithmeticOperator",
                                            replacement="a - b")])
    [site] = survivor_sites(run)
    assert site["original"] == "return a + b" and site["change"] == "a - b"
    run.matches_state = None  # an untied report: its lines may not be this state's
    assert survivor_sites(run) == []


# --- AXF-VN-01 (VozNativa v0.5/v0.7 dogfood): --mutate-tests with a unittest file ---------------------------------

def _unittest_project(root):
    write(root / "calc.py", "def add(a, b):\n    return a + b\n")
    write(root / "tests" / "test_calc.py", "import unittest\nfrom calc import add\n\n"
                                            "class T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")
    write(root / "tests" / "test_other.py", "import unittest\n\nclass U(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(True)\n")


def _run(argv, cwd):
    import subprocess

    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)


def test_a_selected_unittest_file_becomes_a_module_name_that_runs(tmp_path):
    _unittest_project(tmp_path)
    command = cosmic_ray.test_command_for(sys.executable, "unittest", ["tests/test_calc.py"], tmp_path)
    assert command[1:] == ["-m", "unittest", "--failfast", "tests.test_calc"]
    done = _run(command, tmp_path)
    assert done.returncode == 0 and "Ran 1 test" in done.stderr


def test_negative_control_the_old_command_cannot_start(tmp_path):
    _unittest_project(tmp_path)
    old = [sys.executable, "-m", "unittest", "discover", "--failfast", "tests/test_calc.py"]
    done = _run(old, tmp_path)
    assert done.returncode != 0 and "not importable" in done.stderr


def test_a_selected_unittest_directory_is_discovered_from_the_project_root(tmp_path):
    _unittest_project(tmp_path)
    command = cosmic_ray.test_command_for(sys.executable, "unittest", ["tests"], tmp_path)
    assert command[-2:] == ["-s", "tests"]
    done = _run(command, tmp_path)
    assert done.returncode == 0 and "Ran 2 tests" in done.stderr
    write(tmp_path / "tests" / "__init__.py", "")           # a package keeps the project root as top level
    command = cosmic_ray.test_command_for(sys.executable, "unittest", ["tests"], tmp_path)
    assert command[-4:] == ["-s", "tests", "-t", "."]
    done = _run(command, tmp_path)
    assert done.returncode == 0 and "Ran 2 tests" in done.stderr


def test_files_and_directories_are_not_mixed_and_paths_stay_inside(tmp_path):
    import pytest

    _unittest_project(tmp_path)
    for selection in (["tests", "tests/test_calc.py"], ["../x/test_y.py"]):
        with pytest.raises(ValueError):
            cosmic_ray.test_command_for(sys.executable, "unittest", selection, tmp_path)


def test_other_runners_and_no_selection_keep_their_commands(tmp_path):
    assert cosmic_ray.test_command_for("py", "pytest-native", ["tests/test_a.py"])[-1] == "tests/test_a.py"
    assert cosmic_ray.test_command_for("py", "unittest", []) == ["py", "-m", "unittest", "discover", "--failfast"]


# --- AXF-VN-01 qualification (v1.0): layouts, refusals, empty selections and the finding's label ----------------------

_CASE = ("import unittest\nfrom calc import add\n\nclass T(unittest.TestCase):\n"
         "    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")


def test_layouts_a_selected_file_runs_from_as_a_module(tmp_path):
    """Root file, nested folders without any __init__.py (namespace packages), and a package only at the leaf."""
    import pytest

    write(tmp_path / "calc.py", "def add(a, b):\n    return a + b\n")
    write(tmp_path / "test_root.py", _CASE)
    write(tmp_path / "tests" / "unit" / "test_deep.py", _CASE)
    write(tmp_path / "suite" / "inner" / "__init__.py", "")
    write(tmp_path / "suite" / "inner" / "test_leaf.py", _CASE)
    for selected, module in (("test_root.py", "test_root"), ("tests/unit/test_deep.py", "tests.unit.test_deep"),
                             ("suite/inner/test_leaf.py", "suite.inner.test_leaf")):
        command = cosmic_ray.test_command_for(sys.executable, "unittest", [selected], tmp_path)
        assert command[-1] == module
        done = _run(command, tmp_path)
        assert done.returncode == 0 and "Ran 1 test" in done.stderr, (selected, done.stderr)
    both = cosmic_ray.test_command_for(sys.executable, "unittest", ["test_root.py", "tests/unit/test_deep.py"], tmp_path)
    done = _run(both, tmp_path)
    assert both[-2:] == ["test_root", "tests.unit.test_deep"] and "Ran 2 tests" in done.stderr
    assert cosmic_ray.tests_ran("unittest", done) == 2
    for refused in (["tests/my-tests/test_x.py"], ["tests/test_calc.txt"], ["/abs/test_x.py"], ["C:/abs/test_x.py"],
                    ["tests", "suite"]):
        with pytest.raises(ValueError):
            cosmic_ray.test_command_for(sys.executable, "unittest", refused, tmp_path)


class _Done:
    def __init__(self, returncode, stderr="", stdout=""):
        self.returncode, self.stderr, self.stdout = returncode, stderr, stdout


def test_an_empty_selection_is_counted_not_trusted():
    """Python 3.11's unittest exits 0 after "Ran 0 tests" (3.12+ exits 5): the count, not the exit code, decides."""
    assert cosmic_ray.tests_ran("unittest", _Done(0, "\n----\nRan 0 tests in 0.000s\n\nOK\n")) == 0
    assert cosmic_ray.tests_ran("unittest", _Done(5, "\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n")) == 0
    assert cosmic_ray.tests_ran("django", _Done(0, "Ran 3 tests in 0.1s\n")) == 3
    assert cosmic_ray.tests_ran("pytest-native", _Done(5)) == 0
    assert cosmic_ray.tests_ran("pytest-native", _Done(0, stdout="1 passed")) is None  # no count: exit code only
    assert cosmic_ray.tests_ran("unittest", _Done(0, "nothing printed")) is None


def test_a_run_that_stopped_is_not_an_unreadable_report():
    from assertiva.audit import _mutation_findings
    from assertiva.models import MutationRun

    state = StateEvidence(label="current", observed_in="copy")
    state.mutation = [MutationRun(source="Cosmic Ray run by Assertiva on calc.py", tool="Cosmic Ray", orchestrated=True,
                                  targets=("calc.py",), error="the selected tests ran no test on this state", stage="selection"),
                      MutationRun(source="m.json", error="ValueError: unsupported mutation report format")]
    codes = [(f.code, f.evidence.get("stage")) for f in _mutation_findings(state)]
    assert codes == [("MUTATION_RUN_NOT_COMPLETED", "selection"), ("MUTATION_REPORT_UNREADABLE", None)]
