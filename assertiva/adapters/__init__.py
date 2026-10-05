"""Capability-driven adapters for verification sources.

The core asks adapters what they support; it never branches on a tool name.
"""

from __future__ import annotations

from pathlib import Path

from assertiva.verification import SupportLevel


def surface_adapters() -> list:
    """Adapters that discover declared/observed verification checks."""
    from .github_actions import GitHubActionsAdapter
    from .pre_commit import PreCommitAdapter

    return [GitHubActionsAdapter(), PreCommitAdapter()]


def runner_adapters(root: str | Path, python: str | None = None) -> list:
    """Executable test-runner adapters that support the project at ``root``."""
    from .pytest_native import PytestNativeAdapter

    candidates = [PytestNativeAdapter(python=python)]
    return [adapter for adapter in candidates if adapter.supports(Path(root)) is SupportLevel.SUPPORTED]
