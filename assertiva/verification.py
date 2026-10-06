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
    MIGRATION = "MIGRATION"
    LOCALIZATION = "LOCALIZATION"
    SECURITY = "SECURITY"
    DEPENDENCY = "DEPENDENCY"
    CONTAINER = "CONTAINER"
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


# --- delivery intelligence: matrix visibility and artifact lineage (declared evidence) ----------

_OS_FAMILY = (("windows", "windows"), ("macos", "macos"), ("mac", "macos"), ("ubuntu", "linux"), ("linux", "linux"),
              ("debian", "linux"), ("alpine", "linux"), ("centos", "linux"), ("fedora", "linux"))


def _merge(target: dict[str, list[str]], values: dict | None) -> None:
    for dim, items in (values or {}).items():
        for item in items:
            if item not in target.setdefault(dim, []):
                target[dim].append(item)


def delivery_matrix(surface: VerificationSurface, runner_adapters=()) -> dict[str, list[str]]:
    """Dimension -> values CI configuration states it runs (matrices, images, runner selections)."""
    covered: dict[str, list[str]] = {}
    for check in surface.by_origin(VerificationOrigin.CI):
        _merge(covered, check.metadata.get("matrix_values"))
        for adapter in runner_adapters:
            if hasattr(adapter, "ci_matrix_values"):
                _merge(covered, adapter.ci_matrix_values(check))
    return covered


def _value_covered(value: str, ci_values: list[str]) -> bool:
    value = str(value).lower()
    return any(ci == "*" or ci.lower() == value or ci.lower().startswith(value + ".") for ci in ci_values)


def matrix_findings(surface: VerificationSurface, declared: dict[str, dict], covered: dict[str, list[str]]) -> list:
    """Declared runtimes/targets versus what CI configuration selects. Gaps are findings, never a score."""
    from .models import Finding

    if not surface.by_origin(VerificationOrigin.CI):
        return []
    findings = []
    for dim, info in sorted(declared.items()):
        ci_values = covered.get(dim, [])
        if not ci_values:
            findings.append(Finding("MATRIX_UNVERIFIED", f"The project declares {dim} {', '.join(info['values'])} but no CI job states which {dim} it runs.",
                                    {"dimension": dim, "declared": info["values"], "source": info["source"]}))
            continue
        missing = [v for v in info["values"] if not _value_covered(v, ci_values)]
        if missing:
            findings.append(Finding("MATRIX_GAP", f"Declared {dim} {', '.join(missing)} is not selected by any CI job.",
                                    {"dimension": dim, "missing": missing, "ci": ci_values, "source": info["source"]}))
    families = {next((fam for key, fam in _OS_FAMILY if key in value.lower()), value.lower()) for value in covered.get("os", [])}
    if len(families) == 1 and not any("$" in value for value in covered.get("os", [])):
        findings.append(Finding("CI_SINGLE_OS", f"Every CI job that states an operating system runs on {families.pop()}; others are not evidenced.",
                                {"os": covered["os"]}, severity="info"))
    return findings


def artifact_lineage(surface: VerificationSurface, artifacts, delivered: dict[str, list[tuple[str, str]]], revision: str | None) -> tuple[list, list]:
    """SOURCE REVISION -> BUILD -> ARTIFACT -> TESTED -> PUBLISHED -> DEPLOYED, only as far as evidence goes."""
    from .models import Finding

    ci = surface.by_origin(VerificationOrigin.CI)
    deliveries = [c for c in ci if c.kind is VerificationKind.DEPLOY or (c.metadata.get("lifecycle") or {}).get("deploys")]
    findings, lineage = [], []
    for artifact in artifacts:
        candidates = delivered.get(artifact.artifact or "", [])
        lineage.append({
            "source_revision": revision, "build": "isolated build by Assertiva", "artifact": artifact.artifact, "sha256": artifact.sha256,
            "tested": artifact.status.value,
            "published": [c.check_id for c in deliveries if c.kind is VerificationKind.DEPLOY] or "NOT_DECLARED",
            "deployed": [c.check_id for c in deliveries if c.metadata.get("environment")] or "NOT_DECLARED",
            "delivered_candidates": [{"path": path, "sha256": sha} for path, sha in candidates],
        })
        differing = [path for path, sha in candidates if artifact.sha256 and sha != artifact.sha256]
        if differing:
            findings.append(Finding("TESTED_ARTIFACT_DIFFERS_FROM_DELIVERED",
                                    "An artifact with the tested artifact's name has different bytes; it is not the one Assertiva qualified.",
                                    {"tested": artifact.artifact, "tested_sha256": artifact.sha256, "differs": differing}))
    jobs: dict[str, list[VerificationCheck]] = {}
    for check in ci:
        jobs.setdefault(check.source or check.check_id, []).append(check)
    for job, checks in sorted(jobs.items()):
        publishes = [c for c in checks if c.kind is VerificationKind.DEPLOY]
        builds = [c for c in checks if c.kind in (VerificationKind.BUILD, VerificationKind.PACKAGE)]
        if publishes and builds and not any(c.kind is VerificationKind.TEST for c in checks):
            findings.append(Finding("PUBLISHED_ARTIFACT_NOT_QUALIFIED",
                                    "A CI job builds and publishes an artifact without running tests in that job.",
                                    {"job": job, "build": [c.command for c in builds], "publish": [c.command for c in publishes]}))
    if deliveries:
        findings.append(Finding("ARTIFACT_LINEAGE_UNKNOWN",
                                "Delivery steps are declared, but no evidence ties the published or deployed bytes to a tested artifact.",
                                {"deliveries": [c.command or c.tool or c.check_id for c in deliveries][:10]}))
    return lineage, findings
