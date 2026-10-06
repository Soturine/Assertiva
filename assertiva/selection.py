"""Conservative test selection from a revision-scoped impact graph.

A change selects the tests with a proven path to it (E0–E3). Whenever impact is not proven the
selection widens: shared fixtures to their scope; configuration, unmapped changes, changes with
no proven path, stale graphs and "nothing changed" to the full suite; tests that reach an unknown
relation are always added and the selection is then never claimed complete. E4 heuristics may
add tests but never narrow a run. "No edge found" never means "no test needed".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .impact import ImpactEdge, ImpactGraph, Relation, StaleGraphError, UnknownRelation

CLAIM = ("a green selected set proves only that the selected tests passed at this revision; "
         "it does not prove full-suite success or that the selector found every affected test")


class Trigger(str, Enum):
    SHARED_FIXTURE = "SHARED_FIXTURE"
    CONFIGURATION = "CONFIGURATION"
    UNKNOWN_RELATION = "UNKNOWN_RELATION"
    UNMAPPED_CHANGE = "UNMAPPED_CHANGE"
    NO_PROVEN_PATH = "NO_PROVEN_PATH"
    STALE_GRAPH = "STALE_GRAPH"
    NO_CHANGES = "NO_CHANGES"
    NO_TEST_NODES = "NO_TEST_NODES"
    CHANGES_UNKNOWN = "CHANGES_UNKNOWN"
    COMPONENT_DEPENDENCY = "COMPONENT_DEPENDENCY"


class Confidence(str, Enum):
    PROVEN_PATHS = "PROVEN_PATHS"  # every change mapped through E0–E3 edges and no unknown relation reachable
    BOUNDED_BY_UNKNOWNS = "BOUNDED_BY_UNKNOWNS"  # widened around unknown relations: never complete
    FULL_SUITE = "FULL_SUITE"  # the selection is the whole suite


@dataclass(frozen=True)
class FileChange:
    path: str
    status: str  # A, M, D or R (copies count as additions, type changes as modifications)
    old_path: str | None = None


@dataclass(frozen=True)
class SelectionReason:
    reason: str
    tier: str | None = None
    path: tuple[str, ...] = ()
    trigger: Trigger | None = None


@dataclass(frozen=True)
class Widening:
    trigger: Trigger
    path: str | None
    full: bool
    reason: str


@dataclass
class TestSelection:
    __test__ = False  # not a test class

    revision: str
    base: str | None = None
    graph_revision: str | None = None
    git_revision: str | None = None
    changes: list[FileChange] = field(default_factory=list)
    selected: dict[str, list[SelectionReason]] = field(default_factory=dict)
    not_selected: dict[str, str] = field(default_factory=dict)
    unknown_dependencies: list[UnknownRelation] = field(default_factory=list)
    widening: list[Widening] = field(default_factory=list)
    fallback: str | None = None
    confidence: Confidence = Confidence.FULL_SUITE
    limitations: list[str] = field(default_factory=list)

    @property
    def full(self) -> bool:
        return any(w.full for w in self.widening)


def _path(edges: list[ImpactEdge]) -> tuple[str, ...]:
    return tuple(f"{e.source} -{e.relation.value}-> {e.target}" for e in edges)


def _weakest(edges: list[ImpactEdge]) -> str | None:
    return max((e.tier for e in edges), default=None)


def select_tests(
    graph: ImpactGraph,
    changes: list[FileChange],
    revision: str,
    base: str | None = None,
    must_run: set[str] | frozenset = frozenset(),
) -> TestSelection:
    selection = TestSelection(revision=revision, base=base, graph_revision=graph.revision, git_revision=graph.git_revision,
                              changes=list(changes), limitations=[CLAIM, *graph.limitations])

    def add(test: str, reason: SelectionReason) -> None:
        reasons = selection.selected.setdefault(test, [])
        if reason not in reasons:
            reasons.append(reason)

    def widen(trigger: Trigger, path: str | None, reason: str, full: bool = True) -> None:
        selection.widening.append(Widening(trigger, path, full, reason))

    try:
        graph.require(revision)
    except StaleGraphError as exc:
        widen(Trigger.STALE_GRAPH, None, str(exc))
        return _finish(selection, graph)
    if not graph.tests:
        widen(Trigger.NO_TEST_NODES, None, "no adapter mapped any test at this revision")
    if not changes:
        widen(Trigger.NO_CHANGES, None, "no change was detected; only the full suite is evidence for this state")

    facts = graph.facts()
    fixtures = {e.target for e in facts if e.relation is Relation.DEPENDS_ON_FIXTURE}
    configuration = {e.target for e in facts if e.relation in (Relation.USES_CONFIG, Relation.USES_ARTIFACT)}
    for change in changes:
        traced = False
        old = change.old_path if change.status == "R" else (change.path if change.status == "D" else None)
        if old:
            importers = graph.importers_of_missing(old)
            for test, edges in graph.affected_tests(importers, include_heuristic=False).items():
                add(test, SelectionReason(f"refers to a deleted or renamed file ({old})", _weakest(edges) or "E3", _path(edges)))
                traced = True
            if change.status == "D":
                if not traced:
                    widen(Trigger.NO_PROVEN_PATH, old, "nothing at this revision still refers to the deleted file; its impact is not proven")
                continue
        path = change.path
        if path not in graph.nodes:
            widen(Trigger.UNMAPPED_CHANGE, path, "no adapter relates this file to any test")
            continue
        if path in configuration:
            widen(Trigger.CONFIGURATION, path, "framework, project or build configuration affects every test")
        proven = graph.affected_tests({path}, include_heuristic=False)
        if path in fixtures:
            widen(Trigger.SHARED_FIXTURE, path, f"shared fixture/hook file: every test in its scope ({len(proven)}) is selected", full=False)
        for test, edges in proven.items():
            if test == path:
                add(test, SelectionReason("the test file itself changed", "E1"))
            else:
                add(test, SelectionReason(f"depends on {path}", _weakest(edges), _path(edges)))
        for test, edges in graph.affected_tests({path}).items():
            if test not in proven:
                add(test, SelectionReason(f"heuristic relation to {path} (not proof)", "E4", _path(edges)))
        if not proven and not traced:
            widen(Trigger.NO_PROVEN_PATH, path, "no proven path from this change to any test; no edge found is not evidence that no test is needed")

    if changes:
        for test in sorted(graph.tests):
            reached = graph.unknowns_reached_by(test)
            if reached:
                for unknown in reached:
                    if unknown not in selection.unknown_dependencies:
                        selection.unknown_dependencies.append(unknown)
                add(test, SelectionReason(f"depends on {reached[0].node}, whose dependencies are unknown: {reached[0].reason}",
                                          None, (), Trigger.UNKNOWN_RELATION))
        if selection.unknown_dependencies:
            widen(Trigger.UNKNOWN_RELATION, None,
                  f"{len(selection.unknown_dependencies)} unknown relation(s) reachable from tests; every test reaching one is selected",
                  full=False)
    for test in sorted(must_run):
        add(test, SelectionReason("known failing test or reproducer", None))
    return _finish(selection, graph)


def _finish(selection: TestSelection, graph: ImpactGraph) -> TestSelection:
    if not selection.full and not selection.selected:
        selection.widening.append(Widening(Trigger.NO_PROVEN_PATH, None, True, "nothing was selected; that is never evidence that nothing needs to run"))
    if selection.full:
        triggers = ", ".join(dict.fromkeys(w.trigger.value for w in selection.widening if w.full))
        selection.fallback = f"full suite ({triggers})"
        first = next(w for w in selection.widening if w.full)
        for test in sorted(graph.tests):
            selection.selected.setdefault(test, []).append(SelectionReason(f"widened to the full suite: {first.reason}", None, (), first.trigger))
        selection.not_selected = {}
        selection.confidence = Confidence.FULL_SUITE
    else:
        selection.not_selected = {test: "no proven path from any changed file (E0–E3 edges at this revision)"
                                  for test in sorted(graph.tests - set(selection.selected))}
        selection.confidence = Confidence.BOUNDED_BY_UNKNOWNS if selection.unknown_dependencies else Confidence.PROVEN_PATHS
    if graph.unknowns and selection.confidence is Confidence.PROVEN_PATHS:
        selection.limitations.append("unknown relations exist but no test reaches them statically")
    return selection


def select_changes(root: str | Path, base: str, must_run: set[str] | frozenset = frozenset()) -> TestSelection:
    """Impact graph of the working tree plus the selection for its changes relative to ``base``."""
    from .impact import build_impact_graph

    graph = build_impact_graph(root)
    try:
        changes = changed_files(root, base)
    except ValueError as exc:
        selection = TestSelection(revision=graph.revision, base=base, graph_revision=graph.revision,
                                  git_revision=graph.git_revision, limitations=[CLAIM])
        selection.widening.append(Widening(Trigger.CHANGES_UNKNOWN, None, True, str(exc)))
        return _finish(selection, graph)
    return select_tests(graph, changes, revision=graph.revision, base=base, must_run=must_run)


def changed_files(root: str | Path, base: str) -> list[FileChange]:
    """Changes in the working tree (committed, staged, unstaged, untracked) relative to ``base``."""
    from .workspace import _git

    root = Path(root)
    if _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}") is None:
        raise ValueError(f"unknown base revision: {base}")
    diff = _git(root, "-c", "core.quotepath=false", "diff", "--name-status", "-M", "--relative", base, "--")
    untracked = _git(root, "-c", "core.quotepath=false", "ls-files", "--others", "--exclude-standard")
    if diff is None or untracked is None:
        raise ValueError("the changes could not be read from version control")
    changes = []
    for line in diff.splitlines():
        parts = line.split("\t")
        status = parts[0][:1]
        if status == "R":
            changes.append(FileChange(parts[2], "R", old_path=parts[1]))
        elif status == "C":
            changes.append(FileChange(parts[2], "A"))
        elif status in ("A", "M", "D"):
            changes.append(FileChange(parts[1], status))
        elif status:
            changes.append(FileChange(parts[-1], "M"))
    changes += [FileChange(path, "A") for path in untracked.splitlines() if path]
    return changes
