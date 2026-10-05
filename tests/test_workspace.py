import pytest

from assertiva.candidate import CandidateChangeKind
from assertiva.workspace import (
    ApprovalRequiredError,
    ProjectModifiedError,
    StaleBaselineError,
    Approval,
    apply_changes,
    capture_baseline,
    change_set,
    create_workspace,
    read_only_guard,
    remove_workspace,
    tree_fingerprint,
)

from conftest import write


def test_tree_fingerprint_detects_any_file_change_outside_git_metadata(calc_project):
    before = tree_fingerprint(calc_project)
    write(calc_project / ".pytest_cache" / "v" / "x", "cache")
    assert tree_fingerprint(calc_project) != before


def test_read_only_guard_raises_when_project_is_modified(calc_project):
    with pytest.raises(ProjectModifiedError) as excinfo:
        with read_only_guard(calc_project):
            write(calc_project / "stray.txt", "oops")
    assert "stray.txt" in excinfo.value.paths


@pytest.mark.parametrize("project", ["calc_project", "git_calc_project"])
def test_candidate_uses_exact_baseline(project, request):
    root = request.getfixturevalue(project)
    baseline = capture_baseline(root)
    workspace = create_workspace(baseline)
    try:
        assert capture_baseline(workspace).files == baseline.files
        assert not workspace.resolve().is_relative_to(root.resolve())
    finally:
        remove_workspace(baseline, workspace)


def test_dirty_git_baseline_includes_uncommitted_work(git_calc_project):
    write(git_calc_project / "calc.py", "def add(a, b):\n    return b + a\n")
    write(git_calc_project / "notes_untracked.py", "X = 1\n")
    baseline = capture_baseline(git_calc_project)
    assert baseline.dirty is True
    workspace = create_workspace(baseline)
    try:
        assert capture_baseline(workspace).files == baseline.files
    finally:
        remove_workspace(baseline, workspace)


def test_candidate_changes_only_isolated_workspace(git_calc_project):
    original = tree_fingerprint(git_calc_project)
    baseline = capture_baseline(git_calc_project)
    workspace = create_workspace(baseline)
    try:
        write(workspace / "tests" / "test_new.py", "def test_new():\n    assert 1 + 1 == 2\n")
        (workspace / "calc.py").write_text("def add(a, b):\n    return a + b  # edited\n", encoding="utf-8")
        changes = change_set(baseline, workspace)
    finally:
        remove_workspace(baseline, workspace)
    assert tree_fingerprint(git_calc_project) == original
    assert {(c.path, c.kind) for c in changes} == {
        ("tests/test_new.py", CandidateChangeKind.ADD),
        ("calc.py", CandidateChangeKind.MODIFY),
    }


def test_retirement_candidate_preserves_original(calc_project):
    baseline = capture_baseline(calc_project)
    workspace = create_workspace(baseline)
    try:
        (workspace / "tests" / "test_calc.py").unlink()
        changes = change_set(baseline, workspace)
    finally:
        remove_workspace(baseline, workspace)
    [retire] = changes
    assert retire.kind is CandidateChangeKind.RETIRE_CANDIDATE
    assert retire.original_preserved
    assert retire.original_fingerprint == baseline.files["tests/test_calc.py"]
    assert (calc_project / "tests" / "test_calc.py").exists()


def test_apply_requires_explicit_human_approval(calc_project):
    baseline = capture_baseline(calc_project)
    workspace = create_workspace(baseline)
    try:
        write(workspace / "tests" / "test_new.py", "def test_new():\n    assert 1 + 1 == 2\n")
        changes = change_set(baseline, workspace)
        with pytest.raises(ApprovalRequiredError):
            apply_changes(calc_project, baseline, workspace, changes, approval=None)
        with pytest.raises(ApprovalRequiredError):
            apply_changes(calc_project, baseline, workspace, changes, Approval(frozenset(), "reviewer"))
    finally:
        remove_workspace(baseline, workspace)
    assert not (calc_project / "tests" / "test_new.py").exists()


def test_retirement_never_applies_without_approval(calc_project):
    baseline = capture_baseline(calc_project)
    workspace = create_workspace(baseline)
    try:
        write(workspace / "tests" / "test_new.py", "def test_new():\n    assert 1 + 1 == 2\n")
        (workspace / "tests" / "test_calc.py").unlink()
        changes = change_set(baseline, workspace)
        add = next(c for c in changes if c.kind is CandidateChangeKind.ADD)
        applied = apply_changes(calc_project, baseline, workspace, changes, Approval(frozenset({add.change_id}), "reviewer"))
    finally:
        remove_workspace(baseline, workspace)
    assert [c.change_id for c in applied] == [add.change_id]
    assert (calc_project / "tests" / "test_new.py").exists()
    assert (calc_project / "tests" / "test_calc.py").exists()


def test_approved_retirement_is_applied(calc_project):
    baseline = capture_baseline(calc_project)
    workspace = create_workspace(baseline)
    try:
        (workspace / "tests" / "test_calc.py").unlink()
        changes = change_set(baseline, workspace)
        apply_changes(calc_project, baseline, workspace, changes, Approval(frozenset({changes[0].change_id}), "reviewer"))
    finally:
        remove_workspace(baseline, workspace)
    assert not (calc_project / "tests" / "test_calc.py").exists()


def test_stale_baseline_refuses_apply(calc_project):
    baseline = capture_baseline(calc_project)
    workspace = create_workspace(baseline)
    try:
        (workspace / "tests" / "test_calc.py").write_text("def test_x():\n    assert 3 == 3\n", encoding="utf-8")
        write(workspace / "tests" / "test_new.py", "def test_new():\n    assert 1 + 1 == 2\n")
        changes = change_set(baseline, workspace)
        user_edit = "def test_user():\n    assert 'user' == 'user'\n"
        (calc_project / "tests" / "test_calc.py").write_text(user_edit, encoding="utf-8")
        approval = Approval(frozenset(c.change_id for c in changes), "reviewer")
        with pytest.raises(StaleBaselineError) as excinfo:
            apply_changes(calc_project, baseline, workspace, changes, approval)
    finally:
        remove_workspace(baseline, workspace)
    assert "tests/test_calc.py" in excinfo.value.paths
    # Refusal is atomic: no approved change was partially applied.
    assert (calc_project / "tests" / "test_calc.py").read_text(encoding="utf-8") == user_edit
    assert not (calc_project / "tests" / "test_new.py").exists()


def test_candidate_edited_after_qualification_refuses_apply(calc_project):
    baseline = capture_baseline(calc_project)
    workspace = create_workspace(baseline)
    try:
        write(workspace / "tests" / "test_new.py", "def test_new():\n    assert 1 + 1 == 2\n")
        changes = change_set(baseline, workspace)
        write(workspace / "tests" / "test_new.py", "def test_new():\n    pass\n")
        with pytest.raises(StaleBaselineError):
            apply_changes(calc_project, baseline, workspace, changes, Approval(frozenset({changes[0].change_id}), "reviewer"))
    finally:
        remove_workspace(baseline, workspace)
    assert not (calc_project / "tests" / "test_new.py").exists()


def test_git_worktree_is_cleaned_up(git_calc_project):
    from conftest import git

    def worktrees():
        listing = git(git_calc_project, "worktree", "list", "--porcelain")
        return {line.split(" ", 1)[1] for line in listing.splitlines() if line.startswith("worktree ")}

    baseline = capture_baseline(git_calc_project)
    workspace = create_workspace(baseline)
    try:
        assert workspace.as_posix() in worktrees()
    finally:
        remove_workspace(baseline, workspace)
    assert not workspace.exists()
    assert workspace.as_posix() not in worktrees()
