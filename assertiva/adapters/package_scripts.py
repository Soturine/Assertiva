"""package.json scripts as declared local verification checks.

Scripts are discovered, classified by their command and never executed by discovery.
"""

from __future__ import annotations

import json
from pathlib import Path

from assertiva.verification import SupportLevel, VerificationCheck, VerificationKind, VerificationOrigin

from .commands import classify_command


_RUNNERS = (("npm", "run"), ("npm", "run-script"), ("pnpm", "run"), ("yarn", "run"), ("bun", "run"), ("npm",), ("pnpm",), ("yarn",), ("bun",))


_RUN_ALL = ("npm-run-all", "run-s", "run-p", "concurrently")


def script_calls(command: str, scripts: dict) -> list[str]:
    """Scripts of this package.json a script command runs: `npm test`, `npm run x`, `yarn x`, `pnpm x`, `run-s a b`."""
    import re
    import shlex

    calls = []
    for segment in re.split(r"\s*(?:&&|\|\||;|&)\s*", command):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            tokens = segment.split()
        if tokens and tokens[0] in _RUN_ALL:
            calls += [t for t in tokens[1:] if t in scripts]
            continue
        for runner in _RUNNERS:
            if tuple(tokens[: len(runner)]) == runner and len(tokens) > len(runner) and tokens[len(runner)] in scripts:
                calls.append(tokens[len(runner)])
                break
    return list(dict.fromkeys(calls))


def script_graph(scripts: dict) -> dict[str, dict]:
    """For every script: the scripts it calls directly and every script it reaches (cycles stop, never loop). A script
    reached through two paths runs twice when both are invoked: repetition is cost, not more evidence (TCC-A11)."""
    direct = {name: script_calls(str(command), scripts) for name, command in scripts.items()}

    def reach(name, seen):
        out = []
        for callee in direct.get(name, []):
            if callee not in seen:
                out += [callee, *reach(callee, seen | {callee})]
        return out

    return {name: {"calls": direct[name], "reaches": list(dict.fromkeys(reach(name, {name})))} for name in scripts}


def repeated_scripts(checks: list, delivery: list) -> dict[str, list[str]]:
    """Scripts reached by more than one CI step's script invocation (npm test -> test:integration -> test:mqtt, and the
    CI also runs test:integration): script -> the CI steps that run it."""
    import shlex

    graph = {c.metadata.get("script"): c.metadata for c in checks if c.adapter_id == "package-scripts" and c.metadata.get("script")}
    runs: dict[str, list[str]] = {}
    for check in delivery if graph else ():
        try:
            tokens = shlex.split(check.command or "", posix=True)
        except ValueError:
            continue
        invoked = next((tokens[len(r)] for r in _RUNNERS if tuple(tokens[: len(r)]) == r and len(tokens) > len(r)
                        and tokens[len(r)] in graph), None)
        for script in [invoked, *graph[invoked].get("reaches", [])] if invoked else ():
            runs.setdefault(script, []).append(check.check_id)
    # AXR-05: the same script in two workflow files is not one run repeated (a push gate and a tag release run on
    # different events); only steps of one workflow file are compared
    out = {}
    for script, steps in sorted(runs.items()):
        by_file: dict[str, list[str]] = {}
        for step in steps:
            by_file.setdefault(_workflow_of(step), []).append(step)
        repeated = [s for group in by_file.values() if len(group) > 1 for s in group]
        if repeated:
            out[script] = repeated
    return out


def _workflow_of(check_id: str) -> str:
    """The configuration file a CI check id names (gha:.github/workflows/ci.yml:job:3 -> that file)."""
    parts = check_id.split(":")
    return parts[1] if len(parts) > 2 else check_id


def invoked(command: str, scripts: dict) -> list[str]:
    """Scripts a command runs, directly and through nested scripts, in order; cycles stop."""
    graph = script_graph(scripts)
    out = []
    for name in script_calls(command, scripts):
        out += [name, *graph.get(name, {}).get("reaches", [])]
    return list(dict.fromkeys(out))


class PackageScriptsAdapter:
    adapter_id = "package-scripts"

    def invoked_scripts(self, root: Path, check: VerificationCheck) -> list[str]:
        """The package.json scripts a declared step runs (npm run verify -> verify and what it calls)."""
        try:
            scripts = json.loads((Path(root) / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
        except (OSError, ValueError):
            return []
        return invoked(check.command or "", scripts) if check.command else []

    def effective_tool(self, root: Path, check: VerificationCheck) -> str | None:
        """The tool a declared `npm test` / `npm run lint` / `yarn lint` step really runs, read from package.json.
        Used only to match equivalent checks; the step's own classification (and what may run) is unchanged."""
        import shlex

        try:
            tokens = shlex.split(check.command or "", posix=True)
            scripts = json.loads((Path(root) / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
        except (OSError, ValueError):
            return None
        for runner in _RUNNERS:
            if tuple(tokens[: len(runner)]) == runner and len(tokens) > len(runner):
                name = tokens[len(runner)]
                if name in scripts:
                    cls = classify_command(str(scripts[name]))
                    return cls.tool if not cls.setup_only and cls.kind is not VerificationKind.UNKNOWN else None
        return None

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / "package.json").is_file() else SupportLevel.UNSUPPORTED

    def discover(self, root: Path) -> list[VerificationCheck]:
        try:
            scripts = json.loads((Path(root) / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
        except (OSError, ValueError) as exc:
            return [VerificationCheck(check_id="package-scripts", kind=VerificationKind.UNKNOWN, origin=VerificationOrigin.LOCAL,
                                      source="package.json", adapter_id=self.adapter_id, evidence_tier="E2",
                                      limitations=(f"package.json could not be read: {exc}"[:200],))]
        checks, graph = [], script_graph(scripts)
        for name, command in sorted(scripts.items()):
            cls = classify_command(str(command))
            if cls.setup_only:
                continue
            checks.append(VerificationCheck(
                check_id=f"package-script:{name}", kind=cls.kind, origin=VerificationOrigin.LOCAL, command=str(command),
                tool=cls.tool, source="package.json", adapter_id=self.adapter_id, evidence_tier="E2",
                limitations=("no adapter classifies this script; its semantics are unknown",) if cls.kind is VerificationKind.UNKNOWN else (),
                metadata={"script": name, "runner_args": list(cls.runner_args), **graph.get(name, {})},
            ))
        return checks
