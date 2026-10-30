"""Tool-call guard for semantic evals: the workspace boundary enforced outside the evaluated model.

A prompt can ask an agent to stay in its workspace and leave private files alone; only a check on each tool call
can refuse the attempt. ``decide`` answers allow/deny for one tool call from a policy written by ``semantic.py
prepare`` (``guard.json``: the workspace, extra readable folders, the private files of the fixture). Run as a hook
(Claude Code ``PreToolUse``: the call arrives as JSON on stdin) it exits 2 to refuse, says why on stderr and appends
the refusal to ``guard-log.jsonl`` beside the policy, which ``semantic.py record`` reads:

    python evals/guard.py PATH/TO/guard.json  < tool-call.json

Refused: network tools; a path that resolves outside the workspace and the extra folders (``..``, absolute paths,
``~``, environment variables); any reference to a private file, by path, by name or by a wildcard that matches it.
A shell command is read token by token; a token that is not a path is not guessed at. This is a boundary for evals,
not a sandbox: a process the agent starts can still do what the operating system lets it do.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path, PurePosixPath

NETWORK_TOOLS = frozenset({"WebFetch", "WebSearch"})
PATH_KEYS = ("file_path", "path", "notebook_path")
SHELL_TOOLS = frozenset({"Bash", "PowerShell"})
_VARIABLE = re.compile(r"\$\{?[A-Za-z_]\w*\}?|%[A-Za-z_]\w*%|\$env:[A-Za-z_]\w*", re.I)


def _resolve(token: str, workspace: Path) -> Path:
    path = Path(os.path.expanduser(token))
    return (path if path.is_absolute() else workspace / path).resolve(strict=False)


def _inside(path: Path, folders: list[Path]) -> bool:
    return any(path == folder or folder in path.parents for folder in folders)


def _shell_tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        tokens = command.split()
    out = []
    for token in tokens:  # `--file=../x`, `>out`, `2>../log`: the path is what follows the operator
        out += [part for part in re.split(r"(?:^[0-9]*[<>]+|=)", token) if part]
    return out


def _looks_like_path(token: str) -> bool:
    return any(c in token for c in "/\\") or token.startswith(("~", ".")) or bool(re.match(r"^[A-Za-z]:", token))


def decide(tool: str, tool_input: dict, policy: dict) -> tuple[bool, str]:
    """(allowed, reason) for one tool call under ``policy``."""
    workspace = Path(policy["workspace"]).resolve(strict=False)
    readable = [workspace, *(Path(p).resolve(strict=False) for p in policy.get("readable", ()))]
    private = [Path(p).resolve(strict=False) for p in policy.get("private", ())]
    if tool in NETWORK_TOOLS:
        return False, f"{tool}: network access is outside the eval's tools"
    tokens: list[str] = []
    for key in PATH_KEYS:
        if isinstance(tool_input.get(key), str):
            tokens.append(tool_input[key])
    explicit = len(tokens)  # these are paths by definition; shell tokens only when they look like one
    if tool == "Glob" and isinstance(tool_input.get("pattern"), str):
        tokens.append(tool_input["pattern"])
        explicit += 1
    if tool in SHELL_TOOLS:
        command = str(tool_input.get("command", ""))
        if _VARIABLE.search(command):
            return False, "the command expands environment variables, so the paths it reaches cannot be checked"
        tokens += _shell_tokens(command)
    for index, token in enumerate(tokens):
        pure = PurePosixPath(token.replace("\\", "/"))
        wildcard = any(c in pure.name for c in "*?[")
        folder = _resolve(str(pure.parent), workspace) if wildcard else None
        if any(pure.name == secret.name or (wildcard and folder == secret.parent and fnmatch.fnmatchcase(secret.name, pure.name))
               for secret in private):
            return False, f"{token}: refers to a file the project marks as private"
        if index >= explicit and not _looks_like_path(token):
            continue
        resolved = _resolve(re.split(r"[*?\[]", token, maxsplit=1)[0] or ".", workspace)
        if resolved in private:
            return False, f"{token}: a file the project marks as private"
        if not _inside(resolved, readable):
            return False, f"{token}: outside the workspace"
    return True, "inside the workspace"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    policy_path = Path(argv[0])
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    call = json.loads(sys.stdin.read() or "{}")
    tool, tool_input = str(call.get("tool_name", "")), call.get("tool_input") or {}
    allowed, reason = decide(tool, tool_input, policy)
    if allowed:
        return 0
    with (policy_path.parent / "guard-log.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps({"tool": tool, "input": tool_input, "reason": reason}) + "\n")
    print(f"refused by the eval guard: {reason}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
