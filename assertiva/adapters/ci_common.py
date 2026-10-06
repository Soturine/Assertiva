"""Normalization shared by CI configuration adapters: one declared command -> one VerificationCheck.

Every provider adapter reads only its own file format; commands, gates, matrices, operating
systems, runtimes, environments and conditions are normalized here the same way for all of them.
Configuration is declared evidence (E2): it never proves that a step was selected or executed.
"""

from __future__ import annotations

import re

from assertiva.verification import GateMode, VerificationCheck, VerificationKind, VerificationOrigin

from .commands import classify_command

# matrix/variable key (lower case, "." and "_" as "-") -> normalized dimension
_DIMENSIONS = {
    "python": ("python", "python-version", "pythonversion", "py"),
    "node": ("node", "node-version", "nodeversion", "nodejs"),
    "java": ("java", "java-version", "javaversion", "jdk"),
    "os": ("os", "runs-on", "vmimage", "platform"),
}
_EXPRESSION = ("${", "$(", "$[")
_IMAGE_RUNTIME = re.compile(r"(?:^|/)(python|node|openjdk|eclipse-temurin|maven)[:@-]?(\d+(?:\.\d+)*)?", re.I)


def dimension(key: str) -> str | None:
    key = str(key).lower().replace(".", "-").replace("_", "-")
    return next((dim for dim, names in _DIMENSIONS.items() if key in names), None)


def matrix_values(matrix) -> dict[str, list[str]]:
    """Normalized dimension -> declared values from any provider's matrix shape (dicts, lists, includes)."""
    found: dict[str, list[str]] = {}

    def add(key, value):
        dim = dimension(key)
        if dim is None or value is None:
            return
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, (str, int, float)) and not any(m in str(item) for m in _EXPRESSION) and str(item) not in found.setdefault(dim, []):
                found[dim].append(str(item))

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, (dict, list)) and dimension(key) is None:
                    walk(value)
                else:
                    add(key, value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(matrix)
    return found


def image_runtime(image) -> dict[str, list[str]]:
    """Runtime hinted by a container image name (``python:3.12`` -> python 3.12)."""
    match = _IMAGE_RUNTIME.search(str(image or ""))
    name = match.group(1).lower() if match else None
    if not match or not match.group(2) or name == "maven":  # a maven image tag is Maven's version, not Java's
        return {}
    return {{"openjdk": "java", "eclipse-temurin": "java"}.get(name, name): [match.group(2)]}


def merge_values(*sources: dict[str, list[str]]) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for source in sources:
        for dim, values in (source or {}).items():
            for value in values:
                if value and not any(marker in value for marker in _EXPRESSION) and value not in merged.setdefault(dim, []):
                    merged[dim].append(value)
    return merged


def lifecycle(condition, deploys: bool) -> dict:
    return {
        "declared": True,
        "selected": "CONDITIONAL" if condition not in (None, "", [], {}) else "UNCONDITIONAL",
        "executed": "UNKNOWN",  # configuration never proves execution; remote CI is never queried
        "deploys": deploys,
    }


def command_check(adapter_id: str, check_id: str, command: str, source: str, gate: GateMode, meta: dict,
                  deploys: bool = False) -> VerificationCheck | None:
    """A declared command step, classified; None for setup-only commands."""
    command = command.strip()
    cls = classify_command(command)
    if cls.setup_only:
        return None
    limitations = []
    if cls.kind is VerificationKind.UNKNOWN:
        limitations.append("no adapter classifies this command; its semantics are unknown")
    if cls.unclassified and cls.kind is not VerificationKind.UNKNOWN:
        limitations.append("step also runs unclassified commands: " + "; ".join(cls.unclassified))
    deploys = deploys or cls.kind is VerificationKind.DEPLOY
    return VerificationCheck(
        check_id=check_id, kind=cls.kind, origin=VerificationOrigin.CI, gate=gate, command=command, tool=cls.tool,
        source=source, adapter_id=adapter_id, evidence_tier="E2", limitations=tuple(limitations),
        metadata={**meta, **cls.metadata, "runner_args": list(cls.runner_args), "lifecycle": lifecycle(meta.get("condition"), deploys)},
    )


def opaque_check(adapter_id: str, check_id: str, tool: str, source: str, gate: GateMode, meta: dict, limitation: str,
                 deploys: bool = False) -> VerificationCheck:
    """A step whose semantics live outside the repository (actions, tasks, plugins)."""
    return VerificationCheck(
        check_id=check_id, kind=VerificationKind.UNKNOWN, origin=VerificationOrigin.CI, gate=gate, tool=tool, source=source,
        adapter_id=adapter_id, evidence_tier="E2", limitations=(limitation,),
        metadata={**meta, "lifecycle": lifecycle(meta.get("condition"), deploys)},
    )


def unreadable_check(adapter_id: str, check_id: str, source: str, problem: str) -> VerificationCheck:
    return VerificationCheck(check_id=check_id, kind=VerificationKind.UNKNOWN, origin=VerificationOrigin.CI, source=source,
                             adapter_id=adapter_id, evidence_tier="E2", limitations=(problem.splitlines()[0][:200],))
