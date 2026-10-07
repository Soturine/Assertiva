"""Identity of the Assertiva runtime that produced a report (not of the audited project)."""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from . import __version__, _checkout_version


def _git(checkout: Path, *args: str) -> str | None:
    try:
        done = subprocess.run(["git", "--no-optional-locks", "-C", str(checkout), *args], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


@lru_cache(maxsize=1)
def runtime_identity() -> dict:
    """Version, install kind and, for a source checkout, the git revision of the code that is running."""
    package = Path(__file__).resolve().parent
    checkout = package.parent
    from_checkout = _checkout_version() is not None
    identity: dict = {"version": __version__, "install": "source-checkout" if from_checkout else "installed-package",
                      "revision": None, "dirty": None}
    if from_checkout and (checkout / ".git").exists():
        identity["revision"] = _git(checkout, "rev-parse", "HEAD")
        status = _git(checkout, "status", "--porcelain", "--untracked-files=no", "--", "assertiva", "pyproject.toml")
        identity["dirty"] = None if status is None else bool(status)
    return identity
