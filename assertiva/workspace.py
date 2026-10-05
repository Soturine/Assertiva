"""Project isolation: baselines, candidate workspaces, change sets and approved application.

Everything that executes project code or edits candidate files happens outside the
original project. The original is written only by ``apply_changes`` and only for an
explicitly approved, non-stale change set.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .candidate import CandidateChangeKind, CandidateTestChange


class ProjectModifiedError(RuntimeError):
    def __init__(self, paths: list[str]):
        self.paths = paths
        super().__init__(f"read-only project was modified: {', '.join(paths[:10])}")


class ApprovalRequiredError(PermissionError):
    pass


class StaleBaselineError(RuntimeError):
    def __init__(self, paths: list[str]):
        self.paths = paths
        super().__init__(
            "project or candidate changed since the candidate was qualified; refusing to overwrite: "
            + ", ".join(paths)
        )


def assertiva_home() -> Path:
    """Assertiva-owned state/report storage, outside audited projects by default."""
    configured = os.environ.get("ASSERTIVA_HOME")
    return Path(configured).resolve() if configured else (Path.home() / ".assertiva").resolve()


def state_dir(root: str | Path, kind: str) -> Path:
    root = Path(root).resolve()
    home = assertiva_home()
    if home == root or home.is_relative_to(root):
        raise ValueError(f"ASSERTIVA_HOME ({home}) must be outside the project ({root})")
    key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
    return home / kind / f"{root.name}-{key}"


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def tree_fingerprint(root: str | Path) -> dict[str, str]:
    """Strict fingerprint of every file below ``root`` except Git metadata.

    Includes ignored files and caches on purpose: a read-only run must not create them.
    """
    root = Path(root)
    return {
        _rel(path, root): file_digest(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


@contextmanager
def read_only_guard(root: str | Path) -> Iterator[None]:
    before = tree_fingerprint(root)
    yield
    after = tree_fingerprint(root)
    if after != before:
        changed = sorted(p for p in set(before) | set(after) if before.get(p) != after.get(p))
        raise ProjectModifiedError(changed)


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def _git_toplevel(root: Path) -> Path | None:
    out = _git(root, "rev-parse", "--show-toplevel")
    return Path(out.strip()).resolve() if out else None


def project_files(root: str | Path) -> list[str]:
    """Files that make up the project: Git tracked + untracked-not-ignored, else every file."""
    root = Path(root)
    listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed is not None and _git_toplevel(root) is not None:
        return sorted({p for p in listed.split("\0") if p and (root / p).is_file()})
    return sorted(tree_fingerprint(root))


@dataclass(frozen=True)
class Baseline:
    root: str
    revision: str | None
    dirty: bool | None
    files: dict[str, str]

    @property
    def digest(self) -> str:
        h = hashlib.sha256()
        for path, digest in sorted(self.files.items()):
            h.update(f"{path}\0{digest}\n".encode())
        return h.hexdigest()


def capture_baseline(root: str | Path) -> Baseline:
    root = Path(root).resolve()
    files = {path: file_digest(root / path) for path in project_files(root)}
    revision = _git(root, "rev-parse", "HEAD")
    status = _git(root, "status", "--porcelain", "--untracked-files=normal") if revision else None
    return Baseline(
        root=str(root),
        revision=revision.strip() if revision else None,
        dirty=bool(status.strip()) if status is not None else None,
        files=files,
    )


def _copy_files(source: Path, target: Path, files: list[str]) -> None:
    for rel in files:
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, destination)


def create_workspace(baseline: Baseline, *, prefer_worktree: bool = True) -> Path:
    """Create an isolated copy of the exact baseline outside the project.

    A detached Git worktree is used for a clean repository root; otherwise the baseline
    files are copied. Either way the result is verified against the baseline fingerprint.
    """
    root = Path(baseline.root)
    workspace = Path(tempfile.mkdtemp(prefix="assertiva-candidate-")).resolve()
    use_worktree = (
        prefer_worktree
        and baseline.revision is not None
        and baseline.dirty is False
        and _git_toplevel(root) == root
    )
    if use_worktree:
        workspace.rmdir()
        if _git(root, "worktree", "add", "--detach", "--quiet", str(workspace), baseline.revision) is None:
            use_worktree = False
            workspace.mkdir()
    if not use_worktree:
        _copy_files(root, workspace, sorted(baseline.files))

    observed = {path: file_digest(workspace / path) for path in project_files(workspace)}
    if observed != baseline.files:
        remove_workspace(baseline, workspace)
        if use_worktree:
            return create_workspace(baseline, prefer_worktree=False)
        raise RuntimeError("candidate workspace does not match the baseline fingerprint")
    return workspace


def snapshot(source: str | Path, target: str | Path | None = None) -> Path:
    """Copy of a project or workspace's project files; a disposable temp dir by default."""
    source = Path(source)
    target = Path(target) if target else Path(tempfile.mkdtemp(prefix="assertiva-run-"))
    target.mkdir(parents=True, exist_ok=True)
    _copy_files(source, target, project_files(source))
    return target.resolve()


def remove_workspace(baseline: Baseline | None, workspace: str | Path) -> None:
    workspace = Path(workspace)
    if baseline is not None and (workspace / ".git").is_file():
        _git(Path(baseline.root), "worktree", "remove", "--force", str(workspace))
        _git(Path(baseline.root), "worktree", "prune")
    shutil.rmtree(workspace, ignore_errors=True)


def _ignored_by_project(baseline: Baseline, paths: list[str]) -> set[str]:
    """Paths the original project's ignore rules exclude (caches, build output...)."""
    root = Path(baseline.root)
    if not paths or _git_toplevel(root) is None:
        return set()
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-z", "--stdin"],
            cwd=root,
            input="\0".join(paths),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return set()
    return {p for p in result.stdout.split("\0") if p}


def change_set(baseline: Baseline, workspace: str | Path) -> list[CandidateTestChange]:
    """Diff the candidate workspace against the immutable baseline."""
    workspace = Path(workspace)
    listed = [p for p in project_files(workspace) if p not in baseline.files]
    ignored = _ignored_by_project(baseline, listed)
    candidate = {
        path: file_digest(workspace / path)
        for path in project_files(workspace)
        if path not in ignored
    }
    changes: list[CandidateTestChange] = []
    for path in sorted(set(baseline.files) | set(candidate)):
        before, after = baseline.files.get(path), candidate.get(path)
        if before == after:
            continue
        if before is None:
            kind, reason = CandidateChangeKind.ADD, "added in candidate"
        elif after is None:
            kind, reason = CandidateChangeKind.RETIRE_CANDIDATE, "removed in candidate; original stays until approved"
        else:
            kind, reason = CandidateChangeKind.MODIFY, "modified in candidate"
        changes.append(
            CandidateTestChange(
                change_id=path,
                path=path,
                kind=kind,
                reason=reason,
                original_fingerprint=before,
                candidate_fingerprint=after,
            )
        )
    return changes


@dataclass(frozen=True)
class Approval:
    """Explicit human approval of specific change ids. There is no approve-everything default."""

    change_ids: frozenset[str]
    approved_by: str


def _current(path: Path) -> str | None:
    return file_digest(path) if path.is_file() else None


def apply_changes(
    project_root: str | Path,
    baseline: Baseline,
    workspace: str | Path,
    changes: list[CandidateTestChange],
    approval: Approval | None,
) -> list[CandidateTestChange]:
    project_root, workspace = Path(project_root), Path(workspace)
    if approval is None or not approval.change_ids:
        raise ApprovalRequiredError("explicit human approval of specific changes is required")
    by_id = {change.change_id: change for change in changes}
    unknown = sorted(approval.change_ids - set(by_id))
    if unknown:
        raise ValueError(f"approval references unknown changes: {', '.join(unknown)}")
    if Path(baseline.root) != project_root.resolve():
        raise ValueError("baseline belongs to a different project")

    approved = [by_id[change_id] for change_id in sorted(approval.change_ids)]
    stale = sorted(
        change.path
        for change in approved
        if _current(project_root / change.path) != change.original_fingerprint
        or _current(workspace / change.path) != change.candidate_fingerprint
    )
    if stale:
        raise StaleBaselineError(stale)

    for change in approved:
        target = project_root / change.path
        if change.kind is CandidateChangeKind.RETIRE_CANDIDATE:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / change.path, target)
    return approved
