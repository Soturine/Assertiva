"""Playwright adapter: run the project's own Playwright Test with the official JSON reporter.

The results format is Playwright's ``JSONReport`` (``config.projects``, ``suites[].specs[].tests[].results[]``).
Projects are distinguished as DECLARED (in the config), SELECTED (in the run) and EXECUTED (at least one
attempt actually ran). The report does not record each project's browser, so engines are inferred from
project names and said to be. Locator evidence is static source analysis (E3): it describes coupling and
semantics, it is not a quality score. Assertiva never installs browsers, never targets remote base URLs,
and has no screenshot or visual comparison engine.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from assertiva.candidate import StageStatus
from assertiva.models import Outcome, RunEvidence, TestInvocation
from assertiva.process import execution_refusal, run_command
from assertiva.verification import SupportLevel

from .base import AdapterCapability

_CONFIGS = tuple(f"playwright.config.{ext}" for ext in ("ts", "js", "mjs", "cjs", "mts", "cts"))
_ENGINES = {"chromium": ("chromium", "chrome", "edge"), "firefox": ("firefox",), "webkit": ("webkit", "safari")}
_RANK = {"DECLARED": 1, "SELECTED": 2, "EXECUTED": 3}
_MISSING_BROWSER = re.compile(r"Executable doesn't exist at|Looks like Playwright .* was just installed or updated")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "[::1]"}
_BASE_URL = re.compile(r"""baseURL\s*:\s*["'`](https?://[^"'`]+)["'`]""")
_COSMETIC = {"--quiet", "-q"}
FORMAT_LIMITS = [
    "browser engines are inferred from project names; Playwright's JSON report does not record each project's browser",
    "attachments (screenshots, traces, videos) are referenced by name and path only; files written in a disposable copy are removed with it",
]

_LOCATOR_CALL = re.compile(
    r"""\.(getByRole|getByLabel|getByPlaceholder|getByText|getByTestId|getByAltText|getByTitle|locator|\$\$?)\(\s*(?:(["'`])((?:\\.|(?!\2).)*)\2)?""",
    re.S,
)
_BY_METHOD = {"getByRole": "ROLE", "getByLabel": "LABEL", "getByPlaceholder": "PLACEHOLDER", "getByText": "TEXT",
              "getByTestId": "TEST_ID", "getByAltText": "OTHER", "getByTitle": "OTHER"}
_ENGINE_PREFIX = {"xpath": "XPATH", "css": "CSS", "text": "TEXT", "role": "ROLE", "data-testid": "TEST_ID",
                  "internal:testid": "TEST_ID", "internal:role": "ROLE", "internal:label": "LABEL", "internal:text": "TEXT", "id": "CSS"}
LOCATOR_KINDS = ("ROLE", "LABEL", "PLACEHOLDER", "TEXT", "TEST_ID", "CSS", "XPATH", "OTHER", "UNKNOWN")


def classify_locator(call: str) -> str:
    """Kind of one locator call (``getByRole(...)``, ``locator("...")``). Evidence of semantics, not a judgment."""
    match = _LOCATOR_CALL.search("." + call.lstrip("."))
    if not match:
        return "UNKNOWN"
    method, selector = match.group(1), match.group(3)
    if method in _BY_METHOD:
        return _BY_METHOD[method]
    if selector is None:
        return "UNKNOWN"  # a variable or expression: the selector is not visible statically
    selector = selector.strip()
    if selector.startswith(("//", "..", "(//")):
        return "XPATH"
    engine = re.match(r"^([a-z:-]+)=", selector)
    if engine and engine.group(1) in _ENGINE_PREFIX:
        return _ENGINE_PREFIX[engine.group(1)]
    if selector[:1] in "\"'":
        return "TEXT"  # legacy quoted text selector
    return "CSS"


def _package(root: Path) -> dict:
    try:
        return json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _relative(path: str, root: str) -> str:
    if root == "<ROOT>":  # recorded fixtures
        return path.replace("<ROOT>", "").lstrip("\\/").replace("\\", "/")
    try:
        return Path(os.path.relpath(os.path.realpath(path), os.path.realpath(root))).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _engine(project: str) -> str | None:
    name = project.lower()
    return next((engine for engine, hints in _ENGINES.items() if any(h in name for h in hints)), None)


def _clean(text: str | None, limit: int = 1000) -> str | None:
    return _ANSI.sub("", text)[:limit] if text else None


def _join(directory: str, file: str) -> str:
    return directory.rstrip("\\/") + "/" + file.replace("\\", "/")


def parse_playwright_results(data: dict | str, root: str | Path) -> RunEvidence:
    """Normalize a Playwright JSON report into run evidence (no execution)."""
    run = RunEvidence(adapter_id="playwright", mode="execute", status=StageStatus.UNKNOWN)
    try:
        if isinstance(data, str):
            data = json.loads(data)
        suites, projects = data["suites"], data["config"]["projects"]
        if not isinstance(suites, list) or not isinstance(projects, list):
            raise TypeError("suites/projects are not lists")
    except (ValueError, KeyError, TypeError) as exc:
        run.status = StageStatus.BLOCKED
        run.limitations.append(f"Playwright results could not be read: {exc}"[:300])
        return run
    run.limitations += FORMAT_LIMITS
    root = str(root)
    test_dirs = {p.get("id") or p.get("name"): p.get("testDir", root) for p in projects}
    state = {p.get("name", ""): "DECLARED" for p in projects}
    attachments: dict[str, list[dict]] = {}
    retried, missing_browser = [], set()

    for error in data.get("errors") or []:
        location = error.get("location") or {}
        if location.get("file"):
            rel = _relative(location["file"], root)
            run.collection_errors.append(rel)
            run.metadata.setdefault("error_sources", {})[rel] = rel
        else:
            run.limitations.append("Playwright reported an error outside any test: " + (_clean(error.get("message"), 300) or "unknown"))

    def walk(suite: dict, titles: tuple[str, ...]) -> None:
        specs = suite.get("specs") or []
        shared: dict[tuple, int] = {}
        for spec in specs:
            for test in spec.get("tests") or []:
                key = (test.get("projectName"), spec.get("line"), spec.get("column"))
                shared[key] = shared.get(key, 0) + 1
        for spec in specs:
            for test in spec.get("tests") or []:
                _test(spec, test, titles, shared)
        for child in suite.get("suites") or []:
            walk(child, (*titles, child.get("title", "")))

    def _test(spec: dict, test: dict, titles: tuple[str, ...], shared: dict) -> None:
        project = test.get("projectName", "")
        state[project] = max(state.get(project, "SELECTED"), "SELECTED", key=_RANK.get)
        rel = _relative(_join(test_dirs.get(test.get("projectId"), root), spec.get("file", "")), root)
        line, column = spec.get("line"), spec.get("column")
        name = " › ".join([*titles, spec.get("title", "")])
        invocation_id = f"{rel} › {name} [{project}]"
        declaration = f"{rel}:{line}:{column}"
        results = test.get("results") or []
        final = results[-1] if results else {}
        errors = [e.get("message", "") for r in results for e in (r.get("errors") or [])]
        message = _clean((final.get("error") or {}).get("message"))
        status, expected = test.get("status"), test.get("expectedStatus")
        markers = tuple(dict.fromkeys([*(t.lstrip("@") for t in spec.get("tags") or []),
                                       *(a.get("type", "") for a in test.get("annotations") or [])]))
        if not results:
            outcome, message = Outcome.NOT_RUN, "selected but not executed"
        elif errors and all(_MISSING_BROWSER.search(e) for e in errors):
            outcome, message = Outcome.NOT_RUN, f"not executed: the browser for project {project} is not installed"
            missing_browser.add(project)
        elif status == "skipped":
            outcome = Outcome.SKIPPED
            message = message or next((f"{a['type']}: {a.get('description') or ''}".strip(": ")
                                       for a in test.get("annotations") or [] if a.get("type") in ("skip", "fixme")), None)
        elif status == "expected":
            outcome = Outcome.XFAILED if expected == "failed" else Outcome.PASSED
        elif status == "flaky":
            outcome = Outcome.PASSED
            retried.append(invocation_id)
            message = f"passed after {len(results)} attempts (earlier attempts failed)"
        elif expected == "failed" and final.get("status") == "passed":
            outcome = Outcome.XPASSED
        elif final.get("status") == "interrupted":
            outcome, message = Outcome.NOT_RUN, "interrupted"
        else:
            outcome = Outcome.FAILED
            if final.get("status") == "timedOut":
                message = "timed out" + (f": {message}" if message else "")
        if outcome not in (Outcome.NOT_RUN, Outcome.SKIPPED):
            state[project] = "EXECUTED"
        files = [
            {"name": a.get("name"), "content_type": a.get("contentType"), "attempt": r.get("retry", 0),
             "path": _relative(a["path"], root) if a.get("path") else None}
            for r in results for a in r.get("attachments") or []
        ]
        if files:
            attachments[invocation_id] = files
        durations = [r.get("duration") for r in results if r.get("duration") is not None]
        run.invocations.append(TestInvocation(
            invocation_id=invocation_id, declaration_id=declaration, materialization_id=f"{declaration} [{project}]",
            parameters_id=spec.get("title") if shared.get((project, line, column), 0) > 1 else None,
            markers=markers, outcome=outcome, duration_s=sum(durations) / 1000 if durations else None,
            message=message, source_paths=(rel,),
        ))

    for suite in suites:
        walk(suite, ())
    run.metadata["attachments"] = attachments
    matrix = {f"project {name}": value for name, value in state.items()}
    for engine in _ENGINES:
        states = [value for name, value in state.items() if _engine(name) == engine]
        matrix[f"engine {engine}"] = max(states, key=_RANK.get) if states else "NOT_CONFIGURED"
    run.metadata["matrix"] = matrix
    for name, value in state.items():
        if name in missing_browser:
            run.limitations.append(f"project {name} was selected but not executed: its browser is not installed (Assertiva does not install browsers)")
        elif value == "DECLARED":
            run.limitations.append(f"project {name} is declared but was not selected in this run")
    if retried:
        run.limitations.append("retried tests passed only after earlier failed attempts: " + ", ".join(retried[:5]))
    outcomes = {inv.outcome for inv in run.invocations}
    if run.collection_errors or outcomes & {Outcome.FAILED, Outcome.ERROR, Outcome.XPASSED}:
        run.status = StageStatus.FAIL
    elif not outcomes & {Outcome.PASSED, Outcome.XFAILED}:
        run.status = StageStatus.UNKNOWN if run.invocations else StageStatus.BLOCKED
        run.limitations.append("no browser test was executed; this is not evidence of a passing suite")
    else:
        run.status = StageStatus.PASS
    return run


class PlaywrightAdapter:
    adapter_id = "playwright"

    def __init__(self, python: str | None = None, timeout_s: float = 900.0):
        self.timeout_s = timeout_s  # `python` is accepted for the common factory signature only

    def supports(self, root: Path) -> SupportLevel:
        root = Path(root)
        package = _package(root)
        deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        if "@playwright/test" in deps or any((root / name).is_file() for name in _CONFIGS):
            return SupportLevel.SUPPORTED
        return SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        return (
            AdapterCapability("structured_results", SupportLevel.SUPPORTED, "official JSON reporter"),
            AdapterCapability("execution_matrix", SupportLevel.SUPPORTED, "projects declared/selected/executed; engines inferred from names"),
            AdapterCapability("locator_evidence", SupportLevel.SUPPORTED, "static (E3), informational"),
            AdapterCapability("coverage", SupportLevel.UNSUPPORTED),
            AdapterCapability("visual_comparison", SupportLevel.UNSUPPORTED),
        )

    def installed_dependencies(self) -> tuple[str, ...]:
        return ("node_modules",)  # browsers live in Playwright's own cache, outside the project

    def _node(self) -> str | None:
        configured = os.environ.get("ASSERTIVA_NODE")
        if configured:
            return configured if Path(configured).is_file() else None
        return shutil.which("node")

    def _remote_targets(self, root: Path) -> list[str]:
        hosts = []
        for name in _CONFIGS:
            try:
                text = (root / name).read_text(encoding="utf-8")
            except OSError:
                continue
            hosts += [urlparse(url).hostname or url for url in _BASE_URL.findall(text)]
        return [h for h in hosts if h not in _LOCAL_HOSTS]

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        root = Path(root)

        def blocked(reason: str, **extra) -> RunEvidence:
            return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[reason], **extra)

        refusal = execution_refusal()
        if refusal:
            return blocked(refusal)
        remote = self._remote_targets(root)
        if remote:
            return blocked(f"the Playwright config targets a remote baseURL ({', '.join(remote)}); Assertiva never runs browser tests against remote environments")
        cli = next((p for p in (root / "node_modules" / "playwright" / "cli.js", root / "node_modules" / "@playwright" / "test" / "cli.js") if p.is_file()), None)
        if cli is None:
            return blocked("the project's Playwright is not installed (node_modules/playwright); Assertiva does not install dependencies or browsers")
        node = self._node()
        if not node:
            return blocked("Node.js was not found (PATH or ASSERTIVA_NODE)")
        with tempfile.TemporaryDirectory(prefix="assertiva-playwright-") as tmp:
            out = Path(tmp) / "results.json"
            command = [node, str(cli), "test", "--reporter=json", *(args or [])]
            env = {**os.environ, "PLAYWRIGHT_JSON_OUTPUT_FILE": str(out), "FORCE_COLOR": "0"}
            result = run_command(command, root, env=env, timeout_s=self.timeout_s)
            if result.error or result.timed_out or not out.is_file():
                return blocked(f"Playwright produced no results: {result.summary()}", command=command, wall_clock_s=result.duration_s)
            run = parse_playwright_results(out.read_text(encoding="utf-8"), root)
            run.command, run.exit_code, run.wall_clock_s = command, result.returncode, result.duration_s
        if coverage:
            run.limitations.append("browser tests are not coverage-instrumented by Assertiva")
        return run

    def static_signals(self, root) -> dict[str, int]:
        """Locator kinds used by Playwright test files (static, E3; informational, never a score)."""
        root = Path(root)
        counts = {f"locator_{kind.lower()}": 0 for kind in LOCATOR_KINDS}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git", "test-results", "playwright-report")]
            for filename in filenames:
                if not re.search(r"\.(spec|test|e2e)\.[cm]?[jt]sx?$", filename):
                    continue
                try:
                    text = (Path(dirpath) / filename).read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                if "@playwright/test" not in text:
                    continue
                for match in _LOCATOR_CALL.finditer(text):
                    counts[f"locator_{classify_locator(match.group(0)).lower()}"] += 1
        return {name: value for name, value in counts.items() if value}

    def static_negative_paths(self, root) -> dict[str, list[str]]:
        return {}

    def reproduction_args(self, check) -> list[str] | None:
        """Playwright arguments reproducing a delivery check (`playwright test ...`)."""
        if check.tool == "playwright test" and check.command and "${{" not in check.command:
            return list(check.metadata.get("runner_args", []))
        return None

    def equivalent_to_default(self, args: list[str]) -> bool:
        return all(arg in _COSMETIC for arg in args)
