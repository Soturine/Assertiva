"""Optional project configuration: `.assertiva.toml` at the project root, or `[tool.assertiva]` in pyproject.toml.

Nothing is required: detection works without it. The file is the project owner's (a human-authored,
versioned file that an audit never writes), so it is where execution authorizations live. Unknown keys
are reported, never guessed.

    [tests]
    runners = ["unittest"]  # when detection cannot know: pytest, unittest, django, jest, vitest, playwright, maven
    timeout_s = 1800        # per test run (default 900; Maven 1200)

    [execution]
    authorize = ["gha:.github/workflows/ci.yml:test:3", "python manage.py migrate --check"]  # check ids or exact commands
    env = ["DATABASE_URL"]  # variables the tests need that look like credentials (withheld otherwise)
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FILE = ".assertiva.toml"
_KNOWN = {"execution": {"authorize", "env"}, "tests": {"runners", "timeout_s"}}
RUNNERS = ("pytest", "unittest", "django", "jest", "vitest", "playwright", "maven")


@dataclass(frozen=True)
class ProjectConfig:
    source: str | None = None
    authorize: tuple[str, ...] = ()
    env: tuple[str, ...] = ()
    runners: tuple[str, ...] = ()  # empty: detect from the project
    timeout_s: float | None = None
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
    tests = data.get("tests") or {}
    if not isinstance(tests, dict):
        problems.append("[tests] must be a table; ignored")
        tests = {}
    problems += [f"unknown key tests.{key} ignored" for key in tests if key not in _KNOWN["tests"]]
    runners = _strings(tests.get("runners", []), "tests.runners", problems)
    problems += [f"unknown runner {name!r} in tests.runners ignored" for name in runners if name not in RUNNERS]
    timeout = tests.get("timeout_s")
    if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0):
        problems.append("tests.timeout_s must be a positive number; ignored")
        timeout = None
    return ProjectConfig(
        source=source,
        authorize=_strings(execution.get("authorize", []), "execution.authorize", problems),
        env=_strings(execution.get("env", []), "execution.env", problems),
        runners=tuple(name for name in runners if name in RUNNERS),
        timeout_s=float(timeout) if timeout is not None else None,
        problems=tuple(problems),
    )
