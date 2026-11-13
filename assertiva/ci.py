from __future__ import annotations

import posixpath
import re
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
        """The directory is an expression (`${{ matrix.dir }}`, `$DIR`) or a `cd` whose target is not literal: where it
        runs is not known from configuration."""
        return "$" in self.base or self.base == UNRESOLVED

    def root_scopes(self) -> tuple[str, ...]:
        """The scopes as repository paths: joined to the working directory (a base alone means everything under it)."""
        if not self.base:
            return self.scopes
        base = posixpath.normpath(self.base.replace("\\", "/")).removeprefix("./")
        base = "" if base == "." else base
        joined = [posixpath.normpath(posixpath.join(base, s)) if base else s for s in self.scopes or ("",)]
        return tuple(dict.fromkeys(("" if j == "." else j) for j in joined))


UNRESOLVED = "<unresolved>"


def join_directories(*parts: str | None) -> str:
    """Directories joined in order ("" = unchanged); a None part (a `cd` the command line does not determine) makes the
    result unresolved."""
    if any(p is None for p in parts):
        return UNRESOLVED
    joined = posixpath.normpath("/".join(p.replace("\\", "/").strip("/") for p in parts if p)) if any(parts) else ""
    return "" if joined == "." else joined.removeprefix("./")


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
    """One invocation per command of a CI step that runs ``tool`` (a step may run several, on several lines or after a
    `cd`: AXF-02), each scoped from its own arguments and directory."""
    from .verification import VerificationOrigin, discover_surface

    out = []
    for check in discover_surface(Path(root)).by_origin(VerificationOrigin.CI):
        if not check.command:
            continue
        workflow, step_directory = check.source.split("#")[0], str(check.metadata.get("working_directory") or "")
        recorded = check.metadata.get("invocations")
        if recorded is None:  # a check built without the command table (older records): its first command only
            recorded = [{"tool": check.tool, "runner_args": check.metadata.get("runner_args", ()), "command": check.command,
                         "directory": ""}] if check.tool == tool else []
        for inv in recorded:
            if inv.get("tool") == tool:
                out.append(CiPytestInvocation(workflow, inv.get("command") or check.command, scopes(inv.get("runner_args") or ()),
                                              join_directories(step_directory, inv.get("directory"))))
    return out


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


_LAUNCHERS = {"run", "call", "check_call", "check_output", "Popen", "system", "spawnv", "execv", "execvp", "run_command"}
_SCRIPT_RUNNERS = {"python", "python3", "py", "bash", "sh", "pwsh", "powershell"}
_SHELL_RUNS = {"pytest": re.compile(r"(?:^|[\s;&|(])(?:python[\d.]*\s+-m\s+)?pytest\b"),
               "unittest": re.compile(r"(?:^|[\s;&|(])python[\d.]*\s+-m\s+unittest\b")}


def _python_script_runs(text: str, tool: str) -> bool:
    """Whether a Python script's source invokes ``tool``: `pytest.main(...)`, `unittest.main(...)`, or the runner's
    name as a literal argument of a call (`subprocess.run([sys.executable, "-m", "pytest"])`). Read, never run."""
    import ast

    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == tool and func.attr == "main":
            return True
        leaf = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        if leaf not in _LAUNCHERS:  # `print("pytest")` mentions the runner; it does not run it
            continue
        literals = [n.value for arg in node.args for n in ast.walk(arg) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        if any(value == tool or value.split()[:1] == [tool] or f"-m {tool}" in value for value in literals):
            return True
    return False


def scripts_running(root: str | Path, tool: str) -> list[dict]:
    """CI steps that run a repository script whose source invokes ``tool`` (AXF-M3-01): `python tools/gate.py`, `bash
    ci/test.sh`, `./run-tests.sh`. One level, read statically: the script's own arguments to the runner (which tests
    it selects) are not interpreted, so the scope stays unknown. A script that does not mention the runner is not one."""
    from .adapters.commands import _tokens, classify_command
    from .verification import VerificationOrigin, discover_surface

    root = Path(root).resolve()
    found = []
    for check in discover_surface(root).by_origin(VerificationOrigin.CI):
        if not check.command:
            continue
        directory = root / str(check.metadata.get("working_directory") or "")
        cls = classify_command(check.command)
        segments = [(s, None) for s in (cls.unclassified or ((check.command,) if cls.kind.value == "UNKNOWN" else ()))]
        # AXR-03: one hop through the project's package scripts (npm run verify -> python tools/verify.py); the graph
        # of scripts is cycle-safe, and only commands written in package.json are read, never run
        scripts = _package_scripts(directory)
        if scripts:
            from .adapters.package_scripts import invoked

            for name in invoked(check.command, scripts):
                inner = classify_command(str(scripts[name]))
                own = inner.unclassified or ((str(scripts[name]),) if inner.kind.value == "UNKNOWN" else ())
                segments += [(s, name) for s in own]
        for segment, via in segments:
            tokens = _tokens(segment)
            if not tokens:
                continue
            path = tokens[1] if tokens[0] in _SCRIPT_RUNNERS and len(tokens) > 1 else tokens[0]
            script = (directory / path).resolve()
            if not (script.is_file() and root in script.parents) or script.suffix not in (".py", ".sh", ".bash", ".ps1", ""):
                continue
            try:
                text = script.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            runs = _python_script_runs(text, tool) if script.suffix == ".py" else any(
                _SHELL_RUNS[tool].search(line) for line in text.splitlines() if not line.lstrip().startswith("#"))
            if runs:
                found.append({"workflow": check.source.split("#")[0], "command": segment,
                              "script": script.relative_to(root).as_posix(), "basis": "STATIC",
                              **({"via_package_script": via} if via else {})})
    return found


def _package_scripts(directory: Path) -> dict:
    import json

    try:
        return json.loads((directory / "package.json").read_text(encoding="utf-8")).get("scripts") or {}
    except (OSError, ValueError, AttributeError):
        return {}


def indirect_invocations(root: str | Path, tool: str) -> list[CiPytestInvocation]:
    """Scripts that run ``tool`` as CI invocations whose directory is unresolved: they may select any test, so no gap is
    claimed against them, and none is claimed for them."""
    return [CiPytestInvocation(s["workflow"], s["command"], (), UNRESOLVED) for s in scripts_running(root, tool)]
