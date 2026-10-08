"""Project isolation: baselines, candidate workspaces, change sets and approved application.

Everything that executes project code or edits candidate files happens outside the
original project. The original is written only by ``apply_changes`` and only for an
explicitly approved, non-stale change set.

Filesystem boundary rules: links (symlinks, junctions) are project entries identified by
their target, never followed; content outside the project root is never copied in as if
it were project material; writes never go through a linked directory or out of the root.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterator

from .candidate import CandidateChangeKind, CandidateTestChange

_REPARSE_POINT = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT


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


class PathBoundaryError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("refusing to cross the project boundary: " + "; ".join(problems))


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


# --- links ---------------------------------------------------------------------------

def _link_target(path: Path) -> str | None:
    try:
        target = os.readlink(path)
    except (OSError, ValueError):
        return None
    return target[4:] if target.startswith("\\\\?\\") else target


def is_link(path: Path) -> bool:
    """Symlink or junction/mount-point reparse point (a link we can read the target of)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT) and _link_target(path) is not None


def _real(path: Path) -> Path:
    return Path(os.path.realpath(path))


def _inside(root: Path, path: Path) -> str | None:
    """Relative POSIX path of ``path`` (already resolved) inside ``root``, or None."""
    try:
        rel = path.relative_to(_real(root))
    except ValueError:
        return None
    return rel.as_posix()


def _link_identity(root: Path, link: Path) -> tuple[str, str]:
    """('internal', target relative to root) or ('external', absolute target)."""
    resolved = _real(link)
    rel = _inside(root, resolved)
    return ("internal", rel) if rel is not None else ("external", resolved.as_posix())


def file_digest(path: Path) -> str:
    """Content digest of a regular file; the executable bit counts where filesystems have one."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if os.name != "nt" and os.stat(path).st_mode & stat.S_IXUSR:
        digest += ":x"
    return digest


def entry_digest(root: Path, rel: str) -> str | None:
    """Digest of a project entry: file content, or a link's identity (never its target's content)."""
    path = Path(root) / rel
    if is_link(path):
        kind, target = _link_identity(Path(root), path)
        return f"link:{kind}:{target}"
    return file_digest(path) if path.is_file() else None


# --- listing -------------------------------------------------------------------------

@dataclass
class _Listing:
    files: list[str] = field(default_factory=list)
    nested: list[str] = field(default_factory=list)


def _walk(root: Path, base: Path, listing: _Listing) -> None:
    try:
        entries = sorted(os.scandir(base), key=lambda e: e.name)
    except OSError:
        return
    for entry in entries:
        if entry.name == ".git":
            continue
        path = Path(entry.path)
        rel = path.relative_to(root).as_posix()
        if is_link(path):
            listing.files.append(rel)
        elif entry.is_dir(follow_symlinks=False):
            if os.path.lexists(path / ".git"):
                listing.nested.append(rel)
            _walk(root, path, listing)
        elif entry.is_file(follow_symlinks=False):
            listing.files.append(rel)


def _listing(root: Path) -> _Listing:
    root = Path(root)
    listing = _Listing()
    listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if listed is None or _git_toplevel(root) is None:
        _walk(root, root, listing)
    else:
        links: dict[str, bool] = {}

        def linked_ancestor(rel: str) -> str | None:
            # Git on Windows lists files *through* a junction; the project entry is the link itself.
            parts = rel.split("/")
            for i in range(1, len(parts)):
                prefix = "/".join(parts[:i])
                if prefix not in links:
                    links[prefix] = is_link(root / prefix)
                if links[prefix]:
                    return prefix
            return None

        for rel in sorted({p.rstrip("/") for p in listed.split("\0") if p}):
            ancestor = linked_ancestor(rel)
            if ancestor is not None:
                listing.files.append(ancestor)
                continue
            path = root / rel
            if is_link(path) or path.is_file():
                listing.files.append(rel)
            elif path.is_dir():  # nested repository or submodule: its working tree, not its .git
                listing.nested.append(rel)
                _walk(root, path, listing)
    listing.files = sorted(set(listing.files))
    return listing


def tree_fingerprint(root: str | Path) -> dict[str, str]:
    """Strict fingerprint of every entry below ``root`` except Git metadata.

    Includes ignored files and caches on purpose: a read-only run must not create them.
    """
    root = Path(root)
    listing = _Listing()
    _walk(root, root, listing)
    return {rel: entry_digest(root, rel) for rel in listing.files}


def project_files(root: str | Path) -> list[str]:
    """Entries that make up the project: Git tracked + untracked-not-ignored, else every entry."""
    return _listing(Path(root)).files


# Directories where coding agents and editors install their own tools (skills, rules, extensions): a link
# there is the auditor's or the developer's tooling, not part of the product, its build or its tests.
AGENT_TOOL_DIRS = frozenset({".claude", ".codex", ".cursor", ".gemini", ".agents", ".windsurf", ".continue", ".vscode", ".idea"})


def link_kind(root: Path, rel: str, tracked: set[str] | None) -> str:
    """AGENT_TOOL (inside an agent/editor tool directory), TRACKED (versioned with the project), UNTRACKED."""
    if rel.split("/", 1)[0] in AGENT_TOOL_DIRS:
        return "AGENT_TOOL"
    if tracked is None:
        return "UNKNOWN"
    return "TRACKED" if rel in tracked else "UNTRACKED"


def boundary_report(root: str | Path) -> dict:
    """Links leaving the project, broken links and nested repositories (reported, never followed)."""
    root = Path(root)
    listing = _listing(root)
    external, broken = [], []
    for rel in listing.files:
        path = root / rel
        if is_link(path):
            if _link_identity(root, path)[0] == "external":
                external.append(rel)
            if not os.path.exists(path):
                broken.append(rel)
    listed = _git(root, "ls-files", "-z", "--cached") if external else None
    tracked = {p for p in listed.split("\0") if p} if listed is not None else None
    kinds = {rel: link_kind(root, rel, tracked) for rel in external}
    return {"external_links": external, "broken_links": broken, "nested_repositories": listing.nested, "external_link_kinds": kinds}


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
    files = {path: entry_digest(root, path) for path in project_files(root)}
    revision = _git(root, "rev-parse", "HEAD")
    status = _git(root, "status", "--porcelain", "--untracked-files=normal") if revision else None
    return Baseline(
        root=str(root),
        revision=revision.strip() if revision else None,
        dirty=bool(status.strip()) if status is not None else None,
        files=files,
    )


# --- copying -------------------------------------------------------------------------

def _make_link(link: Path, target: Path, directory: bool) -> bool:
    try:
        os.symlink(os.path.relpath(target, link.parent) if target.is_absolute() else target, link, target_is_directory=directory)
        return True
    except (OSError, ValueError):
        pass
    if directory and os.name == "nt":
        try:
            import _winapi

            _winapi.CreateJunction(str(target), str(link))
            return True
        except OSError:
            return False
    return False


def _copy_files(source: Path, target: Path, files: list[str]) -> list[str]:
    """Copy project entries; returns notes about links that could not be reproduced exactly."""
    notes: list[str] = []
    links = [rel for rel in files if is_link(source / rel)]
    for rel in files:
        if rel in links:
            continue
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, destination, follow_symlinks=False)
    for rel in links:  # after regular files, so rebased internal targets exist
        src, destination = source / rel, target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        kind, where = _link_identity(source, src)
        directory = os.path.isdir(src)
        link_to = target / where if kind == "internal" else Path(where)
        if _make_link(destination, link_to, directory):
            continue
        if kind == "internal" and os.path.isfile(src):
            shutil.copy2(src, destination)  # internal content only, materialized
            notes.append(f"{rel}: internal link materialized as a copy (links unsupported here)")
        else:
            notes.append(f"{rel}: link not reproduced; its target was not copied")
    return notes


def create_workspace(baseline: Baseline, *, prefer_worktree: bool = True) -> Path:
    """Create an isolated copy of the exact baseline outside the project.

    A detached Git worktree is used for a clean repository root; otherwise the baseline
    entries are copied. Either way the result is verified against the baseline fingerprint.
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

    observed = {path: entry_digest(workspace, path) for path in project_files(workspace)}
    if observed != baseline.files:
        remove_workspace(baseline, workspace)
        if use_worktree:
            return create_workspace(baseline, prefer_worktree=False)
        raise RuntimeError("candidate workspace does not match the baseline fingerprint")
    return workspace


def snapshot(source: str | Path, target: str | Path | None = None) -> Path:
    """Copy of a project or workspace's entries; a disposable temp dir by default."""
    source = Path(source)
    target = Path(target) if target else Path(tempfile.mkdtemp(prefix="assertiva-run-"))
    target.mkdir(parents=True, exist_ok=True)
    _copy_files(source, target, project_files(source))
    return target.resolve()


def link_installed(copy: str | Path, origin: str | Path, names) -> list[str]:
    """Link installed dependency directories from the origin into a copy.

    Installed dependencies are usually ignored, so copies never contain them; runners that need
    them get a link (never a copy, never followed on removal). Names must stay inside both roots.
    """
    copy, origin = Path(copy), Path(origin)
    linked = []
    for name in names:
        rel = PurePosixPath(str(name).replace("\\", "/"))
        if not str(name) or rel.is_absolute() or ".." in rel.parts or PureWindowsPath(str(name)).drive:
            raise PathBoundaryError(f"installed dependency path escapes the project: {name!r}")
        source, target = origin / rel, copy / rel
        if not source.is_dir() or os.path.lexists(target):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if _make_link(target, source.resolve(), directory=True):
            linked.append(rel.as_posix())
    return linked


def remove_workspace(baseline: Baseline | None, workspace: str | Path) -> None:
    workspace = Path(workspace)
    if baseline is not None and (workspace / ".git").is_file():
        _git(Path(baseline.root), "worktree", "remove", "--force", str(workspace))
        _git(Path(baseline.root), "worktree", "prune")
    remove_tree(workspace)


def remove_tree(path: str | Path) -> None:
    """Delete a directory without following links inside it (junctions included)."""
    path = Path(path)
    if not os.path.lexists(path):
        return
    for root, dirs, files in os.walk(path, topdown=True):
        for name in [*dirs]:
            child = Path(root) / name
            if is_link(child):
                dirs.remove(name)
                _unlink_link(child)
    shutil.rmtree(path, ignore_errors=True)


def _unlink_link(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        try:
            os.rmdir(path)  # directory junctions/symlinks on Windows
        except OSError:
            pass


# --- change set and approved application --------------------------------------------

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
    entries = project_files(workspace)
    ignored = _ignored_by_project(baseline, [p for p in entries if p not in baseline.files])
    candidate = {path: entry_digest(workspace, path) for path in entries if path not in ignored}
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


_DRIVE = re.compile(r"^[A-Za-z]:")


def _path_problem(rel: str) -> str | None:
    if not rel or rel.startswith(("/", "\\")) or _DRIVE.match(rel) or "\\" in rel:
        return f"{rel!r} is not a relative project path"
    if any(part in ("", ".", "..") for part in rel.split("/")):
        return f"{rel!r} traverses outside its directory"
    return None


def _linked_parent(root: Path, rel: str) -> str | None:
    parts = rel.split("/")
    for i in range(1, len(parts)):
        prefix = "/".join(parts[:i])
        if is_link(root / prefix):
            return prefix
    return None


def _boundary_problems(project: Path, workspace: Path, baseline: Baseline, approved: list[CandidateTestChange]) -> list[str]:
    problems: list[str] = []
    existing = {p.casefold(): p for p in baseline.files}
    seen: dict[str, str] = {}
    for change in approved:
        rel = change.path
        problem = _path_problem(rel)
        if problem:
            problems.append(problem)
            continue
        for root, name in ((project, "project"), (workspace, "candidate")):
            linked = _linked_parent(root, rel)
            if linked:
                problems.append(f"{rel}: {name} directory {linked!r} is a link; writes through links are refused")
        source = workspace / rel
        if change.kind is not CandidateChangeKind.RETIRE_CANDIDATE and is_link(source):
            if _link_identity(workspace, source)[0] == "external":
                problems.append(f"{rel}: candidate link points outside the project")
        folded = rel.casefold()
        if (existing.get(folded, rel) != rel) or (seen.get(folded, rel) != rel):
            problems.append(f"{rel}: case-only collision with {existing.get(folded) or seen.get(folded)}")
        seen[folded] = rel
    return problems


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
    problems = _boundary_problems(project_root, workspace, baseline, approved)
    if problems:
        raise PathBoundaryError(problems)
    stale = sorted(
        change.path
        for change in approved
        if entry_digest(project_root, change.path) != change.original_fingerprint
        or entry_digest(workspace, change.path) != change.candidate_fingerprint
    )
    if stale:
        raise StaleBaselineError(stale)

    _transaction(project_root, workspace, approved)
    return approved


class ApplyFailedError(RuntimeError):
    pass


_STAGED = ".assertiva-staged"


def _transaction(project: Path, workspace: Path, approved: list[CandidateTestChange]) -> None:
    """Stage, back up, install, verify; on any failure restore everything touched."""
    backup_dir = Path(tempfile.mkdtemp(prefix="assertiva-apply-backup-"))
    backups: dict[str, tuple[str, str] | None] = {}  # path -> ("file", backup) | ("link", target) | None
    created: list[Path] = []
    staged: dict[str, Path] = {}
    touched: list[CandidateTestChange] = []
    try:
        for index, change in enumerate(approved):
            target = project / change.path
            if os.path.lexists(target):
                if is_link(target):
                    backups[change.path] = ("link", str(_real(target)))
                else:
                    shutil.copy2(target, backup_dir / str(index), follow_symlinks=False)
                    backups[change.path] = ("file", str(backup_dir / str(index)))
            else:
                backups[change.path] = None
            if change.kind is CandidateChangeKind.RETIRE_CANDIDATE or is_link(workspace / change.path):
                continue
            for parent in reversed([*target.parents]):
                if parent != project and project in parent.parents and not os.path.lexists(parent):
                    parent.mkdir()
                    created.append(parent)
            staged[change.path] = target.with_name(target.name + _STAGED)
            shutil.copy2(workspace / change.path, staged[change.path], follow_symlinks=False)
        for change in approved:
            touched.append(change)
            _install(project, workspace, change, staged.get(change.path))
        mismatched = [c.path for c in approved if entry_digest(project, c.path) != c.candidate_fingerprint]
        if mismatched:
            raise ApplyFailedError("applied content does not match the candidate: " + ", ".join(mismatched))
    except Exception as exc:
        _rollback(project, touched, backups)
        for path in staged.values():
            if os.path.lexists(path):
                path.unlink()
        for directory in reversed(created):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise ApplyFailedError(f"apply failed and was rolled back: {exc}") from exc
    finally:
        remove_tree(backup_dir)


def _install(project: Path, workspace: Path, change: CandidateTestChange, staged: Path | None) -> None:
    target, source = project / change.path, workspace / change.path
    if os.path.lexists(target) and is_link(target):
        _unlink_link(target)
    if change.kind is CandidateChangeKind.RETIRE_CANDIDATE:
        if os.path.lexists(target):
            target.unlink()
    elif is_link(source):
        _, where = _link_identity(workspace, source)
        if not _make_link(target, project / where, os.path.isdir(source)):
            raise PathBoundaryError([f"{change.path}: the link cannot be reproduced on this platform"])
    else:
        os.replace(staged, target)  # atomic per file


def _rollback(project: Path, touched: list[CandidateTestChange], backups: dict) -> None:
    for change in reversed(touched):
        target = project / change.path
        if os.path.lexists(target):
            if is_link(target):
                _unlink_link(target)
            else:
                target.unlink()
        original = backups.get(change.path)
        if original and original[0] == "file":
            shutil.copy2(original[1], target, follow_symlinks=False)
        elif original and original[0] == "link":
            _make_link(target, Path(original[1]), os.path.isdir(original[1]))
