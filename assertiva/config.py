"""Optional configuration. Declarative settings come from the project; consent never does.

`.assertiva.toml` at the project root (or `[tool.assertiva]` in pyproject.toml) may only describe the project:

    [tests]
    runners = ["unittest"]  # when detection cannot know: pytest, unittest, django, jest, vitest, playwright, maven
    timeout_s = 1800        # per test run (default 900; Maven 1200)

Consent to effects outside the disposable copy is the user's, in `<ASSERTIVA_HOME>/consent.toml`, outside every
project: a cloned repository cannot authorize its own commands or unlock the user's credentials.

    [[project]]
    root = "/home/me/src/shop"
    authorize = ["python manage.py migrate"]  # exact commands (a check id is a position a later commit can reuse)
    env = ["DATABASE_URL"]                    # withheld variables the tests need; connections reach local hosts only

Nothing is required: detection works without either file. Unknown keys are reported, never guessed.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FILE = ".assertiva.toml"
CONSENT = "consent.toml"
_KNOWN = {"tests": {"runners", "timeout_s"}}
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
        return bool(check.command) and check.command.strip() in self.authorize


def _strings(value, where: str, problems: list[str]) -> tuple[str, ...]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(v.strip() for v in value if v.strip())
    problems.append(f"{where} must be a list of strings; ignored")
    return ()


def load_config(root: str | Path) -> ProjectConfig:
    root = Path(root)
    data, source = None, None
    authorize, env, consent_problems = _consent(root)  # the user's, whatever the project's file says
    try:
        if (root / FILE).is_file():
            data, source = tomllib.loads((root / FILE).read_text(encoding="utf-8")), FILE
        elif (root / "pyproject.toml").is_file():
            tool = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8")).get("tool", {})
            if isinstance(tool, dict) and "assertiva" in tool:
                data, source = tool["assertiva"], "pyproject.toml [tool.assertiva]"
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return ProjectConfig(source=FILE, authorize=authorize, env=env,
                             problems=(f"configuration could not be read: {exc}"[:200], *consent_problems))
    if not isinstance(data, dict):
        return ProjectConfig(authorize=authorize, env=env, problems=tuple(consent_problems))
    execution = data.get("execution")
    problems = [f"unknown section [{name}] ignored" for name in data if name not in _KNOWN and name != "execution"]
    if isinstance(execution, dict):
        problems += [f"execution.{key} is not read from the project; consent belongs in <ASSERTIVA_HOME>/{CONSENT}" for key in execution]
    elif execution is not None:
        problems.append(f"[execution] is not read from the project; consent belongs in <ASSERTIVA_HOME>/{CONSENT}")
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
        source=source, authorize=authorize, env=env,
        runners=tuple(name for name in runners if name in RUNNERS),
        timeout_s=float(timeout) if timeout is not None else None,
        problems=tuple(problems + consent_problems),
    )


def _consent(root: Path) -> tuple[tuple[str, ...], tuple[str, ...], list[str]]:
    """The user's consent for this project (authorized commands, passed-through variables), from outside it."""
    from .workspace import assertiva_home

    path = assertiva_home() / CONSENT
    problems: list[str] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return (), (), [f"{CONSENT} could not be read: {exc}"[:200]]
    target = str(Path(root).resolve()).replace("\\", "/").rstrip("/").casefold()
    for entry in data.get("project", []) if isinstance(data.get("project"), list) else []:
        if isinstance(entry, dict) and str(Path(str(entry.get("root", ""))).resolve()).replace("\\", "/").rstrip("/").casefold() == target:
            return (_strings(entry.get("authorize", []), "consent authorize", problems),
                    _strings(entry.get("env", []), "consent env", problems), problems)
    return (), (), problems
