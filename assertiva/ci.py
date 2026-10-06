from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CiPytestInvocation:
    workflow: str
    command: str
    scopes: tuple[str, ...] = ()

    @property
    def runs_all_tests(self) -> bool:
        return not self.scopes


_OPTIONS_WITH_VALUES = {
    "-k", "-m", "-c", "-p", "-o", "--maxfail", "--tb", "--junitxml", "--junit-xml", "--ignore", "--ignore-glob",
    "--rootdir", "--confcutdir", "--basetemp", "--deselect", "--cov", "--cov-report", "--durations",
}


def pytest_scopes(runner_args: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Positional path/node-id scopes of a pytest command line (empty = default scope)."""
    scopes, skip = [], False
    for token in runner_args:
        if skip:
            skip = False
            continue
        if token in _OPTIONS_WITH_VALUES:
            skip = True
            continue
        if token.startswith("-"):
            continue
        scopes.append(token.replace("\\", "/").removeprefix("./").rstrip("/"))
    return tuple(dict.fromkeys(scopes))


def discover_ci_pytest(root: str | Path) -> list[CiPytestInvocation]:
    """pytest invocations declared by any recognized CI configuration (the Verification Surface)."""
    from .verification import VerificationOrigin, discover_surface

    return [
        CiPytestInvocation(check.source.split("#")[0], check.command, pytest_scopes(check.metadata.get("runner_args", ())))
        for check in discover_surface(Path(root)).by_origin(VerificationOrigin.CI)
        if check.tool == "pytest" and check.command
    ]


def path_selected_by_ci(path: str, invocations: list[CiPytestInvocation]) -> bool:
    normalized = path.replace("\\", "/").removeprefix("./")
    for inv in invocations:
        if inv.runs_all_tests:
            return True
        for scope in inv.scopes:
            s = scope.split("::")[0].rstrip("/")
            if normalized == s or normalized.startswith(s + "/"):
                return True
    return False
