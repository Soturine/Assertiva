from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class VerificationKind(str, Enum):
    TEST = "TEST"
    LINT = "LINT"
    FORMAT = "FORMAT"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    TYPECHECK = "TYPECHECK"
    COVERAGE = "COVERAGE"
    MUTATION = "MUTATION"
    BUILD = "BUILD"
    PACKAGE = "PACKAGE"
    SCHEMA = "SCHEMA"
    MIGRATION = "MIGRATION"
    GENERATED_CODE = "GENERATED_CODE"
    LOCALIZATION = "LOCALIZATION"
    SECURITY = "SECURITY"
    DEPENDENCY = "DEPENDENCY"
    CONTAINER = "CONTAINER"
    STARTUP = "STARTUP"
    HEALTH = "HEALTH"
    DEPLOY = "DEPLOY"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


class VerificationOrigin(str, Enum):
    LOCAL = "LOCAL"
    HOOK = "HOOK"
    CI = "CI"
    BUILD = "BUILD"
    PACKAGE = "PACKAGE"
    DEPLOY = "DEPLOY"
    DECLARED = "DECLARED"
    OBSERVED = "OBSERVED"
    UNKNOWN = "UNKNOWN"


class GateMode(str, Enum):
    BLOCKING = "BLOCKING"
    ADVISORY = "ADVISORY"
    ALLOWED_FAILURE = "ALLOWED_FAILURE"
    UNKNOWN = "UNKNOWN"


class SupportLevel(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VerificationCheck:
    check_id: str
    kind: VerificationKind
    origin: VerificationOrigin
    gate: GateMode = GateMode.UNKNOWN
    command: str | None = None
    tool: str | None = None
    scope: tuple[str, ...] = ()
    source: str | None = None
    adapter_id: str | None = None
    evidence_tier: str | None = None
    limitations: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationSurface:
    checks: list[VerificationCheck] = field(default_factory=list)

    def add(self, check: VerificationCheck) -> None:
        if any(existing.check_id == check.check_id for existing in self.checks):
            raise ValueError(f"duplicate verification check id: {check.check_id}")
        self.checks.append(check)

    def by_origin(self, origin: VerificationOrigin) -> list[VerificationCheck]:
        return [check for check in self.checks if check.origin is origin]

    def by_kind(self, kind: VerificationKind) -> list[VerificationCheck]:
        return [check for check in self.checks if check.kind is kind]

    def blocking(self) -> list[VerificationCheck]:
        return [check for check in self.checks if check.gate is GateMode.BLOCKING]

    def ids(self) -> set[str]:
        return {check.check_id for check in self.checks}


def verification_gap(
    declared_or_local: Iterable[VerificationCheck],
    delivery: Iterable[VerificationCheck],
) -> set[str]:
    expected = {check.check_id for check in declared_or_local}
    observed = {check.check_id for check in delivery}
    return expected - observed
