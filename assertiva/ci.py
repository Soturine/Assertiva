from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CiPytestInvocation:
    workflow: str
    command: str
    scopes: tuple[str, ...] = ()
    # where the runner starts, relative to the repository root ("" = the root); scopes are relative to it
    base: str = ""

    @property
    def runs_all_tests(self) -> bool:
        return not self.scopes and not self.base

    @property
    def base_unresolved(self) -> bool:
        """The directory is an expression (`${{ matrix.dir }}`): where it runs is not known from configuration."""
        return "${{" in self.base or "$(" in self.base

    def root_scopes(self) -> tuple[str, ...]:
        """The scopes as repository paths: joined to the working directory (a base alone means everything under it)."""
        if not self.base:
            return self.scopes
        base = posixpath.normpath(self.base.replace("\\", "/")).removeprefix("./")
        base = "" if base == "." else base
        joined = [posixpath.normpath(posixpath.join(base, s)) if base else s for s in self.scopes or ("",)]
        return tuple(dict.fromkeys(("" if j == "." else j) for j in joined))


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


def unittest_scopes(runner_args: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Paths a `python -m unittest` command line selects (empty = discovery from the working directory)."""
    args = list(runner_args)
    if not args or args[0] == "discover" or args[0].startswith("-"):
        args = args[1:] if args and args[0] == "discover" else args
        start, positional, skip = None, [], None
        for token in args:
            if skip:
                start = token if skip in {"-s", "--start-directory"} else start
                skip = None
            elif token in {"-s", "--start-directory", "-p", "--pattern", "-t", "--top-level-directory", "-k"}:
                skip = token
            elif not token.startswith("-"):
                positional.append(token)
        start = start or (positional[0] if positional else ".")
        start = start.replace("\\", "/").removeprefix("./").rstrip("/")
        return () if start in {"", "."} else (start,)
    modules = [t for t in args if not t.startswith("-")]
    return tuple(dict.fromkeys(m.replace("\\", "/").removesuffix(".py").replace(".", "/") for m in modules))


def _ci_invocations(root: str | Path, tool: str, scopes) -> list[CiPytestInvocation]:
    from .verification import VerificationOrigin, discover_surface

    return [
        CiPytestInvocation(check.source.split("#")[0], check.command, scopes(check.metadata.get("runner_args", ())),
                           str(check.metadata.get("working_directory") or ""))
        for check in discover_surface(Path(root)).by_origin(VerificationOrigin.CI)
        if check.tool == tool and check.command
    ]


def discover_ci_pytest(root: str | Path) -> list[CiPytestInvocation]:
    """pytest invocations declared by any recognized CI configuration (the Verification Surface)."""
    return _ci_invocations(root, "pytest", pytest_scopes)


def discover_ci_unittest(root: str | Path) -> list[CiPytestInvocation]:
    """Python unittest invocations declared by CI configuration: declared evidence, not executed by Assertiva."""
    return _ci_invocations(root, "unittest", unittest_scopes)


def path_selected_by_ci(path: str, invocations: list[CiPytestInvocation]) -> bool:
    normalized = path.replace("\\", "/").removeprefix("./")
    for inv in invocations:
        if inv.runs_all_tests or inv.base_unresolved:  # an unresolved directory may be this one: no gap is claimed
            return True
        for scope in inv.root_scopes():
            s = scope.split("::")[0].rstrip("/")
            if not s or normalized in {s, s + ".py"} or normalized.startswith(s + "/"):
                return True
    return False
