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
    return {script: steps for script, steps in sorted(runs.items()) if len(steps) > 1}


class PackageScriptsAdapter:
    adapter_id = "package-scripts"

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
