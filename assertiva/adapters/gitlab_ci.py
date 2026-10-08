"""GitLab CI adapter: ``.gitlab-ci.yml`` and its local includes -> declared CI VerificationChecks (E2).

The effective configuration is resolved the way GitLab merges it, as far as the repository alone allows:
local includes (paths, globs, nested includes; cycles and missing files reported), deep merge in include order
with the main file last, ``default:`` keywords, hidden jobs and ``extends`` (multi-level, cycles reported),
and ``!reference`` tags. Remote, project, template and component includes are never fetched: they stay
opaque checks, so the resolved configuration is then explicitly partial. Each ``before_script``/``script``
entry is a classified command; ``rules``/``only``/``except``/``when`` make a job conditional; ``allow_failure``
is an allowed failure. Nothing is ever run against GitLab.
"""

from __future__ import annotations

import glob
from pathlib import Path

import yaml

from assertiva.verification import GateMode, SupportLevel, VerificationCheck

from .ci_common import command_check, image_runtime, matrix_values, merge_values, opaque_check, unreadable_check

ENTRY = ".gitlab-ci.yml"
_GLOBAL = {"stages", "variables", "default", "include", "workflow", "image", "services", "before_script", "after_script",
           "cache", "pages"}
_DEFAULTS = ("image", "services", "before_script", "after_script", "tags", "interruptible", "retry", "timeout")
_CONDITIONS = ("rules", "only", "except", "when")
_MAX_INCLUDES = 150  # GitLab's own limit for a pipeline
_MAX_EXTENDS = 11  # GitLab's nesting limit


class _Reference(list):
    """A ``!reference [job, key, ...]`` tag, resolved after merging."""


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!reference", lambda loader, node: _Reference(loader.construct_sequence(node, deep=True)))


def _lines(value) -> list[str]:
    if isinstance(value, list):
        out = []
        for item in value:
            out += _lines(item) if isinstance(item, list) else ([str(item)] if item is not None else [])
        return out
    return [str(value)] if value else []


def _merge(base: dict, override: dict) -> dict:
    """GitLab's merge: mappings merge deeply, any other value (lists included) is replaced."""
    out = dict(base)
    for key, value in override.items():
        out[key] = _merge(out[key], value) if isinstance(out.get(key), dict) and isinstance(value, dict) else value
    return out


class GitLabCiAdapter:
    adapter_id = "gitlab-ci"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / ENTRY).is_file() else SupportLevel.UNSUPPORTED

    def _load(self, root: Path, rel: str) -> dict:
        document = yaml.load((root / rel).read_text(encoding="utf-8"), Loader=_Loader)  # noqa: S506 - SafeLoader subclass
        if not isinstance(document, dict):
            raise ValueError("not a mapping")
        return document

    def _include_entries(self, value) -> list:
        return value if isinstance(value, list) else [value] if value else []

    def _local_targets(self, root: Path, pattern: str) -> list[str]:
        """Repository paths an include names (leading slash = repository root; globs allowed); never outside it."""
        relative = pattern.lstrip("/")
        matches = sorted(glob.glob(str(root / relative), recursive=True)) if any(c in relative for c in "*?[") else [str(root / relative)]
        out = []
        for match in matches:
            path = Path(match).resolve()
            if root.resolve() in path.parents and path.is_file():
                out.append(path.relative_to(root.resolve()).as_posix())
        return out

    def _resolve(self, root: Path) -> tuple[dict, dict[str, str], list[VerificationCheck]]:
        """Merged configuration, the file that last defined each top-level key, and checks for what stays opaque."""
        notes: list[VerificationCheck] = []
        origin: dict[str, str] = {}
        visited: list[str] = []

        def load(rel: str, chain: tuple[str, ...]) -> dict:
            if rel in chain:
                notes.append(unreadable_check(self.adapter_id, f"gitlab:{rel}:include-cycle", rel,
                                              "include cycle: " + " -> ".join([*chain, rel])))
                return {}
            if rel in visited or len(visited) >= _MAX_INCLUDES:
                return {}  # GitLab includes a file once
            visited.append(rel)
            try:
                document = self._load(root, rel)
            except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
                notes.append(unreadable_check(self.adapter_id, f"gitlab:{rel}", rel, f"pipeline file could not be read: {exc}"))
                return {}
            merged: dict = {}
            for index, entry in enumerate(self._include_entries(document.get("include")), start=1):
                local = entry if isinstance(entry, str) and "://" not in entry else entry.get("local") if isinstance(entry, dict) else None
                if local:
                    targets = self._local_targets(root, str(local))
                    if not targets:
                        notes.append(unreadable_check(self.adapter_id, f"gitlab:{rel}:include:{index}", rel,
                                                      f"included local file not found in the repository: {local}"))
                    for target in targets:
                        merged = _merge(merged, load(target, (*chain, rel)))
                else:
                    kind = next((k for k in ("remote", "project", "template", "component") if isinstance(entry, dict) and k in entry),
                                "remote" if isinstance(entry, str) else "include")
                    notes.append(opaque_check(self.adapter_id, f"gitlab:{rel}:include:{index}", f"include:{kind}", rel, GateMode.UNKNOWN, {},
                                              f"{kind} include is not followed (never fetched); jobs it defines are not part of this configuration"))
            own = {key: value for key, value in document.items() if key != "include"}
            for key in own:
                origin[key] = rel
            return _merge(merged, own)

        return load(ENTRY, ()), origin, notes

    def _resolve_references(self, value, config: dict, depth: int = 0):
        if isinstance(value, _Reference):
            target = config
            for part in value:
                target = target.get(part) if isinstance(target, dict) else None
            return self._resolve_references(target, config, depth + 1) if depth < 10 else None
        if isinstance(value, list):
            out = []
            for item in value:
                resolved = self._resolve_references(item, config, depth)
                out += resolved if isinstance(item, _Reference) and isinstance(resolved, list) else [resolved]
            return out
        if isinstance(value, dict):
            return {k: self._resolve_references(v, config, depth) for k, v in value.items()}
        return value

    def _expand(self, name: str, config: dict, seen: tuple[str, ...] = ()) -> tuple[dict, str | None]:
        """A job with its ``extends`` chain merged in (parents first); a problem when the chain cannot be resolved."""
        job = config.get(name)
        if not isinstance(job, dict):
            return {}, f"extended job {name} is not defined"
        parents = job.get("extends")
        parents = [parents] if isinstance(parents, str) else list(parents or [])
        if not parents:
            return job, None
        if name in seen or len(seen) >= _MAX_EXTENDS:
            return job, "extends cycle or nesting deeper than GitLab allows: " + " -> ".join([*seen, name])
        merged, problem = {}, None
        for parent in parents:
            expanded, issue = self._expand(str(parent), config, (*seen, name))
            merged = _merge(merged, expanded)
            problem = problem or issue
        merged = _merge(merged, {k: v for k, v in job.items() if k != "extends"})
        return merged, problem

    def discover(self, root: Path) -> list[VerificationCheck]:
        root = Path(root)
        try:
            self._load(root, ENTRY)
        except (OSError, UnicodeDecodeError, yaml.YAMLError, ValueError) as exc:
            return [unreadable_check(self.adapter_id, f"gitlab:{ENTRY}", ENTRY, f"pipeline could not be parsed: {exc}")]
        config, origin, checks = self._resolve(root)
        config = self._resolve_references(config, config)
        default = config.get("default") if isinstance(config.get("default"), dict) else {}
        defaults = {key: default.get(key, config.get(key)) for key in _DEFAULTS if default.get(key, config.get(key)) is not None}
        for name, raw in config.items():
            if name in _GLOBAL or str(name).startswith(".") or not isinstance(raw, dict):
                continue
            job, problem = self._expand(name, config)
            job = {**{k: v for k, v in defaults.items() if k not in job}, **job}
            source = origin.get(name, ENTRY)
            image = job.get("image")
            image = image.get("name") if isinstance(image, dict) else image
            environment = job.get("environment")
            environment = environment.get("name") if isinstance(environment, dict) else environment
            matrix = (job.get("parallel") or {}).get("matrix") if isinstance(job.get("parallel"), dict) else None
            condition = {key: job[key] for key in _CONDITIONS if key in job and job[key] != "on_success"} or None
            services = [s.get("name") if isinstance(s, dict) else str(s) for s in job.get("services") or []]
            meta = {"job": name, "stage": job.get("stage", "test"), "environment": environment, "matrix": matrix, "condition": condition,
                    "image": image, "services": [s for s in services if s], "needs": job.get("needs"), "defined_in": source,
                    "matrix_values": merge_values(matrix_values(matrix), image_runtime(image))}
            if raw.get("extends"):
                meta["extends"] = raw["extends"]
            allow = job.get("allow_failure")
            gate = GateMode.ALLOWED_FAILURE if allow is True or isinstance(allow, dict) else GateMode.UNKNOWN
            if isinstance(allow, dict):
                meta["allow_failure"] = allow
            if job.get("when") == "never":
                continue
            limitations = (problem,) if problem else ()
            for index, command in enumerate([*_lines(job.get("before_script")), *_lines(job.get("script"))], start=1):
                check = command_check(self.adapter_id, f"gitlab:{ENTRY}:{name}:{index}", command, f"{source}#{name}", gate, meta,
                                      deploys=bool(environment))
                if check is not None:
                    if limitations:
                        check = VerificationCheck(**{**check.__dict__, "limitations": check.limitations + limitations})
                    checks.append(check)
        return checks
