from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TestDefinition:
    node_id: str
    path: str
    name: str
    assertion_kinds: tuple[str, ...] = ()
    smoke_like: bool = False


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
class CiPytestInvocation:
    workflow: str
    command: str
    scopes: tuple[str, ...] = ()

    @property
    def runs_all_tests(self) -> bool:
        return not self.scopes


@dataclass(frozen=True)
class CoverageSummary:
    line_percent: float | None = None
    branch_percent: float | None = None
    source: str | None = None


@dataclass(frozen=True)
class Finding:
    code: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class PytestAssuranceReport:
    root: Path
    tests: list[TestDefinition]
    ci_invocations: list[CiPytestInvocation]
    findings: list[Finding]
    coverage: CoverageSummary | None = None
    materializations: list[TestCompositionRelation] = field(default_factory=list)

    @property
    def smoke_like_count(self) -> int:
        return sum(test.smoke_like for test in self.tests)

    @property
    def smoke_ratio(self) -> float:
        return self.smoke_like_count / len(self.tests) if self.tests else 0.0

    @property
    def expected_error_count(self) -> int:
        return sum("EXPECTED_ERROR_CONTRACT" in test.assertion_kinds for test in self.tests)

    def has_finding(self, code: str) -> bool:
        return any(f.code == code for f in self.findings)
