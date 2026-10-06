"""Workspace components (packages/modules) and which of them a change affects.

Only explicit layouts count: adapters report components and dependencies declared by manifests
(E1), the workspace configuration files that affect every component, and dependencies they could
not resolve (unknowns). A component affected by a change takes its declared dependents with it,
transitively. Files outside every component, workspace configuration and unknown dependencies widen.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Component:
    name: str
    path: str  # project-relative directory
    manifest: str
    depends_on: tuple[str, ...] = ()
    provenance: str = ""
    tier: str = "E1"
    unknown_dependencies: tuple[str, ...] = ()


@dataclass
class ComponentContribution:
    components: list[Component] = field(default_factory=list)
    workspace_files: set[str] = field(default_factory=set)
    limitations: list[str] = field(default_factory=list)


@dataclass
class AffectedSet:
    components: dict[str, str] = field(default_factory=dict)  # name -> why it is affected
    widening: list = field(default_factory=list)  # selection.Widening entries

    @property
    def full(self) -> bool:
        return any(w.full for w in self.widening)


@dataclass
class ComponentGraph:
    revision: str
    components: dict[str, Component] = field(default_factory=dict)
    workspace_files: set[str] = field(default_factory=set)
    limitations: list[str] = field(default_factory=list)

    def owner(self, path: str) -> Component | None:
        owners = [c for c in self.components.values() if path == c.path or path.startswith(c.path.rstrip("/") + "/")]
        return max(owners, key=lambda c: len(c.path), default=None)

    def dependents(self, name: str) -> dict[str, str]:
        """Components depending on ``name``, transitively: name -> the dependency it was reached through."""
        reverse: dict[str, list[str]] = {}
        for component in self.components.values():
            for dependency in component.depends_on:
                reverse.setdefault(dependency, []).append(component.name)
        found, queue = {}, deque([name])
        while queue:
            current = queue.popleft()
            for dependent in sorted(reverse.get(current, [])):
                if dependent != name and dependent not in found:
                    found[dependent] = current
                    queue.append(dependent)
        return found

    def affected(self, changes) -> AffectedSet:
        from .selection import Trigger, Widening

        result = AffectedSet()
        for change in changes:
            for path in dict.fromkeys(p for p in (change.path, change.old_path) if p):
                if path in self.workspace_files:
                    result.widening.append(Widening(Trigger.CONFIGURATION, path, True, "workspace configuration affects every component"))
                    continue
                owner = self.owner(path)
                if owner is None:
                    result.widening.append(Widening(Trigger.UNMAPPED_CHANGE, path, True, "the file belongs to no declared component"))
                    continue
                result.components.setdefault(owner.name, "contains a changed file")
                for dependent, through in self.dependents(owner.name).items():
                    result.components.setdefault(dependent, f"depends on {through} ({self.components[dependent].manifest})")
        uncertain = [c for c in self.components.values() if c.unknown_dependencies]
        if changes and uncertain:
            for component in uncertain:
                result.components.setdefault(component.name, "has unknown dependencies: " + ", ".join(component.unknown_dependencies))
            result.widening.append(Widening(Trigger.UNKNOWN_RELATION, None, False,
                                            f"{len(uncertain)} component(s) declare dependencies that could not be resolved; they are always affected"))
        if result.full:
            for name in self.components:
                result.components.setdefault(name, "widened: every component")
        return result


def build_component_graph(root: str | Path, revision: str | None = None, adapters: list | None = None) -> ComponentGraph:
    from .adapters import component_adapters
    from .impact import revision_of
    from .workspace import project_files

    root = Path(root).resolve()
    graph = ComponentGraph(revision=revision or revision_of(root)[0])
    files = project_files(root)
    for adapter in component_adapters(root) if adapters is None else adapters:
        contribution = adapter.components(root, files)
        for component in contribution.components:
            if component.name in graph.components:
                graph.limitations.append(f"component name {component.name!r} is declared twice; the second declaration was ignored")
                continue
            graph.components[component.name] = component
        graph.workspace_files |= contribution.workspace_files
        graph.limitations += contribution.limitations
    return graph
