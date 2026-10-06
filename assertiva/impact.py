"""Revision-scoped impact graph: which tests may be affected by a change, and why.

An edge says "``source`` may be affected when ``target`` changes", with the revision it was
observed at, its evidence tier and its provenance:

- E0 runtime coverage mapping;
- E1/E2 relationships declared by a framework or by the project;
- E3 static imports/dependencies;
- E4 heuristic inference: usable to add work, never a fact.

Relations that cannot be proven are not invented: they are recorded as unknowns. Language and
framework knowledge lives in adapters, which contribute edges, unknowns and test nodes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Relation(str, Enum):
    IMPORTS = "IMPORTS"
    COVERS = "COVERS"
    DECLARES = "DECLARES"
    MATERIALIZES = "MATERIALIZES"
    DEPENDS_ON_FIXTURE = "DEPENDS_ON_FIXTURE"
    USES_HELPER = "USES_HELPER"
    USES_CONFIG = "USES_CONFIG"
    USES_ARTIFACT = "USES_ARTIFACT"
    TESTS = "TESTS"


TIERS = ("E0", "E1", "E2", "E3", "E4")
HEURISTIC = "E4"


class StaleGraphError(RuntimeError):
    """Evidence observed at one revision was asked about another."""


@dataclass(frozen=True)
class ImpactEdge:
    """``source`` may be affected when ``target`` changes."""

    source: str
    target: str
    relation: Relation
    revision: str
    tier: str
    provenance: str
    limitations: tuple[str, ...] = ()
    confidence: str | None = None  # only where a tool reports one; never invented

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(f"unknown evidence tier {self.tier!r}")

    @property
    def heuristic(self) -> bool:
        return self.tier == HEURISTIC


@dataclass(frozen=True)
class UnknownRelation:
    """``node`` depends on something that cannot be determined (e.g. a computed import)."""

    node: str
    reason: str
    revision: str
    provenance: str


@dataclass
class ImpactContribution:
    """What one adapter can prove about a project at one revision."""

    edges: list[ImpactEdge] = field(default_factory=list)
    unknowns: list[UnknownRelation] = field(default_factory=list)
    tests: set[str] = field(default_factory=set)
    nodes: set[str] = field(default_factory=set)
    # source -> project paths an unresolved reference could have named (to trace deleted files)
    unresolved: dict[str, set[str]] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


@dataclass
class ImpactGraph:
    revision: str
    edges: list[ImpactEdge] = field(default_factory=list)
    unknowns: list[UnknownRelation] = field(default_factory=list)
    tests: set[str] = field(default_factory=set)
    nodes: set[str] = field(default_factory=set)
    unresolved: dict[str, set[str]] = field(default_factory=dict)
    stale: list[ImpactEdge] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    git_revision: str | None = None
    root: str | None = None

    def require(self, revision: str) -> None:
        if revision != self.revision:
            raise StaleGraphError(f"the impact graph was built at {self.revision[:12]}, not at {revision[:12]}")

    def add(self, edge: ImpactEdge) -> None:
        """Add an edge observed at this revision; evidence from another revision is kept aside, never used."""
        if edge.revision != self.revision:
            self.stale.append(edge)
            note = "evidence observed at another revision was not used"
            if note not in self.limitations:
                self.limitations.append(note)
            return
        self.edges.append(edge)
        self.nodes |= {edge.source, edge.target}

    def merge(self, contribution: ImpactContribution) -> None:
        for edge in contribution.edges:
            self.add(edge)
        for unknown in contribution.unknowns:
            if unknown.revision != self.revision:
                raise StaleGraphError("an unknown relation from another revision cannot describe this one")
            self.unknowns.append(unknown)
        self.tests |= contribution.tests
        self.nodes |= contribution.nodes | contribution.tests
        for source, candidates in contribution.unresolved.items():
            self.unresolved.setdefault(source, set()).update(candidates)
        self.limitations += contribution.limitations

    def facts(self) -> list[ImpactEdge]:
        return [edge for edge in self.edges if not edge.heuristic]

    def _usable(self, include_heuristic: bool) -> list[ImpactEdge]:
        return self.edges if include_heuristic else self.facts()

    def affected_tests(self, changed: set[str], include_heuristic: bool = True) -> dict[str, list[ImpactEdge]]:
        """Tests with a path to a changed node, each with the edges proving it (test first)."""
        by_target: dict[str, list[ImpactEdge]] = {}
        for edge in self._usable(include_heuristic):
            by_target.setdefault(edge.target, []).append(edge)
        toward: dict[str, ImpactEdge | None] = {node: None for node in changed}
        queue = deque(sorted(changed))
        while queue:
            node = queue.popleft()
            for edge in by_target.get(node, []):
                if edge.source not in toward:
                    toward[edge.source] = edge
                    queue.append(edge.source)
        result = {}
        for test in sorted(self.tests & set(toward)):
            path, node = [], test
            while toward.get(node) is not None:
                path.append(toward[node])
                node = toward[node].target
            result[test] = path
        return result

    def closure(self, node: str, include_heuristic: bool = False) -> set[str]:
        """Everything ``node`` depends on (forward reachability)."""
        by_source: dict[str, list[ImpactEdge]] = {}
        for edge in self._usable(include_heuristic):
            by_source.setdefault(edge.source, []).append(edge)
        seen, queue = {node}, deque([node])
        while queue:
            for edge in by_source.get(queue.popleft(), []):
                if edge.target not in seen:
                    seen.add(edge.target)
                    queue.append(edge.target)
        return seen

    def unknowns_reached_by(self, test: str) -> list[UnknownRelation]:
        reached = self.closure(test)
        return [unknown for unknown in self.unknowns if unknown.node in reached]

    def importers_of_missing(self, path: str) -> set[str]:
        """Nodes holding an unresolved reference that could have named ``path`` (e.g. a deleted file)."""
        return {source for source, candidates in self.unresolved.items() if path in candidates}


def revision_of(root: str | Path) -> tuple[str, str | None]:
    """(content revision, VCS revision): the content digest identifies exactly what was analyzed."""
    from .workspace import capture_baseline

    baseline = capture_baseline(root)
    return baseline.digest, baseline.revision


def build_impact_graph(root: str | Path, adapters: list | None = None) -> ImpactGraph:
    from .adapters import impact_adapters
    from .workspace import project_files

    root = Path(root).resolve()
    revision, git_revision = revision_of(root)
    graph = ImpactGraph(revision=revision, git_revision=git_revision, root=str(root))
    files = project_files(root)
    adapters = impact_adapters(root) if adapters is None else adapters
    if not adapters:
        graph.limitations.append("no adapter can relate this project's files to its tests; every change is an unknown impact")
    for adapter in adapters:
        graph.merge(adapter.impact(root, revision, files))
    return graph
