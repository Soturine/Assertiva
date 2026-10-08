"""Gradle adapter: Java, Kotlin/JVM, Android local tests and Kotlin Multiplatform JVM tests, run by Gradle itself.

Discovery is static (settings and build scripts, source sets): modules, their plugins, test frameworks named in
the build (JUnit 4/5, kotlin.test, Kotest, TestNG, Robolectric, Espresso, Compose UI test; MockK and Mockito are
doubles, not runners), coverage plugins (JaCoCo, Kover) and the test source sets that exist. Execution runs a
Gradle distribution prepared for the run (or one installed on PATH), never the project's ``gradle-wrapper.jar``,
in the disposable copy, with Gradle's caches in Assertiva's tools cache (never the user's ~/.gradle) and
``--offline`` unless the run was provisioned with consent (then dependencies may be downloaded).

Per test task the adapter reads the JUnit XML Gradle writes (``build/test-results/<task>``), keeping the module
and task in each id, and the coverage report a coverage plugin the build already applies writes; it never adds a
plugin. What cannot run here is reported per target instead of being assumed: Android instrumented tests
(``src/androidTest``) need a device or emulator and are never run on a physical device; Kotlin/Native and iOS
targets need their host; JS targets are not run by this version.
"""

from __future__ import annotations

import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import Outcome, RunEvidence, TestInvocation
from assertiva.process import execution_refusal, run_command
from assertiva.verification import SupportLevel

from .base import AdapterCapability
from .coverage_reports import load_coverage_report
from .junit import load_junit

_BUILD = ("build.gradle", "build.gradle.kts")
_SETTINGS = ("settings.gradle", "settings.gradle.kts")
_INCLUDE = re.compile(r"""include\s*\(?\s*((?:["'][^"']+["']\s*,?\s*)+)\)?""")
_QUOTED = re.compile(r"""["']([^"']+)["']""")
_FRAMEWORKS = {
    "junit-jupiter": "JUnit 5", "junit:junit": "JUnit 4", 'kotlin("test")': "kotlin.test", "kotlin-test": "kotlin.test",
    "kotest": "Kotest", "testng": "TestNG", "robolectric": "Robolectric", "espresso": "Espresso", "ui-test-junit4": "Compose UI test",
    "mockk": "MockK (doubles)", "mockito": "Mockito (doubles)",
}
_COMPILE_ERROR = re.compile(r"(Compilation failed|compileTestKotlin|compileTestJava|^e: |error: )", re.M)
_RESOLUTION = re.compile(r"(Could not resolve|No cached version|offline mode|Could not GET|Could not download|Plugin \[id: .+\] was not found)")
_KMP_HOSTS = {"js": "JS targets are not run by this version", "wasm": "Wasm targets are not run by this version",
              "ios": "needs a macOS host with Xcode", "macos": "needs a macOS host", "tvos": "needs a macOS host with Xcode",
              "watchos": "needs a macOS host with Xcode", "linux": "Kotlin/Native targets are not run by this version",
              "mingw": "Kotlin/Native targets are not run by this version", "native": "Kotlin/Native targets are not run by this version"}
FORMAT_LIMITS = [
    "results are Gradle's JUnit XML per test task: the JUnit Platform names a method and its parameters, so declarations are known by class and method",
    "only coverage reports the build already produces (JaCoCo, Kover) are read; no coverage plugin is added",
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def modules(root: Path) -> list[dict]:
    """Modules with their build script, plugins, frameworks and test source sets (static, never executed)."""
    root = Path(root)
    settings = next((_read(root / n) for n in _SETTINGS if (root / n).is_file()), "")
    paths = [""]
    for match in _INCLUDE.finditer(settings):
        paths += [q.strip(":").replace(":", "/") for q in _QUOTED.findall(match.group(1))]
    out = []
    for rel in dict.fromkeys(paths):
        folder = root / rel if rel else root
        script = next((folder / n for n in _BUILD if (folder / n).is_file()), None)
        if script is None:
            continue
        text = _read(script)
        applied = "\n".join(line for line in text.splitlines() if "apply false" not in line)  # declared, not applied here
        kind = ("android" if re.search(r"com\.android\.(application|library)", applied)
                else "kmp" if re.search(r"""kotlin\(["']multiplatform["']\)|org\.jetbrains\.kotlin\.multiplatform""", applied)
                else "kotlin-jvm" if re.search(r"""kotlin\(["']jvm["']\)|org\.jetbrains\.kotlin\.jvm""", applied)
                else "java" if re.search(r"\bjava\b|java-library|\bapplication\b", applied) else "unknown")
        source_sets = sorted(p.name for p in (folder / "src").iterdir() if p.is_dir() and p.name.lower().endswith("test")) if (folder / "src").is_dir() else []
        out.append({
            "path": rel or ".", "gradle_path": ":" + rel.replace("/", ":") if rel else "", "kind": kind,
            "frameworks": sorted({name for key, name in _FRAMEWORKS.items() if key in text}),
            "coverage": [tool for tool, key in (("jacoco", "jacoco"), ("kover", "kover")) if key in text],
            "test_source_sets": source_sets,
        })
    return out


def _tasks(module: dict) -> tuple[list[str], dict[str, str]]:
    """Test tasks to run for a module, and the matrix entries that do not run here (with why)."""
    prefix, sets, matrix = module["gradle_path"], module["test_source_sets"], {}
    if module["kind"] == "android":
        tasks = [f"{prefix}:testDebugUnitTest"] if "test" in sets else []
        if "androidTest" in sets:
            matrix[f"{prefix or ':'} connectedAndroidTest (instrumented)"] = "NOT_RUN: needs a device or emulator; a physical device is never used without authorization"
        return tasks, matrix
    if module["kind"] == "kmp":
        tasks = [f"{prefix}:jvmTest"] if any(s in sets for s in ("jvmTest", "commonTest")) else []
        for name in sets:
            target = name[: -len("Test")]
            if target in ("common", "jvm"):
                continue
            reason = next((why for key, why in _KMP_HOSTS.items() if target.lower().startswith(key)), "not run by this version")
            if target == "android":
                reason = "Android unit tests of a multiplatform module are not run by this version"
            matrix[f"{prefix or ':'} {name}"] = f"NOT_RUN: {reason}"
        return tasks, matrix
    return ([f"{prefix}:test"] if "test" in sets else []), matrix


def _declaration(classname: str, name: str) -> tuple[str | None, str | None]:
    """`vip()` -> (`Class#vip`, None); `squares(int)[1]` -> (`Class#squares`, `1`); a display name only (`[1] 0, 0`,
    what Gradle writes for JUnit 5 parameterized cases) -> (None, `1] 0, 0`-style parameters): the method is unknown."""
    display = re.match(r"^\[(?P<index>\d+)\]\s*(?P<rest>.*)$", name)
    if display:
        return None, f"[{display.group('index')}] {display.group('rest')}".strip()
    match = re.match(r"^(?P<method>[^(\[]+)(?:\([^)]*\))?(?:\[(?P<params>.+)\])?$", name)
    method = match.group("method").strip() if match else name
    return f"{classname}#{method}", (match.group("params") if match and match.group("params") else None)


class GradleAdapter:
    adapter_id = "gradle"
    runner = "gradle"

    def __init__(self, python: str | None = None, timeout_s: float = 1800.0):
        self.timeout_s = timeout_s  # `python` is accepted for the common factory signature only

    def supports(self, root: Path) -> SupportLevel:
        root = Path(root)
        return SupportLevel.SUPPORTED if any((root / n).is_file() for n in (*_BUILD, *_SETTINGS)) else SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        s, u = SupportLevel.SUPPORTED, SupportLevel.UNSUPPORTED
        return (
            AdapterCapability("structured_results", s, "Gradle's JUnit XML per test task and module"),
            AdapterCapability("parameterized_invocations", s, "JUnit Platform parameter suffixes"),
            AdapterCapability("coverage", SupportLevel.UNKNOWN, "only JaCoCo/Kover reports the build already writes"),
            AdapterCapability("android_local_tests", SupportLevel.UNKNOWN, "needs an Android SDK on this machine"),
            AdapterCapability("android_instrumented_tests", u, "needs a device or emulator; never run on a physical device"),
            AdapterCapability("kmp_non_jvm_targets", u, "JS, Wasm, Native and iOS targets are listed, not run"),
            AdapterCapability("static_oracle_analysis", SupportLevel.UNKNOWN, "lexical test facts (see test effectiveness)"),
        )

    def _gradle(self) -> str | None:
        from assertiva import environment

        if environment.ACTIVE and environment.ACTIVE.tools.get("gradle"):
            return environment.ACTIVE.tools["gradle"]
        return shutil.which("gradle")

    def _blocked(self, reason: str, **fields) -> RunEvidence:
        return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[reason], **fields)

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        from assertiva import environment
        from assertiva.environment import tools_dir

        root = Path(root)
        refusal = execution_refusal()
        if refusal:
            return self._blocked(refusal)
        gradle = self._gradle()
        if not gradle:
            return self._blocked("no Gradle distribution is available (prepare one with audit --execute --provision); the project's "
                                 "gradle-wrapper.jar is never executed")
        found = modules(root)
        matrix: dict[str, str] = {}
        tasks: list[str] = []
        android_sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
        for module in found:
            module_tasks, module_matrix = _tasks(module)
            matrix.update(module_matrix)
            if module["kind"] == "android" and module_tasks and not android_sdk and not (root / "local.properties").is_file():
                matrix[f"{module['gradle_path'] or ':'} testDebugUnitTest (local)"] = "BLOCKED: no Android SDK (ANDROID_HOME) on this machine"
                continue
            tasks += module_tasks
            if coverage:
                tasks += [f"{module['gradle_path']}:{t}" for t in ("jacocoTestReport",) if "jacoco" in module["coverage"] and module_tasks]
                tasks += [f"{module['gradle_path']}:koverXmlReport" for _ in [0] if "kover" in module["coverage"] and module_tasks]
        tasks = list(args) if args else tasks
        if not tasks:
            run = self._blocked("no test task to run: no module with test sources that this machine can run")
            run.metadata["matrix"] = matrix
            return run
        provisioned = bool(environment.ACTIVE and environment.ACTIVE.tools.get("gradle") and environment.ACTIVE.workspace)
        home = environment.ACTIVE.env.get("GRADLE_USER_HOME") if environment.ACTIVE else None
        env = {**os.environ, "GRADLE_USER_HOME": home or str(tools_dir() / "gradle-home")}
        command = [gradle, "--no-daemon", "--console=plain", "--continue", "-Dorg.gradle.jvmargs=-Xmx1g", *tasks]
        if not provisioned:
            command.insert(1, "--offline")
        result = run_command(command, root, env=env, timeout_s=self.timeout_s)
        run = RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.UNKNOWN, command=command,
                          exit_code=result.returncode, wall_clock_s=result.duration_s)
        run.limitations += FORMAT_LIMITS
        run.metadata.update({"modules": found, "tasks": tasks, "offline": not provisioned})
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        if result.error or result.timed_out:
            return self._blocked(f"Gradle could not run: {result.summary()}", command=command, wall_clock_s=result.duration_s)
        unknown_declarations = False
        for task in tasks:
            if not task.endswith(("Test", ":test")) and not task.split(":")[-1].lower().endswith("test"):
                continue
            module_path, task_name = task.rsplit(":", 1)
            folder = root / module_path.strip(":").replace(":", "/") if module_path else root
            reports = sorted((folder / "build" / "test-results" / task_name).glob("TEST-*.xml"))
            matrix[f"{module_path or ':'} {task_name}"] = "EXECUTED" if reports else "NOT_RUN"
            for report in reports:
                parsed = load_junit(report)
                if parsed.status is StageStatus.BLOCKED:
                    run.limitations.append(f"unreadable test report {report.name} in {task}")
                    continue
                cases = [(c.get("classname") or "", c.get("name") or "") for c in ET.parse(report).getroot().iter("testcase")]
                if len(cases) != len(parsed.invocations):
                    run.limitations.append(f"unreadable test report {report.name} in {task}")
                    continue
                for inv, (classname, name) in zip(parsed.invocations, cases):
                    declaration, params = _declaration(classname, name)
                    if declaration is None:
                        unknown_declarations = True
                    run.invocations.append(TestInvocation(
                        invocation_id=f"{task} {classname}#{name}",
                        declaration_id=f"{module_path or ':'} {declaration or classname + '#' + name}",
                        materialization_id=f"{task} {declaration or classname + '#' + name}", parameters_id=params, outcome=inv.outcome,
                        duration_s=inv.duration_s, message=inv.message, markers=(f"gradle:{task_name}",),
                    ))
        if unknown_declarations:
            # JUnit 5 parameterized cases appear by display name only (`[1] 0, 0`): their method is not in the report
            run.metadata["declaration_identity"] = "UNKNOWN"
            run.limitations.append("some cases are reported by display name only (parameterized): their declaring method is unknown")
        if _RESOLUTION.search(output) and not run.invocations:
            run.status = StageStatus.BLOCKED
            run.limitations.append("Gradle could not resolve the build's plugins or dependencies"
                                   + (" offline (prepare with --provision to allow downloads)" if not provisioned else ""))
            run.metadata["matrix"] = matrix
            return run
        if result.returncode != 0 and _COMPILE_ERROR.search(output):
            failed = sorted({t for t in tasks if f"{t.rsplit(':', 1)[0]}:compile" in output} or {"test compilation"})
            run.collection_errors += [f"compilation failed ({t})" for t in failed]
        run.metadata["matrix"] = matrix
        if coverage:
            summaries = [load_coverage_report(p) for m in found for p in [
                (root / m["path"] / "build" / "reports" / "jacoco" / "test" / "jacocoTestReport.xml"),
                (root / m["path"] / "build" / "reports" / "kover" / "report.xml")] if p.is_file()]
            summaries = [s for s in summaries if s.error is None]
            run.coverage = _merge(summaries) if summaries else None
            if not summaries:
                run.limitations.append("no coverage report: the build applies no coverage plugin that wrote one (none is added)")
        outcomes = {inv.outcome for inv in run.invocations}
        if run.collection_errors or outcomes & {Outcome.FAILED, Outcome.ERROR}:
            run.status = StageStatus.FAIL
        elif not run.invocations or outcomes <= {Outcome.SKIPPED, Outcome.NOT_RUN}:
            run.status = StageStatus.UNKNOWN if result.returncode == 0 else StageStatus.BLOCKED
            run.limitations.append("no test was executed; this is not evidence of a passing suite"
                                   + ("" if result.returncode == 0 else ": " + " | ".join(output.strip().splitlines()[-3:])))
        elif result.returncode == 0:
            run.status = StageStatus.PASS
        else:
            run.status = StageStatus.FAIL
            run.limitations.append(f"Gradle exited with code {result.returncode}: " + " | ".join(output.strip().splitlines()[-3:]))
        return run

    def installed_dependencies(self) -> tuple[str, ...]:
        return ()

    def declared_matrix(self, root) -> dict[str, dict]:
        from .provisioning import declared_jdk

        version = declared_jdk(Path(root))
        return {"java": {"values": [str(version)], "source": "Gradle toolchain declaration"}} if version else {}

    def static_signals(self, root) -> dict[str, int]:
        return {}

    def static_negative_paths(self, root) -> dict[str, list[str]]:
        return {}

    def reproduction_args(self, check) -> list[str] | None:
        """Gradle tasks a declared `./gradlew test` / `gradle check` step runs (test tasks only)."""
        if check.tool not in ("gradle", "./gradlew") or not check.command or "${{" in check.command:
            return None
        tasks = [a for a in check.metadata.get("runner_args", []) if not a.startswith("-")]
        return tasks if tasks and all(t.split(":")[-1].lower().endswith("test") for t in tasks) else None

    def equivalent_to_default(self, args: list[str]) -> bool:
        return False


def _merge(summaries):
    """Coverage of several modules: counts add up (disjoint classes); the scope says which reports."""
    from assertiva.models import CoverageSummary

    counts: dict[str, dict[str, int]] = {}
    product: dict[str, dict[str, int]] = {}
    for summary in summaries:
        for target, source in ((counts, summary.counts), (product, summary.product_counts)):
            for kind, count in source.items():
                bucket = target.setdefault(kind, {"covered": 0, "total": 0})
                bucket["covered"] += count["covered"]
                bucket["total"] += count["total"]
    merged = CoverageSummary(source=", ".join(s.source for s in summaries), counts=counts, tool=summaries[0].tool,
                             scope=f"{len(summaries)} module report(s)", product_counts=product,
                             files=sum(s.files or 0 for s in summaries), test_files=sum(s.test_files or 0 for s in summaries))
    return CoverageSummary(**{**merged.__dict__, "line_percent": merged.percent("line"), "branch_percent": merged.percent("branch")})
