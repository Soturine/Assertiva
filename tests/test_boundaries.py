"""Project filesystem boundaries: links never smuggle outside content in or let writes escape."""

import os
import stat
import sys
from pathlib import Path

import pytest

from assertiva.candidate import CandidateChangeKind, CandidateTestChange
from assertiva.workspace import (
    Approval,
    PathBoundaryError,
    StaleBaselineError,
    apply_changes,
    boundary_report,
    capture_baseline,
    change_set,
    create_workspace,
    file_digest,
    project_files,
    remove_workspace,
    snapshot,
    tree_fingerprint,
)

from conftest import git, write


def link_dir(link: Path, target: Path) -> None:
    """Directory link without privileges: symlink where allowed, NTFS junction otherwise."""
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(target, link, target_is_directory=True)
    except OSError:
        import _winapi  # Windows only: junctions need no special privilege

        _winapi.CreateJunction(str(target), str(link))


@pytest.fixture
def outside(tmp_path):
    secret = tmp_path / "outside"
    write(secret / "secret.txt", "outside content\n")
    return secret


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    write(root / "app.py", "X = 1\n")
    write(root / "data" / "values.txt", "1 2 3\n")
    write(root / "tests" / "test_app.py", "def test_x():\n    assert 1\n")
    return root


def test_external_link_is_an_entry_not_its_content(project, outside):
    link_dir(project / "vendor", outside)
    files = project_files(project)
    assert "vendor" in files and "vendor/secret.txt" not in files
    before = tree_fingerprint(project)
    (outside / "secret.txt").write_text("changed outside\n")
    assert tree_fingerprint(project) == before  # outside content is not project material
    report = boundary_report(project)
    assert report["external_links"] == ["vendor"]


def test_snapshot_never_copies_external_content_as_project(project, outside):
    link_dir(project / "vendor", outside)
    copy = snapshot(project)
    vendor = copy / "vendor"
    assert not os.path.lexists(vendor) or _is_link(vendor)  # a link (same identity) or omitted...
    assert not (vendor / "secret.txt").is_file() or _is_link(vendor)  # ...never a regular copy of outside content


def _is_link(path: Path) -> bool:
    st = os.lstat(path)
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def test_internal_link_in_a_copy_points_into_the_copy_not_the_original(project):
    link_dir(project / "data_alias", project / "data")
    copy = snapshot(project)
    resolved = Path(os.path.realpath(copy / "data_alias"))
    assert resolved == Path(os.path.realpath(copy / "data"))  # rebased: writing through it cannot touch the original


def test_candidate_workspace_reproduces_links_exactly(project, outside):
    link_dir(project / "data_alias", project / "data")
    link_dir(project / "vendor", outside)
    baseline = capture_baseline(project)
    workspace = create_workspace(baseline)
    try:
        assert capture_baseline(workspace).files == baseline.files
    finally:
        remove_workspace(baseline, workspace)


def test_apply_refuses_a_candidate_link_escaping_the_project(project, outside):
    baseline = capture_baseline(project)
    workspace = create_workspace(baseline)
    try:
        link_dir(workspace / "escape", outside)
        changes = change_set(baseline, workspace)
        assert [c.path for c in changes] == ["escape"]
        with pytest.raises(PathBoundaryError):
            apply_changes(project, baseline, workspace, changes, Approval(frozenset({"escape"}), "reviewer"))
    finally:
        remove_workspace(baseline, workspace)
    assert not os.path.lexists(project / "escape")


def test_apply_refuses_writes_through_a_linked_directory(project, outside):
    link_dir(project / "vendor", outside)
    baseline = capture_baseline(project)
    forged = CandidateTestChange("vendor/secret.txt", "vendor/secret.txt", CandidateChangeKind.MODIFY, "forged",
                                 original_fingerprint=None, candidate_fingerprint="x")
    with pytest.raises(PathBoundaryError):
        apply_changes(project, baseline, project, [forged], Approval(frozenset({"vendor/secret.txt"}), "reviewer"))
    assert (outside / "secret.txt").read_text() == "outside content\n"


@pytest.mark.parametrize("bad", ["../outside.txt", "/etc/passwd", "C:/Windows/x.txt", "tests/../../x.txt"])
def test_apply_refuses_traversal_paths(project, bad):
    baseline = capture_baseline(project)
    forged = CandidateTestChange(bad, bad, CandidateChangeKind.ADD, "forged", candidate_fingerprint="x")
    with pytest.raises(PathBoundaryError):
        apply_changes(project, baseline, project, [forged], Approval(frozenset({bad}), "reviewer"))


def test_link_swapped_in_after_qualification_is_stale(project, outside):
    baseline = capture_baseline(project)
    workspace = create_workspace(baseline)
    try:
        write(workspace / "data" / "values.txt", "4 5 6\n")
        changes = change_set(baseline, workspace)
        import shutil

        shutil.rmtree(project / "data")
        link_dir(project / "data", outside)  # the reviewed directory is swapped for a link
        with pytest.raises((StaleBaselineError, PathBoundaryError)):
            apply_changes(project, baseline, workspace, changes, Approval(frozenset({"data/values.txt"}), "reviewer"))
    finally:
        remove_workspace(baseline, workspace)
    assert (outside / "secret.txt").read_text() == "outside content\n"
    assert not (outside / "values.txt").exists()


def test_case_only_collision_is_refused(project):
    baseline = capture_baseline(project)
    clash = CandidateTestChange("Tests/test_app.py", "Tests/test_app.py", CandidateChangeKind.ADD, "case clash", candidate_fingerprint="x")
    with pytest.raises(PathBoundaryError) as excinfo:
        apply_changes(project, baseline, project, [clash], Approval(frozenset({"Tests/test_app.py"}), "reviewer"))
    assert "case" in str(excinfo.value)


def test_nested_repository_content_is_included_and_reported(project):
    git(project, "init", "-q")
    nested = project / "libs" / "inner"
    write(nested / "inner.py", "Y = 2\n")
    git(nested, "init", "-q")
    files = project_files(project)
    assert "libs/inner/inner.py" in files and not any(".git/" in f for f in files)
    assert boundary_report(project)["nested_repositories"] == ["libs/inner"]


def test_executable_bit_is_part_of_the_digest_where_the_filesystem_has_one(project):
    target = project / "app.py"
    before = file_digest(target)
    target.chmod(target.stat().st_mode | stat.S_IXUSR)
    executable_bits = os.name != "nt"
    assert (file_digest(target) != before) is executable_bits


def test_audit_reports_links_escaping_the_project(project, outside):
    from assertiva.audit import run_audit

    link_dir(project / "vendor", outside)
    report = run_audit(project)
    finding = next(f for f in report["findings"] if f["code"] == "PROJECT_LINK_ESCAPES_ROOT")
    assert finding["evidence"]["links"] == ["vendor"]


@pytest.mark.integration
def test_cleaning_up_execution_copies_never_deletes_through_links(project, outside):
    from assertiva.evidence import measure

    link_dir(project / "vendor", outside)
    state = measure(project, "current", "isolated-project-copy", sys.executable)
    assert (outside / "secret.txt").read_text() == "outside content\n"
    assert any("outside its root" in item for item in state.limitations)
