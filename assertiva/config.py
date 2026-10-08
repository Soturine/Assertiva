"""Optional project configuration: `.assertiva.toml` at the project root, or `[tool.assertiva]` in pyproject.toml.

Nothing is required: detection works without it. The file is the project owner's (a human-authored,
versioned file that an audit never writes), so it is where execution authorizations live. Unknown keys
are reported, never guessed.

    [execution]
    authorize = ["gha:.github/workflows/ci.yml:test:3", "python manage.py migrate --check"]  # check ids or exact commands
    env = ["DATABASE_URL"]  # variables the tests need that look like credentials (withheld otherwise)
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FILE = ".assertiva.toml"
_KNOWN = {"execution": {"authorize", "env"}}


@dataclass(frozen=True)
class ProjectConfig:
    source: str | None = None
    authorize: tuple[str, ...] = ()
    env: tuple[str, ...] = ()
    problems: tuple[str, ...] = field(default=())

    def authorizes(self, check) -> bool:
        return check.check_id in self.authorize or (check.command or "").strip() in self.authorize


def _strings(value, where: str, problems: list[str]) -> tuple[str, ...]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(v.strip() for v in value if v.strip())
    problems.append(f"{where} must be a list of strings; ignored")
    return ()


def load_config(root: str | Path) -> ProjectConfig:
    root = Path(root)
    data, source = None, None
    try:
        if (root / FILE).is_file():
            data, source = tomllib.loads((root / FILE).read_text(encoding="utf-8")), FILE
        elif (root / "pyproject.toml").is_file():
            tool = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")).get("tool", {})
            if isinstance(tool, dict) and "assertiva" in tool:
                data, source = tool["assertiva"], "pyproject.toml [tool.assertiva]"
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return ProjectConfig(source=FILE, problems=(f"configuration could not be read: {exc}"[:200],))
    if not isinstance(data, dict):
        return ProjectConfig()
    problems = [f"unknown section [{name}] ignored" for name in data if name not in _KNOWN]
    execution = data.get("execution") or {}
    if not isinstance(execution, dict):
        problems.append("[execution] must be a table; ignored")
        execution = {}
    problems += [f"unknown key execution.{key} ignored" for key in execution if key not in _KNOWN["execution"]]
    return ProjectConfig(
        source=source,
        authorize=_strings(execution.get("authorize", []), "execution.authorize", problems),
        env=_strings(execution.get("env", []), "execution.env", problems),
        problems=tuple(problems),
    )
