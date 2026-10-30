"""Capability-driven adapters for verification sources.

The core asks adapters what they support; it never branches on a tool name.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from assertiva.verification import SupportLevel


def surface_adapters() -> list:
    """Adapters that discover declared/observed verification checks."""
    from .azure_pipelines import AzurePipelinesAdapter
    from .github_actions import GitHubActionsAdapter
    from .gitlab_ci import GitLabCiAdapter
    from .jenkins import JenkinsAdapter
    from .maven import MavenBuildSurfaceAdapter
    from .package_scripts import PackageScriptsAdapter
    from .pre_commit import PreCommitAdapter

    return [GitHubActionsAdapter(), AzurePipelinesAdapter(), GitLabCiAdapter(), JenkinsAdapter(),
            PreCommitAdapter(), PackageScriptsAdapter(), MavenBuildSurfaceAdapter()]


def _python_package(python=None):
    from .python_package import PythonPackageAdapter

    return PythonPackageAdapter(python=python)


def _pytest(python=None):
    from .pytest_native import PytestNativeAdapter

    return PytestNativeAdapter(python=python)


def _unittest(python=None):
    from .unittest_native import UnittestAdapter

    return UnittestAdapter(python=python)


def _django(python=None):
    from .unittest_native import DjangoAdapter

    return DjangoAdapter(python=python)


def _jest(python=None):
    from .jest import JestAdapter

    return JestAdapter(python=python)


def _vitest(python=None):
    from .vitest import VitestAdapter

    return VitestAdapter(python=python)


def _node_test(python=None):
    from .node_test import NodeTestAdapter

    return NodeTestAdapter(python=python)


def _playwright(python=None):
    from .playwright import PlaywrightAdapter

    return PlaywrightAdapter(python=python)


def _gradle(python=None):
    from .gradle import GradleAdapter

    return GradleAdapter(python=python)


def _maven(python=None):
    from .maven import MavenAdapter

    return MavenAdapter(python=python)


# Plain lists of factories (called with the target interpreter); no plugin machinery.
RUNNER_FACTORIES = [_pytest, _unittest, _django, _jest, _vitest, _node_test, _playwright, _maven, _gradle]
ARTIFACT_FACTORIES = [_python_package]


def impact_adapters(root: str | Path) -> list:
    """Adapters that relate a project's files to its tests (impact edges)."""
    from .python_impact import PythonImpactAdapter

    return [PythonImpactAdapter()]


def component_adapters(root: str | Path) -> list:
    """Adapters that read explicit workspace layouts (components and declared dependencies)."""
    from .workspaces import NpmWorkspacesAdapter, PythonProjectsAdapter

    return [NpmWorkspacesAdapter(), PythonProjectsAdapter()]


# A run-wide limit chosen by the caller (`--timeout-s`), never written into the audited project. Precedence: this,
# then the project's `[tests] timeout_s`, then the adapter's default; the source is recorded with each run.
_TIMEOUT_OVERRIDE: list[float] = []


@contextmanager
def timeout_override(seconds: float | None):
    """Within this block every runner and artifact adapter uses ``seconds`` as its per-run limit (None: no override)."""
    if seconds is None:
        yield
        return
    _TIMEOUT_OVERRIDE.append(float(seconds))
    try:
        yield
    finally:
        _TIMEOUT_OVERRIDE.pop()


def current_timeout(default: float) -> float:
    """The caller's run-wide limit when one is set, else ``default`` (for commands run outside an adapter)."""
    return _TIMEOUT_OVERRIDE[-1] if _TIMEOUT_OVERRIDE else default


def _limit(adapters: list, configured: float | None = None) -> list:
    for adapter in adapters:
        if _TIMEOUT_OVERRIDE:
            adapter.timeout_s, adapter.timeout_source = _TIMEOUT_OVERRIDE[-1], "command line (--timeout-s)"
        elif configured:
            adapter.timeout_s, adapter.timeout_source = configured, "project configuration ([tests] timeout_s)"
        else:
            adapter.timeout_source = "adapter default"
    return adapters


def artifact_adapters(root: str | Path, python: str | None = None) -> list:
    """Adapters that build and verify a deliverable artifact for the project at ``root``."""
    candidates = [factory(python=python) for factory in ARTIFACT_FACTORIES]
    return _limit([adapter for adapter in candidates if adapter.supports(Path(root)) is SupportLevel.SUPPORTED])


def runner_name(adapter) -> str:
    """The runner's name as a project configuration names it (`tests.runners`)."""
    return getattr(adapter, "runner", adapter.adapter_id.removesuffix("-native"))


def runner_adapters(root: str | Path, python: str | None = None) -> list:
    """Executable test-runner adapters for the project at ``root``: the configured runners (`.assertiva.toml`
    `[tests] runners`) when it names them, otherwise those that recognize the project."""
    from assertiva.config import load_config

    config = load_config(root)
    candidates = [factory(python=python) for factory in RUNNER_FACTORIES]
    if config.runners:
        chosen = [adapter for adapter in candidates if runner_name(adapter) in config.runners]
    else:
        chosen = [adapter for adapter in candidates if adapter.supports(Path(root)) is SupportLevel.SUPPORTED]
    return _limit(chosen, config.timeout_s)


def static_providers(adapters: list) -> list:
    """Adapters whose static analysis to use: one per ``static_family`` (several runners can share one)."""
    seen, out = set(), []
    for adapter in adapters:
        family = getattr(adapter, "static_family", adapter.adapter_id)
        if family not in seen:
            seen.add(family)
            out.append(adapter)
    return out
