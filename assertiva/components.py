"""Workspace components (packages/modules) and which of them a change affects.

Facts only. Adapters report components and dependencies declared by manifests (E1), the workspace
configuration files that affect every component, and dependencies they could not resolve (unknowns).
A component affected by a change takes its declared dependents with it, transitively. What to run
about it (widening, fallback, confidence) is decided by the selection, nowhere else.
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

    def affected(self, changes) -> dict[str, str]:
        """Components a change affects, and why (facts only; widening is the selection's policy)."""
        affected: dict[str, str] = {}
        for change in changes:
            for path in dict.fromkeys(p for p in (change.path, change.old_path) if p):
                if path in self.workspace_files:
                    for name in self.components:
                        affected.setdefault(name, f"workspace configuration changed ({path})")
                    continue
                owner = self.owner(path)
                if owner is None:
                    continue
                affected.setdefault(owner.name, "contains a changed file")
                for dependent, through in self.dependents(owner.name).items():
                    affected.setdefault(dependent, f"depends on {through} ({self.components[dependent].manifest})")
        if changes:
            for component in self.components.values():
                if component.unknown_dependencies:
                    affected.setdefault(component.name, "has unknown dependencies: " + ", ".join(component.unknown_dependencies))
        return affected


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
