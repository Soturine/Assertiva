"""Isolated execution environments: run workspaces, verified downloads, safe extraction, the prepared environment.

Everything an execution needs that the project does not ship (an interpreter environment, installed
dependencies, a JDK, a build tool, a disposable service) is prepared outside the project, under
``ASSERTIVA_HOME``: ``tools/`` keeps verified downloads between runs (identified by content), and each run gets
``workspaces/<run-id>/`` (``env/``, ``artifacts/``, ``evidence/``, ``manifest.json``) that is removed when the run
ends, whether it succeeded, failed or was interrupted. Nothing is installed globally, no PATH or registry is
changed, no administrator rights are used. A virtual environment or a copy is not a security sandbox: project
code still runs with the user's permissions and network (reported as the isolation level).

What to prepare is adapter knowledge (``adapters/provisioning.py``); this module never names a tool.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
import urllib.request
import uuid
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .workspace import assertiva_home, remove_tree

MAX_DOWNLOAD_BYTES = 600 * 1024 * 1024
MAX_EXTRACTED_BYTES = 3 * 1024 * 1024 * 1024
DOWNLOAD_TIMEOUT_S = 120
STALE_WORKSPACE_S = 24 * 3600

# Isolation the run actually had, never more than was obtained.
ISOLATION_STATIC = "STATIC_ONLY"  # read and parsed; no project code ran
ISOLATION_COPY = "DISPOSABLE_COPY"  # project code ran in a copy with credentials withheld; same user, same network
ISOLATION_SANDBOX = "SANDBOX"  # container/VM confinement (not provided by this version)


class ProvisioningError(RuntimeError):
    pass


@dataclass
class Step:
    """One preparation: what, why, whether it downloads or runs third-party code, what happened."""

    step_id: str
    ecosystem: str
    action: str
    reason: str
    downloads: list[str] = field(default_factory=list)
    runs_third_party_code: bool = False
    status: str = "PLANNED"  # PLANNED, DONE, REUSED, BLOCKED, FAILED, NOT_NEEDED
    detail: str = ""
    divergences: list[str] = field(default_factory=list)
    duration_s: float | None = None


@dataclass
class Prepared:
    """The environment prepared for this run (read by runners and the process layer)."""

    workspace: Path | None = None
    python: str | None = None
    dirs: dict[str, Path] = field(default_factory=dict)  # installed dependency dir name -> prepared location
    env: dict[str, str] = field(default_factory=dict)  # variables runners need (tool homes, service URLs)
    path_prefix: list[str] = field(default_factory=list)  # tool bin directories, first on PATH for children
    tools: dict[str, str] = field(default_factory=dict)  # tool id -> executable or home
    steps: list[Step] = field(default_factory=list)
    services: list[dict] = field(default_factory=list)
    requirements: list[dict] = field(default_factory=list)
    cleanups: list = field(default_factory=list)  # callables run when the run ends, last first


ACTIVE: Prepared | None = None


@contextmanager
def active(prepared: Prepared):
    """Make ``prepared`` the environment of executions in this block; always clean up at the end."""
    global ACTIVE
    previous, ACTIVE = ACTIVE, prepared
    try:
        yield prepared
    finally:
        ACTIVE = previous
        for cleanup in reversed(prepared.cleanups):
            try:
                cleanup()
            except Exception:  # noqa: BLE001 - one failed cleanup must not skip the others
                pass
        prepared.cleanups.clear()


def child_overlay(env: dict) -> dict:
    """``env`` with the prepared tool homes, service variables and tool bin directories (no-op without a run)."""
    if ACTIVE is None:
        return env
    out = {**env, **ACTIVE.env}
    if ACTIVE.path_prefix:
        out["PATH"] = os.pathsep.join([*ACTIVE.path_prefix, env.get("PATH", "")])
    return out


# --- workspaces --------------------------------------------------------------------------------

def tools_dir() -> Path:
    """Verified downloads kept between runs: ASSERTIVA_TOOLS when set (a shared cache), else ASSERTIVA_HOME/tools."""
    configured = os.environ.get("ASSERTIVA_TOOLS")
    path = Path(configured).resolve() if configured else assertiva_home() / "tools"
    path.mkdir(parents=True, exist_ok=True)
    return path


def new_workspace() -> Path:
    """A fresh run workspace; stale ones left by killed runs are removed first."""
    base = assertiva_home() / "workspaces"
    base.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for old in base.iterdir():
        try:
            if old.is_dir() and now - old.stat().st_mtime > STALE_WORKSPACE_S:
                remove_tree(old)
        except OSError:
            pass
    path = base / uuid.uuid4().hex[:8]  # short: Windows tools still hit the 260-character path limit
    for sub in ("env", "artifacts", "evidence"):
        (path / sub).mkdir(parents=True)
    return path


def write_manifest(prepared: Prepared, extra: dict | None = None) -> None:
    if prepared.workspace is None:
        return
    data = {"workspace": str(prepared.workspace), "python": prepared.python, "tools": prepared.tools,
            "dirs": {k: str(v) for k, v in prepared.dirs.items()}, "env": sorted(prepared.env),
            "steps": [step.__dict__ for step in prepared.steps], "services": prepared.services, **(extra or {})}
    (prepared.workspace / "manifest.json").write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# --- downloads ---------------------------------------------------------------------------------

def _read_url(url: str, limit: int) -> bytes:
    if not url.startswith("https://"):
        raise ProvisioningError(f"refusing a non-HTTPS download: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": "assertiva"})
    with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_S) as response:  # noqa: S310 - https only, checked above
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > limit:
            raise ProvisioningError(f"download of {int(declared)} bytes exceeds the limit of {limit}: {url}")
        data = bytearray()
        while chunk := response.read(1 << 20):
            data += chunk
            if len(data) > limit:
                raise ProvisioningError(f"download exceeds the limit of {limit} bytes: {url}")
    return bytes(data)


def published_sha256(url: str) -> str:
    """The checksum the publisher serves next to an artifact (first hex token of the file)."""
    token = _read_url(url, 4096).decode("ascii", errors="replace").split()[0].lower()
    if len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
        raise ProvisioningError(f"no sha256 at {url}")
    return token


def download(url: str, sha256: str, name: str, limit: int = MAX_DOWNLOAD_BYTES) -> Path:
    """A verified download in the tools cache, named by its checksum; reused when already there."""
    target = tools_dir() / "downloads" / f"{sha256[:16]}-{name}"
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha256:
        return target
    data = _read_url(url, limit)
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256.lower():
        raise ProvisioningError(f"checksum mismatch for {url}: expected {sha256}, got {actual}; the download was discarded")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    partial.write_bytes(data)
    os.replace(partial, target)
    return target


# --- safe extraction ---------------------------------------------------------------------------

def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if not name or path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
        raise ProvisioningError(f"archive entry escapes its target: {name!r}")
    return path


def extract(archive: Path, target: Path, limit: int = MAX_EXTRACTED_BYTES) -> Path:
    """Extract a zip or tar archive into ``target``: no absolute paths, no ``..``, no links or devices, bounded size.
    The whole archive is checked before anything is written."""
    archive, target = Path(archive), Path(target)
    total = 0
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            infos = z.infolist()
            for info in infos:
                _safe_member(info.filename)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ProvisioningError(f"archive entry is a link: {info.filename!r}")
                total += info.file_size
            if total > limit:
                raise ProvisioningError(f"archive expands to {total} bytes, over the limit of {limit}")
            target.mkdir(parents=True, exist_ok=True)
            for info in infos:
                destination = target / _safe_member(info.filename)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as source, open(destination, "wb") as out:
                    shutil.copyfileobj(source, out)
                mode = (info.external_attr >> 16) & 0o777
                if mode and os.name != "nt":
                    os.chmod(destination, mode)
        return target
    try:
        tar = tarfile.open(archive)
    except tarfile.TarError as exc:
        raise ProvisioningError(f"not a supported archive: {archive.name}") from exc
    with tar:
        members = tar.getmembers()
        links = []
        for member in members:
            name = _safe_member(member.name)
            if member.issym():
                # a relative link that stays inside the extraction (shared-library aliases in tool bundles)
                resolved = PurePosixPath(*_normalized(name.parent / member.linkname))
                if member.linkname.startswith("/") or resolved.parts[:1] == ("..",):
                    raise ProvisioningError(f"archive link points outside its target: {member.name!r} -> {member.linkname!r}")
                links.append((name, member.linkname))
                continue
            if not (member.isfile() or member.isdir()):
                raise ProvisioningError(f"archive entry is not a regular file, directory or inner link: {member.name!r}")
            total += member.size
        if total > limit:
            raise ProvisioningError(f"archive expands to {total} bytes, over the limit of {limit}")
        target.mkdir(parents=True, exist_ok=True)
        for member in members:
            if member.issym():
                continue
            destination = target / _safe_member(member.name)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, open(destination, "wb") as out:
                shutil.copyfileobj(source, out)
            if os.name != "nt":
                os.chmod(destination, member.mode & 0o777)
        for name, linkname in links:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                os.symlink(linkname, destination)
            else:  # no unprivileged links on Windows: a copy of the (inner) target when it is a file
                source = (destination.parent / linkname)
                if source.is_file():
                    shutil.copy2(source, destination)
    return target


def _normalized(path: PurePosixPath) -> list[str]:
    parts: list[str] = []
    for part in path.parts:
        if part == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append("..")
        elif part not in (".", ""):
            parts.append(part)
    return parts or ["."]
