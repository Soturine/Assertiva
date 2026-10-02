from __future__ import annotations

import re
import shlex
from pathlib import Path

from .models import CiPytestInvocation

_RUN_LINE = re.compile(r"^(?P<indent>\s*)(?:-\s*)?run\s*:\s*(?P<value>.*)$")
_SHELL_BREAKS = {"&&", "||", ";", "|"}


def _workflow_commands(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    commands, i = [], 0
    while i < len(lines):
        match = _RUN_LINE.match(lines[i])
        if not match:
            i += 1
            continue
        value = match.group("value").strip()
        indent = len(match.group("indent"))
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            block = []
            i += 1
            while i < len(lines):
                raw = lines[i]
                if raw.strip() and len(raw) - len(raw.lstrip()) <= indent:
                    break
                block.append(raw.strip())
                i += 1
            commands.append("\n".join(x for x in block if x))
            continue
        if value:
            commands.append(value)
        i += 1
    return commands


def _pytest_tail(tokens: list[str]):
    for i, token in enumerate(tokens):
        if token == "pytest" or token.endswith("/pytest") or token.endswith("\\pytest"):
            return tokens[i + 1:]
        if token == "-m" and i > 0 and tokens[i - 1] in {"python", "python3", "py"}:
            if i + 1 < len(tokens) and tokens[i + 1] == "pytest":
                return tokens[i + 2:]
    return None


def _extract_scopes(command: str):
    try:
        tokens = shlex.split(command.replace("\n", " "), posix=True)
    except ValueError:
        return None
    tail = _pytest_tail(tokens)
    if tail is None:
        return None
    scopes, skip = [], False
    options_with_values = {"-k","-m","--maxfail","--tb","--junitxml","--junit-xml","--ignore","--ignore-glob","--rootdir","--confcutdir","--basetemp"}
    for token in tail:
        if token in _SHELL_BREAKS:
            break
        if skip:
            skip = False
            continue
        if token in options_with_values:
            skip = True
            continue
        if token.startswith("-"):
            continue
        normalized = token.replace("\\", "/").lstrip("./")
        if normalized.startswith(("tests/", "test/")) or normalized in {"tests","test"} or normalized.endswith(".py"):
            scopes.append(normalized.rstrip("/"))
    return tuple(dict.fromkeys(scopes))


def discover_github_actions_pytest(root: str | Path) -> list[CiPytestInvocation]:
    root = Path(root)
    workflows = root / ".github" / "workflows"
    if not workflows.exists():
        return []
    out = []
    for path in sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")]):
        for command in _workflow_commands(path):
            scopes = _extract_scopes(command)
            if scopes is not None:
                out.append(CiPytestInvocation(str(path.relative_to(root)).replace("\\","/"), command, scopes))
    return out


def path_selected_by_ci(path: str, invocations: list[CiPytestInvocation]) -> bool:
    normalized = path.replace("\\","/").lstrip("./")
    for inv in invocations:
        if inv.runs_all_tests:
            return True
        for scope in inv.scopes:
            s = scope.replace("\\","/").lstrip("./").rstrip("/")
            if normalized == s or normalized.startswith(s + "/"):
                return True
    return False
