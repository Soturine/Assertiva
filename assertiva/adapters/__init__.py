"""Capability-driven adapters for verification sources.

The core asks adapters what they support; it never branches on a tool name.
"""

from __future__ import annotations

from pathlib import Path

from assertiva.verification import SupportLevel


def surface_adapters() -> list:
    """Adapters that discover declared/observed verification checks."""
    from .github_actions import GitHubActionsAdapter
    from .maven import MavenBuildSurfaceAdapter
    from .package_scripts import PackageScriptsAdapter
    from .pre_commit import PreCommitAdapter

    return [GitHubActionsAdapter(), PreCommitAdapter(), PackageScriptsAdapter(), MavenBuildSurfaceAdapter()]


def _python_package(python=None):
    from .python_package import PythonPackageAdapter

    return PythonPackageAdapter(python=python)


def _pytest(python=None):
    from .pytest_native import PytestNativeAdapter

    return PytestNativeAdapter(python=python)


def _jest(python=None):
    from .jest import JestAdapter

    return JestAdapter(python=python)


def _playwright(python=None):
    from .playwright import PlaywrightAdapter

    return PlaywrightAdapter(python=python)


def _maven(python=None):
    from .maven import MavenAdapter

    return MavenAdapter(python=python)


# Plain lists of factories (called with the target interpreter); no plugin machinery.
RUNNER_FACTORIES = [_pytest, _jest, _playwright, _maven]
ARTIFACT_FACTORIES = [_python_package]


def impact_adapters(root: str | Path) -> list:
    """Adapters that relate a project's files to its tests (impact edges)."""
    from .python_impact import PythonImpactAdapter

    return [PythonImpactAdapter()]


def component_adapters(root: str | Path) -> list:
    """Adapters that read explicit workspace layouts (components and declared dependencies)."""
    from .workspaces import NpmWorkspacesAdapter, PythonProjectsAdapter

    return [NpmWorkspacesAdapter(), PythonProjectsAdapter()]


def artifact_adapters(root: str | Path, python: str | None = None) -> list:
    """Adapters that build and verify a deliverable artifact for the project at ``root``."""
    candidates = [factory(python=python) for factory in ARTIFACT_FACTORIES]
    return [adapter for adapter in candidates if adapter.supports(Path(root)) is SupportLevel.SUPPORTED]


def runner_adapters(root: str | Path, python: str | None = None) -> list:
    """Executable test-runner adapters that support the project at ``root``."""
    candidates = [factory(python=python) for factory in RUNNER_FACTORIES]
    return [adapter for adapter in candidates if adapter.supports(Path(root)) is SupportLevel.SUPPORTED]
