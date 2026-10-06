"""Approved apply is all-or-nothing: no partial project state survives a failure."""

import pytest

from assertiva import workspace as ws
from assertiva.candidate import CandidateChangeKind
from assertiva.workspace import (
    ApplyFailedError,
    Approval,
    apply_changes,
    capture_baseline,
    change_set,
    create_workspace,
    remove_workspace,
    tree_fingerprint,
)

from conftest import write


@pytest.fixture
def prepared(calc_project):
    """Candidate with one ADD (in a new directory), one MODIFY and one RETIRE_CANDIDATE."""
    write(calc_project / "tests" / "test_old.py", "def test_old():\n    assert 1\n")
    baseline = capture_baseline(calc_project)
    workspace = create_workspace(baseline)
    write(workspace / "tests" / "unit" / "test_new.py", "def test_new():\n    assert 2\n")
    write(workspace / "calc.py", "def add(a, b):\n    return b + a\n")
    (workspace / "tests" / "test_old.py").unlink()
    changes = change_set(baseline, workspace)
    assert {c.kind for c in changes} == {CandidateChangeKind.ADD, CandidateChangeKind.MODIFY, CandidateChangeKind.RETIRE_CANDIDATE}
    yield calc_project, baseline, workspace, changes
    remove_workspace(baseline, workspace)


def approve_all(changes):
    return Approval(frozenset(c.change_id for c in changes), "reviewer")


def fail_on_call(monkeypatch, n):
    real, calls = ws._install, {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == n:
            raise OSError("disk full (injected)")
        return real(*args, **kwargs)

    monkeypatch.setattr(ws, "_install", flaky)


@pytest.mark.parametrize("failing_call", [1, 2, 3])
def test_apply_is_all_or_nothing(prepared, monkeypatch, failing_call):
    project, baseline, workspace, changes = prepared
    before = tree_fingerprint(project)
    fail_on_call(monkeypatch, failing_call)
    with pytest.raises(ApplyFailedError) as excinfo:
        apply_changes(project, baseline, workspace, changes, approve_all(changes))
    assert "rolled back" in str(excinfo.value)
    assert tree_fingerprint(project) == before  # including no staged temp files and no new directories
    assert not (project / "tests" / "unit").exists()


def test_retirement_is_transactional(prepared, monkeypatch):
    project, baseline, workspace, changes = prepared
    retire = next(c for c in changes if c.kind is CandidateChangeKind.RETIRE_CANDIDATE)
    fail_on_call(monkeypatch, 3)  # changes apply in sorted order; the retirement comes before the last one
    with pytest.raises(ApplyFailedError):
        apply_changes(project, baseline, workspace, changes, approve_all(changes))
    assert (project / retire.path).read_text(encoding="utf-8") == "def test_old():\n    assert 1\n"


def test_unapproved_changes_are_untouched(prepared):
    project, baseline, workspace, changes = prepared
    modify = next(c for c in changes if c.kind is CandidateChangeKind.MODIFY)
    applied = apply_changes(project, baseline, workspace, changes, Approval(frozenset({modify.change_id}), "reviewer"))
    assert [c.change_id for c in applied] == [modify.change_id]
    assert (project / "tests" / "test_old.py").exists()
    assert not (project / "tests" / "unit" / "test_new.py").exists()


def test_post_apply_fingerprint_matches_candidate(prepared, monkeypatch):
    project, baseline, workspace, changes = prepared
    before = tree_fingerprint(project)
    real_copy = ws.shutil.copy2

    def corrupting_copy(src, dst, *args, **kwargs):
        result = real_copy(src, dst, *args, **kwargs)
        if str(dst).endswith(".assertiva-staged"):
            with open(dst, "a", encoding="utf-8") as handle:
                handle.write("# corrupted in transit\n")
        return result

    monkeypatch.setattr(ws.shutil, "copy2", corrupting_copy)
    with pytest.raises(ApplyFailedError) as excinfo:
        apply_changes(project, baseline, workspace, changes, approve_all(changes))
    assert "does not match the candidate" in str(excinfo.value)
    assert tree_fingerprint(project) == before


def test_successful_apply_leaves_no_staging_files(prepared):
    project, baseline, workspace, changes = prepared
    apply_changes(project, baseline, workspace, changes, approve_all(changes))
    assert not [p for p in tree_fingerprint(project) if "assertiva-staged" in p]
    assert (project / "tests" / "unit" / "test_new.py").exists()
    assert not (project / "tests" / "test_old.py").exists()
