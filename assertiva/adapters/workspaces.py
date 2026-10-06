"""Explicit workspace layouts: npm ``package.json`` workspaces and ``pyproject.toml`` projects in subdirectories.

Components and their dependencies come only from manifests (E1). A dependency that looks local
but cannot be resolved to a component (``workspace:`` protocol, ``file:``/``link:`` paths, direct
file references) is an unknown dependency, never a guess. Other layouts (pnpm, Yarn PnP, Nx,
Maven/Gradle modules) are not read yet.
"""

from __future__ import annotations

import fnmatch
import json
import re
import tomllib
from pathlib import Path, PurePosixPath

from assertiva.components import Component, ComponentContribution

_NPM_WORKSPACE_FILES = ("package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "pnpm-workspace.yaml", ".npmrc")
_NPM_DEP_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
_PY_WORKSPACE_FILES = ("pyproject.toml", "uv.lock", "poetry.lock", "setup.cfg", "requirements.txt", "constraints.txt")
_PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _directory(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return "" if parent == "." else parent


class NpmWorkspacesAdapter:
    adapter_id = "npm-workspaces"

    def components(self, root: Path, files: list[str]) -> ComponentContribution:
        out = ComponentContribution()
        manifest = _json(root / "package.json")
        patterns = manifest.get("workspaces")
        if isinstance(patterns, dict):
            patterns = patterns.get("packages")
        if not isinstance(patterns, list):
            if (root / "pnpm-workspace.yaml").is_file():
                out.limitations.append("pnpm-workspace.yaml layouts are not read yet; their packages are not components")
            return out
        out.workspace_files = {f for f in _NPM_WORKSPACE_FILES if (root / f).is_file()}
        manifests = sorted(f for f in files if PurePosixPath(f).name == "package.json" and "/" in f and "node_modules/" not in f)
        members = [m for m in manifests if any(fnmatch.fnmatch(_directory(m), str(p).rstrip("/")) for p in patterns)]
        data = {m: _json(root / m) for m in members}
        by_name = {d.get("name"): m for m, d in data.items() if d.get("name")}
        by_path = {_directory(m): d.get("name") for m, d in data.items()}
        for member, package in data.items():
            name = package.get("name")
            if not name:
                out.limitations.append(f"{member} has no package name; it is not a component")
                continue
            depends, unknown = [], []
            for key in _NPM_DEP_KEYS:
                for dependency, spec in (package.get(key) or {}).items():
                    spec = str(spec)
                    if dependency in by_name:
                        depends.append(dependency)
                    elif spec.startswith(("file:", "link:")):
                        target = str(PurePosixPath(_directory(member)) / spec.split(":", 1)[1])
                        resolved = by_path.get(_normalize(target))
                        (depends if resolved else unknown).append(resolved or f"{dependency} ({spec})")
                    elif spec.startswith("workspace:"):
                        unknown.append(f"{dependency} ({spec})")
            out.components.append(Component(
                name=name, path=_directory(member), manifest=member, depends_on=tuple(sorted(set(depends))),
                provenance="package.json workspaces + declared dependencies", unknown_dependencies=tuple(unknown),
            ))
        return out


def _normalize(path: str) -> str:
    parts: list[str] = []
    for part in PurePosixPath(path).parts:
        if part == "..":
            if parts:
                parts.pop()
            else:
                return "../"  # escapes the project: never a component
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def _pep503(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


class PythonProjectsAdapter:
    adapter_id = "python-projects"

    def components(self, root: Path, files: list[str]) -> ComponentContribution:
        out = ComponentContribution()
        manifests = sorted(f for f in files if PurePosixPath(f).name == "pyproject.toml" and "/" in f)
        projects = {}
        for manifest in manifests:
            try:
                project = tomllib.loads((root / manifest).read_text(encoding="utf-8")).get("project") or {}
            except (OSError, ValueError) as exc:
                out.limitations.append(f"{manifest} could not be read ({type(exc).__name__}); it is not a component")
                continue
            if project.get("name"):
                projects[manifest] = project
        if not projects:
            return out
        out.workspace_files = {f for f in _PY_WORKSPACE_FILES if (root / f).is_file()}
        names = {_pep503(p["name"]): m for m, p in projects.items()}
        for manifest, project in projects.items():
            requirements = list(project.get("dependencies") or [])
            for extra in (project.get("optional-dependencies") or {}).values():
                requirements += list(extra)
            depends, unknown = [], []
            for requirement in requirements:
                match = _PEP508_NAME.match(str(requirement))
                name = _pep503(match.group(1)) if match else None
                if name in names and name != _pep503(project["name"]):
                    depends.append(name)
                elif " @ file:" in str(requirement) or "@ file:" in str(requirement):
                    unknown.append(str(requirement))
            out.components.append(Component(
                name=_pep503(project["name"]), path=_directory(manifest), manifest=manifest,
                depends_on=tuple(sorted(set(depends))), provenance="pyproject.toml [project] name and dependencies",
                unknown_dependencies=tuple(unknown),
            ))
        return out
