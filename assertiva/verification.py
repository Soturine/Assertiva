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


def discover_surface(root) -> VerificationSurface:
    """Run every surface adapter that supports the project."""
    from pathlib import Path

    from .adapters import surface_adapters

    surface = VerificationSurface()
    for adapter in surface_adapters():
        if adapter.supports(Path(root)) is SupportLevel.SUPPORTED:
            for check in adapter.discover(Path(root)):
                surface.add(check)
    return surface


def _covers(delivery: VerificationCheck, local: VerificationCheck) -> bool:
    if local.tool and delivery.tool == local.tool:
        return True
    runs = delivery.metadata.get("runs_hooks") or []
    return "*" in runs or local.metadata.get("hook_id") in runs


def surface_findings(surface: VerificationSurface) -> list:
    """Generic parity findings: local/declared checks versus delivery (CI) checks."""
    from .models import Finding

    findings: list = []
    delivery = surface.by_origin(VerificationOrigin.CI)
    local = surface.by_origin(VerificationOrigin.HOOK) + surface.by_origin(VerificationOrigin.LOCAL)
    if not delivery:
        findings.append(
            Finding(
                "NO_DELIVERY_PIPELINE_OBSERVED",
                "No CI/CD configuration was recognized. Delivery-path verification is UNKNOWN, not absent.",
                {"recognized_local_checks": len(local)},
            )
        )
        return findings
    missing = [check.check_id for check in local if not any(_covers(ci, check) for ci in delivery)]
    if missing:
        findings.append(
            Finding(
                "LOCAL_CHECK_NOT_OBSERVED_IN_CI",
                "Local/hook checks were not observed in CI; a green pipeline does not cover them.",
                {"checks": missing, "matching": "by tool identity or CI hook runner; renamed tools may be missed"},
            )
        )
    if local:
        ci_only = [
            check.command or check.tool or check.check_id
            for check in delivery
            if check.kind is not VerificationKind.UNKNOWN or check.command
            if not any(check.tool == item.tool for item in local) and not check.metadata.get("runs_hooks")
        ]
        if ci_only:
            findings.append(
                Finding(
                    "CI_ONLY_CHECK",
                    "CI runs checks no discovered local hook declares; local green is weaker than pipeline green.",
                    {"checks": ci_only},
                )
            )
    unknown = [check.check_id for check in surface.checks if check.kind is VerificationKind.UNKNOWN]
    if unknown:
        findings.append(
            Finding(
                "UNCLASSIFIED_VERIFICATION",
                "Some checks could not be classified; they are preserved as UNKNOWN rather than guessed.",
                {"checks": unknown},
            )
        )
    return findings
