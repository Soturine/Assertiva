from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .candidate import StageStatus


class Outcome(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"
    XFAILED = "XFAILED"
    XPASSED = "XPASSED"
    NOT_RUN = "NOT_RUN"


class MutantStatus(str, Enum):
    KILLED = "KILLED"
    SURVIVED = "SURVIVED"
    NO_COVERAGE = "NO_COVERAGE"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"  # invalid mutant: did not compile/load/run
    IGNORED = "IGNORED"
    EQUIVALENT = "EQUIVALENT"
    UNKNOWN = "UNKNOWN"  # pending, not run, or a status this adapter does not know


DETECTED = frozenset({MutantStatus.KILLED, MutantStatus.TIMEOUT})
NOT_EVALUATED = frozenset({MutantStatus.ERROR, MutantStatus.IGNORED, MutantStatus.EQUIVALENT, MutantStatus.UNKNOWN})


@dataclass(frozen=True)
class MutantRecord:
    mutant_id: str
    status: MutantStatus
    native_status: str
    path: str | None = None
    line: int | None = None
    operator: str | None = None
    replacement: str | None = None
    description: str | None = None
    killed_by: tuple[str, ...] = ()
    duration_ms: float | None = None


@dataclass
class MutationRun:
    """Normalized mutation-tool evidence. Fields a tool does not provide stay None/empty."""

    source: str
    tool: str | None = None
    tool_version: str | None = None
    per_mutant: bool = True
    mutants: list[MutantRecord] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)  # MutantStatus value -> count
    sources: dict[str, str] = field(default_factory=dict)  # mutated file -> source text the tool saw
    limitations: list[str] = field(default_factory=list)
    error: str | None = None
    matches_state: bool | None = None  # None: the report cannot be tied to the measured state

    def count(self, status: MutantStatus) -> int:
        return self.counts.get(status.value, 0)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    @property
    def evaluated(self) -> int:
        return sum(n for s, n in self.counts.items() if MutantStatus(s) not in NOT_EVALUATED)

    def survivors(self) -> list[MutantRecord]:
        return [m for m in self.mutants if m.status is MutantStatus.SURVIVED]


@dataclass(frozen=True)
class ArtifactCheck:
    name: str  # build / install / import / tests ...
    status: StageStatus
    command: str | None = None
    duration_s: float | None = None
    detail: str = ""


@dataclass
class ArtifactEvidence:
    """Evidence that a built deliverable (not the source tree) works."""

    adapter_id: str
    kind: str
    status: StageStatus
    artifact: str | None = None
    sha256: str | None = None
    checks: list[ArtifactCheck] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    omitted_files: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    fidelity: dict[str, str] = field(default_factory=dict)  # dimension -> status: what this evidence proves


@dataclass(frozen=True)
class BudgetDecision:
    """Why a piece of expensive evidence was (or was not) produced."""

    stage: str
    decision: str  # EXECUTED / REUSED / NOT_RUN / BLOCKED
    reason: str


@dataclass(frozen=True)
class StabilityRecord:
    invocation_id: str
    outcomes: tuple["Outcome | None", ...]  # first execution first; never replaced by later ones
    durations_s: tuple[float | None, ...]
    verdict: str  # history.Stability value for this run's attempts


@dataclass
class StabilityEvidence:
    attempts: int = 0
    records: list[StabilityRecord] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    messages: dict[str, tuple] = field(default_factory=dict)  # failure messages per attempt (for fingerprints)


@dataclass(frozen=True)
class TestInvocation:
    """One concrete runnable case as reported by a native runner.

    declaration -> materialization -> invocation is preserved: an inherited or shared
    declaration can materialize in many suites, each with many parameter invocations.
    """

    invocation_id: str
    declaration_id: str
    materialization_id: str
    parameters_id: str | None = None
    markers: tuple[str, ...] = ()
    outcome: Outcome | None = None
    duration_s: float | None = None
    inherited: bool = False
    custom: bool = False
    message: str | None = None
    source_paths: tuple[str, ...] = ()  # project files that define this invocation
    attempts: int | None = None  # runner-reported attempts (retries); the outcome is the final one


@dataclass
class RunEvidence:
    """Normalized native runner evidence (collection or execution)."""

    adapter_id: str
    mode: str
    status: StageStatus
    invocations: list[TestInvocation] = field(default_factory=list)
    collection_errors: list[str] = field(default_factory=list)
    deselected: list[str] = field(default_factory=list)
    exit_code: int | None = None
    wall_clock_s: float | None = None
    command: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    coverage: "CoverageSummary | None" = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TestDefinition:
    node_id: str
    path: str
    name: str
    assertion_kinds: tuple[str, ...] = ()
    smoke_like: bool = False
    negative_dims: tuple[str, ...] = ()
    error_types: tuple[str, ...] = ()
    async_unobserved: bool = False


@dataclass(frozen=True)
class TestCompositionRelation:
    declaration_id: str
    materialization_id: str
    relation: str
    source_path: str
    declaration_class: str | None = None
    materialization_class: str | None = None
    assertion_kinds: tuple[str, ...] = ()
    evidence_tier: str = "E1"
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class CoverageSummary:
    """Coverage totals. ``counts`` keeps covered/total per kind (line, branch, method...) when known."""

    line_percent: float | None = None
    branch_percent: float | None = None
    source: str | None = None
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    tool: str | None = None
    scope: str | None = None
    limitations: tuple[str, ...] = ()
    error: str | None = None
    origin: str | None = None  # MEASURED (an engine run) or INGESTED (a report read by Assertiva)
    product_counts: dict[str, dict[str, int]] = field(default_factory=dict)  # counts without test files, when per-file data exists
    files: int | None = None
    test_files: int | None = None

    def percent(self, kind: str) -> float | None:
        count = self.counts.get(kind)
        if count and count["total"]:
            return round(count["covered"] * 100.0 / count["total"], 4)
        return {"line": self.line_percent, "branch": self.branch_percent}.get(kind)


@dataclass(frozen=True)
class Finding:
    code: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    severity: str | None = None  # set by the producing adapter for its own findings
    recommendation: str | None = None
