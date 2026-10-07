"""Command-line knowledge: which known tool a shell command invokes, and as what kind of check.

This table is adapter knowledge, not core policy. Anything not recognized is returned
as UNKNOWN with the command preserved; it is never guessed to be a test or a gate.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from assertiva.verification import VerificationKind as K

_SPLIT = re.compile(r"\s*(?:&&|\|\||;)\s*")
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_PYTHON = re.compile(r"^(?:python(?:\d+(?:\.\d+)?)?|py)$")
_PYTHON_OPTIONS_WITH_VALUES = {"-X", "-W", "--check-hash-based-pycs"}
_WRAPPERS = {("python", "-m"), ("python3", "-m"), ("py", "-m"), ("uv", "run"), ("poetry", "run"), ("pipenv", "run"), ("npx",), ("pnpm", "exec"), ("yarn",)}

# (tool, optional subcommand) -> kind. Subcommand None matches any.
_TOOLS: dict[tuple[str, str | None], K] = {
    ("pytest", None): K.TEST, ("py.test", None): K.TEST, ("unittest", None): K.TEST,
    ("jest", None): K.TEST, ("vitest", None): K.TEST, ("mocha", None): K.TEST,
    ("playwright", "test"): K.TEST, ("cypress", "run"): K.TEST,
    ("go", "test"): K.TEST, ("go", "vet"): K.STATIC_ANALYSIS, ("go", "build"): K.BUILD,
    ("cargo", "test"): K.TEST, ("cargo", "clippy"): K.LINT, ("cargo", "build"): K.BUILD, ("cargo", "fmt"): K.FORMAT,
    ("dotnet", "test"): K.TEST, ("dotnet", "build"): K.BUILD, ("dotnet", "format"): K.FORMAT,
    ("mvn", None): K.TEST, ("gradle", None): K.TEST, ("./gradlew", None): K.TEST, ("./mvnw", None): K.TEST,
    ("ruff", "format"): K.FORMAT, ("ruff", None): K.LINT, ("flake8", None): K.LINT, ("pylint", None): K.LINT,
    ("eslint", None): K.LINT, ("black", None): K.FORMAT, ("isort", None): K.FORMAT, ("prettier", None): K.FORMAT,
    ("mypy", None): K.TYPECHECK, ("pyright", None): K.TYPECHECK, ("tsc", None): K.TYPECHECK,
    ("bandit", None): K.SECURITY, ("semgrep", None): K.SECURITY,
    ("pip-audit", None): K.DEPENDENCY, ("safety", None): K.DEPENDENCY, ("npm", "audit"): K.DEPENDENCY,
    ("build", None): K.PACKAGE, ("twine", "check"): K.PACKAGE, ("npm", "pack"): K.PACKAGE,
    ("coverage", None): K.COVERAGE, ("mutmut", None): K.MUTATION, ("cosmic-ray", None): K.MUTATION, ("stryker", None): K.MUTATION,
    ("docker", "build"): K.CONTAINER, ("alembic", "upgrade"): K.MIGRATION,
    ("npm", "test"): K.TEST, ("npm", "run"): K.UNKNOWN, ("pre-commit", "run"): K.CUSTOM,
    ("compileall", None): K.STATIC_ANALYSIS,
    ("twine", "upload"): K.DEPLOY, ("docker", "push"): K.DEPLOY, ("kubectl", "apply"): K.DEPLOY, ("helm", "upgrade"): K.DEPLOY,
    ("helm", "install"): K.DEPLOY, ("gh", "release"): K.DEPLOY,
}
# Kinds whose recognized tools only read the (disposable) copy: reproducible without asking.
SAFE_KINDS = frozenset({K.LINT, K.FORMAT, K.TYPECHECK, K.STATIC_ANALYSIS, K.PACKAGE, K.BUILD})
_SHELL = re.compile(r"\$\{\{|&&|\|\||[;|<>`$*?]")
_MANAGE_PY = {"test": K.TEST, "check": K.STATIC_ANALYSIS, "migrate": K.MIGRATION, "makemigrations": K.MIGRATION, "compilemessages": K.LOCALIZATION}
_SETUP = {
    ("pip", "install"), ("pip", "download"), ("venv", None), ("cd", None), ("echo", None), ("mkdir", None), ("export", None),
    ("source", None), ("npm", "ci"), ("npm", "install"), ("apt-get", None), ("sudo", None), ("uv", "sync"), ("uv", "pip"),
    ("poetry", "install"), ("pipx", "install"), ("ls", None), ("cat", None), ("set", None),
}


@dataclass(frozen=True)
class CommandClass:
    kind: K
    tool: str
    runner_args: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    setup_only: bool = False
    unclassified: tuple[str, ...] = ()


def _tokens(segment: str) -> list[str]:
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    while tokens and _ENV_ASSIGNMENT.match(tokens[0]):
        tokens = tokens[1:]
    if tokens and ("/" in tokens[0] or "\\" in tokens[0]) and not tokens[0].startswith("./"):
        tokens[0] = PurePosixPath(tokens[0].replace("\\", "/")).name  # .venv/bin/pytest -> pytest
    if tokens and tokens[0].endswith(".exe"):
        tokens[0] = tokens[0][:-4]
    if tokens and _PYTHON.match(tokens[0]):  # python -X utf8 -u -m unittest -> python -m unittest
        rest, i = tokens[1:], 0
        while i < len(rest) and rest[i].startswith("-") and rest[i] not in {"-m", "-c", "-"}:
            i += 2 if rest[i] in _PYTHON_OPTIONS_WITH_VALUES else 1
        tokens = ["python", *rest[i:]]
    changed = True
    while changed and tokens:
        changed = False
        for wrapper in _WRAPPERS:
            if tuple(tokens[: len(wrapper)]) == wrapper and len(tokens) > len(wrapper):
                tokens, changed = tokens[len(wrapper):], True
                break
    return tokens


def _classify_segment(segment: str) -> tuple[K | None, str, tuple[str, ...], dict[str, Any]] | None:
    """None for setup; (None, ...) for unknown; else (kind, tool, args, metadata)."""
    tokens = _tokens(segment)
    if tokens[:2] == ["coverage", "run"] and "-m" in tokens[2:-1]:  # coverage run [opts] -m pytest ... runs pytest, measured
        inner = tokens[tokens.index("-m", 2) + 1:]
        classified = _classify_segment(" ".join(shlex.quote(t) for t in ["python", "-m", *inner]))
        if classified and classified[0] not in (None, K.UNKNOWN):
            kind, tool, args, metadata = classified
            return kind, tool, args, {**metadata, "measured_by": "coverage"}
    if not tokens:
        return None
    head, sub = tokens[0], (tokens[1] if len(tokens) > 1 else None)
    if (head, sub) in _SETUP or (head, None) in _SETUP:
        return None
    if head in {"python", "python3", "py"} and sub and sub.endswith("manage.py") and len(tokens) > 2:
        kind = _MANAGE_PY.get(tokens[2])
        if kind:
            return kind, f"manage.py {tokens[2]}", tuple(tokens[3:]), {}
    if sub is not None and (head, sub) in _TOOLS:
        kind, tool, args = _TOOLS[(head, sub)], f"{head} {sub}", tuple(tokens[2:])
        if head == "pre-commit":
            hook_ids = [t for t in tokens[2:] if not t.startswith("-")]
            return kind, "pre-commit", args, {"runs_hooks": hook_ids or ["*"]}
        return kind, tool, args, {}
    if (head, None) in _TOOLS:
        return _TOOLS[(head, None)], head, tuple(tokens[1:]), {}
    return K.UNKNOWN, " ".join(tokens), (), {}


@dataclass(frozen=True)
class ReproductionPlan:
    argv: tuple[str, ...] | None
    needs_authorization: bool
    reason: str


def reproduction_plan(check, python: str) -> ReproductionPlan:
    """How (and whether) a discovered check may be reproduced locally in a disposable copy.

    DISCOVERED is not AUTHORIZED: only recognized, side-effect-free checks run without an
    explicit authorization; deploys never run; compound shell steps are not reproduced.
    """
    kind = check.kind
    if not check.command:
        return ReproductionPlan(None, False, "no command to reproduce (action or reusable workflow)")
    if kind is K.DEPLOY:
        return ReproductionPlan(None, False, "deploy/publish checks are never executed by Assertiva")
    lines = [line for line in check.command.splitlines() if line.strip()]
    if len(lines) != 1 or _SHELL.search(lines[0]):
        return ReproductionPlan(None, False, "compound shell step is not reproduced")
    if check.metadata.get("working_directory"):
        return ReproductionPlan(None, False, "working-directory is not reproduced")
    try:
        argv = shlex.split(lines[0], posix=True)
    except ValueError:
        return ReproductionPlan(None, False, "command could not be parsed")
    if argv and PurePosixPath(argv[0].replace("\\", "/")).name in {"python", "python3", "py", "python.exe"}:
        argv[0] = python
    return ReproductionPlan(tuple(argv), kind not in SAFE_KINDS, f"{kind.value} check")


def classify_command(command: str) -> CommandClass:
    segments = [s for line in command.splitlines() for s in _SPLIT.split(line.strip()) if s and not s.startswith("#")]
    classified = [(s, _classify_segment(s)) for s in segments]
    meaningful = [(s, c) for s, c in classified if c is not None]
    if not meaningful:
        return CommandClass(K.UNKNOWN, command.strip(), setup_only=True)
    known = [(s, c) for s, c in meaningful if c[0] is not K.UNKNOWN]
    unknown = tuple(s for s, c in meaningful if c[0] is K.UNKNOWN)
    if not known:
        return CommandClass(K.UNKNOWN, meaningful[0][1][1], unclassified=unknown)
    kind, tool, args, metadata = known[0][1]
    return CommandClass(kind, tool, args, metadata, unclassified=unknown)
