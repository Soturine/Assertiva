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
import tomllib
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
    "results are Gradle's JUnit XML per test task: a case named by its method keeps its declaration (class and method); "
    "a parameterized case reported by display name only does not, and its declaration stays UNKNOWN",
    "only coverage reports the build already produces (JaCoCo, Kover) are read; no coverage plugin is added",
]


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


_PLUGIN_REF = re.compile(
    r"""\bid\s*\(?\s*["'](?P<id>[\w.\-]+)["']"""  # id("x") / id 'x'
    r"""|\bapply\s*\(?\s*plugin\s*[:=]\s*["'](?P<legacy>[\w.\-]+)["']"""  # apply plugin: 'x' / apply(plugin = "x")
    r"""|\b(?:pluginManager|plugins)\s*\.\s*apply\s*\(\s*["'](?P<applied>[\w.\-]+)["']"""  # pluginManager.apply("x")
    r"""|\bkotlin\s*\(\s*["'](?P<kotlin>[\w.\-]+)["']\s*\)"""  # kotlin("jvm")
    r"""|\balias\s*\(\s*(?P<alias>[\w.]+)\s*\)"""  # alias(libs.plugins.x)
    r"""|\bfindPlugin\s*\(\s*["'](?P<found>[\w.\-]+)["']\s*\)""")  # libs.findPlugin("x") in convention plugins
_KINDS = (("android", ("com.android.application", "com.android.library", "com.android.dynamic-feature", "com.android.test")),
          ("kmp", ("org.jetbrains.kotlin.multiplatform",)),
          ("kotlin-jvm", ("org.jetbrains.kotlin.jvm",)),
          ("java", ("java", "java-library", "application", "groovy", "scala", "org.jetbrains.kotlin.jvm")))
_SKIP = {"build", ".gradle", ".git", "node_modules", "buildSrc", ".idea", "gradle", "src"}


def _catalogs(root: Path) -> dict[str, str]:
    """Plugin aliases of the version catalogs: `libs.plugins.android.application` and `findPlugin:android-application`
    -> `com.android.application` (`gradle/*.versions.toml`, the catalog name is the file name)."""
    out: dict[str, str] = {}
    for path in sorted((root / "gradle").glob("*.versions.toml")):
        try:
            data = tomllib.loads(_read(path))
        except tomllib.TOMLDecodeError:
            continue
        name = path.name.split(".")[0]
        for key, value in (data.get("plugins") or {}).items():
            plugin = value.split(":")[0] if isinstance(value, str) else (value or {}).get("id") if isinstance(value, dict) else None
            if plugin:
                out[f"{name}.plugins.{re.sub(r'[-_]', '.', key)}"] = plugin
                out[f"findPlugin:{key}"] = plugin
                out[f"findPlugin:{re.sub(r'[-_]', '.', key)}"] = plugin
    return out


def _plugin_ids(text: str, catalog: dict[str, str]) -> set[str]:
    """Plugins a script applies: ids, legacy `apply plugin`, `kotlin("x")`, catalog aliases (lines with `apply false`
    only declare a version and apply nothing)."""
    ids = set()
    for block in re.finditer(r"\bplugins\s*\{(?P<body>[^{}]*)\}", text):  # core plugins by bare name: `jacoco`, `java-library`
        ids.update(m.group(1) for m in re.finditer(r"^\s*`?([a-z][\w-]*)`?\s*$", block.group("body"), re.M))
    for line in text.splitlines():
        if "apply false" in line or "apply(false)" in line:
            continue
        for m in _PLUGIN_REF.finditer(line):
            if m.group("kotlin"):
                ids.add("org.jetbrains.kotlin." + m.group("kotlin"))
            elif m.group("alias"):
                ids.add(catalog.get(m.group("alias"), "alias:" + m.group("alias")))
            elif m.group("found"):
                ids.add(catalog.get("findPlugin:" + m.group("found"), "alias:" + m.group("found")))
            else:
                ids.add(m.group("id") or m.group("legacy") or m.group("applied"))
    return ids


def _conventions(root: Path, settings: str, catalog: dict[str, str]) -> dict[str, set[str]]:
    """Convention plugins of the included builds (buildSrc, build-logic, any `includeBuild`): plugin id -> the plugin
    ids it applies, resolved through other convention plugins. Precompiled script plugins are named by their file
    (and package); class plugins by their `gradlePlugin { register(...) { id; implementationClass } }` entry."""
    builds = ["buildSrc", *re.findall(r"""includeBuild\s*\(?\s*["']([^"']+)["']""", settings)]
    raw: dict[str, set[str]] = {}
    for name in dict.fromkeys(builds):
        folder = (root / name).resolve()
        if not folder.is_dir() or root.resolve() not in folder.parents:
            continue
        sources = [p for p in folder.rglob("*") if p.is_file() and "/src/main/" in p.as_posix() and p.suffix in (".kts", ".gradle", ".kt", ".java", ".groovy")]
        for script in sources:
            if script.name.endswith((".gradle.kts", ".gradle")):
                text = _read(script)
                plugin = script.name.removesuffix(".kts").removesuffix(".gradle")
                package = re.search(r"^\s*package\s+([\w.]+)", text, re.M)
                raw[f"{package.group(1)}.{plugin}" if package else plugin] = _plugin_ids(text, catalog)
        classes = {p.stem: p for p in sources if p.suffix in (".kt", ".java", ".groovy")}
        scripts = [p for n in _BUILD for p in folder.rglob(n) if not {"build", ".gradle"} & set(p.relative_to(folder).parts[:-1])]
        for script in scripts:  # gradlePlugin registrations, in the included build or any of its subprojects
            text = _read(script)
            for block in re.finditer(r"""(?:register|create)\s*\(?\s*["'][^"']+["']\s*\)?\s*\{(?P<body>[^{}]*)\}""", text):
                plugin = re.search(r"""\bid\s*=\s*["']([^"']+)["']""", block.group("body"))
                impl = re.search(r"""implementationClass\s*=\s*["']([\w.$]+)["']""", block.group("body"))
                if plugin and impl and impl.group(1).rsplit(".", 1)[-1] in classes:
                    raw[plugin.group(1)] = _plugin_ids(_read(classes[impl.group(1).rsplit(".", 1)[-1]]), catalog)
    resolved: dict[str, set[str]] = {}

    def expand(plugin: str, seen: frozenset) -> set[str]:
        if plugin in resolved:
            return resolved[plugin]
        out = set()
        for applied in raw.get(plugin, ()):
            out.add(applied)
            if applied in raw and applied not in seen:
                out |= expand(applied, seen | {applied})
        resolved[plugin] = out
        return out

    return {plugin: expand(plugin, frozenset({plugin})) for plugin in raw}


def _kmp_targets(text: str) -> list[str]:
    """JVM targets of a multiplatform module, by name: `jvm()` -> jvm, `jvm("desktop")` -> desktop."""
    return [m.group(1) or "jvm" for m in re.finditer(r"""\bjvm\s*\(\s*(?:name\s*=\s*)?(?:["']([\w-]+)["'])?""", text)]


def _flavors(text: str) -> list[str]:
    """Android product flavors named in the module script (`create("free")`, `register("free")`, Groovy `free {`)."""
    block = re.search(r"productFlavors\s*\{", text)
    if not block:
        return []
    depth, end = 0, None
    for i in range(block.end() - 1, len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if depth == 0:
            end = i
            break
    body = text[block.end():end]
    named = re.findall(r"""(?:create|register|maybeCreate)\s*\(\s*["']([\w]+)["']""", body)
    return named or [n for n in re.findall(r"^\s*(\w+)\s*\{", body, re.M) if n not in ("all", "configureEach")]


def modules(root: Path) -> list[dict]:
    """Modules with their build script, plugins, frameworks and test source sets (static, never executed).

    Plugins are resolved through version-catalog aliases and the convention plugins of included builds; a module
    whose plugins stay unresolved is classified by its layout (an Android manifest, Kotlin source sets). Directories
    with a build script that the settings do not include literally (computed includes) are listed as `declared:
    False`: their tasks are run only when Gradle's own task list confirms them."""
    root = Path(root)
    settings = next((_read(root / n) for n in _SETTINGS if (root / n).is_file()), "")
    catalog = _catalogs(root)
    conventions = _conventions(root, settings, catalog)
    included_builds = {"buildSrc", *(p.strip("./") for p in re.findall(r"""includeBuild\s*\(?\s*["']([^"']+)["']""", settings))}
    paths = [""]
    for match in _INCLUDE.finditer(settings):
        paths += [q.strip(":").replace(":", "/") for q in _QUOTED.findall(match.group(1))]
    declared = set(paths)
    for current, dirs, files in os.walk(root):  # build scripts the settings do not name literally
        rel = Path(current).relative_to(root).as_posix()
        dirs[:] = [d for d in dirs if d not in _SKIP and not d.startswith(".") and (f"{rel}/{d}" if rel != "." else d) not in included_builds]
        if rel != "." and rel.count("/") < 4 and any(f in files for f in _BUILD) and rel not in declared:
            paths.append(rel)
    out = []
    for rel in dict.fromkeys(paths):
        folder = root / rel if rel else root
        script = next((folder / n for n in _BUILD if (folder / n).is_file()), None)
        if script is None:
            continue
        text = _read(script)
        direct = _plugin_ids(text, catalog)
        plugins = set(direct)
        for plugin in direct:
            plugins |= conventions.get(plugin, set())
        kind = next((name for name, ids in _KINDS if plugins & set(ids)), None)
        basis = "plugins"
        if kind is None:  # unresolved plugins: the layout still says what the module is
            if (folder / "src" / "main" / "AndroidManifest.xml").is_file() and re.search(r"\bandroid\s*\{", text):
                kind, basis = "android", "layout"
            elif (folder / "src" / "commonMain").is_dir():
                kind, basis = "kmp", "layout"
            elif re.search(r"(?<![\w.])java\s*\{|sourceCompatibility", text) and (folder / "src" / "main").is_dir():
                kind, basis = "java", "layout"
            else:
                kind = "unknown"
        source_sets = sorted(p.name for p in (folder / "src").iterdir() if p.is_dir() and p.name.lower().endswith("test")) if (folder / "src").is_dir() else []
        conventions_text = " ".join(sorted(plugins))
        out.append({
            "path": rel or ".", "gradle_path": ":" + rel.replace("/", ":") if rel else "", "kind": kind, "kind_basis": basis,
            "declared": rel in declared, "plugins": sorted(p for p in plugins if not p.startswith("alias:")),
            "unresolved_plugins": sorted(p.removeprefix("alias:") for p in plugins if p.startswith("alias:")),
            "frameworks": sorted({name for key, name in _FRAMEWORKS.items() if key in text}),
            "coverage": [tool for tool, key in (("jacoco", "jacoco"), ("kover", "kover")) if key in text or key in conventions_text],
            "test_source_sets": source_sets,
            "flavors": _flavors(text) if kind == "android" else [],
            "jvm_targets": _kmp_targets(text) if kind == "kmp" else [],
        })
    return out


_VERIFICATION = re.compile(r"^Verification tasks\s*\n-+\s*\n(?P<body>(?:[^\n]+\n?)*)", re.M)
_NOT_UNIT = re.compile(r"^(check|connected\w*|device\w*|lint\w*|allTests|\w*AndroidTest|\w*TestReport|test\w*Coverage\w*)$")


def available_tests(output: str) -> dict[str, list[str]]:
    """Test tasks Gradle itself lists (`gradle tasks --all`, Verification group), per project path (`""` = root)."""
    out: dict[str, list[str]] = {}
    output = output.replace("\r\n", "\n")  # a blank line ends the section on every platform
    for section in _VERIFICATION.finditer(output):
        for line in section.group("body").splitlines():
            task = line.split(" - ", 1)[0].strip()
            if not task or " " in task:
                continue
            project, _, name = task.rpartition(":")
            if _NOT_UNIT.match(name) or not (name == "test" or name.endswith(("Test", "Tests"))):
                continue
            out.setdefault(":" + project if project else "", []).append(name)
    return out


def _tasks(module: dict, available: list[str] | None = None) -> tuple[list[str], dict[str, str]]:
    """Test tasks to run for a module, and the matrix entries that do not run here (with why). With Gradle's own task
    list (`available`) the choice is confirmed against it; without it, it is planned from the build scripts."""
    prefix, sets, matrix = module["gradle_path"], module["test_source_sets"], {}
    label = prefix or ":"
    if available is not None:
        chosen = _confirmed(module, available)
        for name in sorted(set(available) - set(chosen)):
            host = next((why for key, why in _KMP_HOSTS.items() if name.lower().startswith(key)), None)
            if module["kind"] == "kmp" and host:  # another target of the module: its host, not a custom task
                matrix[f"{label} {name}"] = f"NOT_RUN: {host}"
            elif name not in ("test",) and not re.match(r"test\w*(Debug|Release)\w*UnitTest$", name):
                matrix[f"{label} {name}"] = "AVAILABLE: a custom test task, not run by default (name it to run it)"
            elif name != "test":
                matrix[f"{label} {name}"] = "AVAILABLE: another variant, not run by default"
    if module["kind"] == "android":
        flavors = [f[:1].upper() + f[1:] for f in module.get("flavors") or []]
        planned = [f"test{f}DebugUnitTest" for f in flavors] or ["testDebugUnitTest"]
        tasks = [f"{prefix}:{t}" for t in (chosen if available is not None else planned)] if "test" in sets or available else []
        if "androidTest" in sets:
            matrix[f"{label} connectedAndroidTest (instrumented)"] = "NOT_RUN: needs a device or emulator; a physical device is never used without authorization"
        return tasks, matrix
    if module["kind"] == "kmp":
        targets = module.get("jvm_targets") or ["jvm"]
        planned = [f"{t}Test" for t in targets] if any(s in sets for s in (*[f"{t}Test" for t in targets], "commonTest")) else []
        tasks = [f"{prefix}:{t}" for t in (chosen if available is not None else planned)]
        for name in sets:
            target = name[: -len("Test")]
            if target in ("common", *targets):
                continue
            reason = next((why for key, why in _KMP_HOSTS.items() if target.lower().startswith(key)), "not run by this version")
            if target == "android":
                reason = "Android unit tests of a multiplatform module are not run by this version"
            matrix[f"{prefix or ':'} {name}"] = f"NOT_RUN: {reason}"
        return tasks, matrix
    if available is not None:
        return [f"{prefix}:{t}" for t in chosen], matrix
    return ([f"{prefix}:test"] if "test" in sets and module.get("declared", True) else []), matrix


def _confirmed(module: dict, available: list[str]) -> list[str]:
    """The standard local test tasks among those Gradle lists: Android debug unit tests of every flavor (else the
    first variant's), the JVM targets of a multiplatform module, `test` elsewhere."""
    if module["kind"] == "android":
        debug = [t for t in available if re.match(r"test\w*DebugUnitTest$", t)]
        return debug or sorted(t for t in available if re.match(r"test\w+UnitTest$", t))[:1]
    if module["kind"] == "kmp":
        return [f"{t}Test" for t in module.get("jvm_targets") or ["jvm"] if f"{t}Test" in available]
    return ["test"] if "test" in available else []


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
        provisioned = bool(environment.ACTIVE and environment.ACTIVE.tools.get("gradle") and environment.ACTIVE.workspace)
        home = environment.ACTIVE.env.get("GRADLE_USER_HOME") if environment.ACTIVE else None
        env = {**os.environ, "GRADLE_USER_HOME": home or str(tools_dir() / "gradle-home")}
        listing = None
        if not args:  # Gradle's own task list (configuration only, no test runs) confirms which test tasks exist
            command = [gradle, "--no-daemon", "--console=plain", "-q", "tasks", "--all", "-Dorg.gradle.jvmargs=-Xmx1g"]
            if not provisioned:
                command.insert(1, "--offline")
            listed = run_command(command, root, env=env, timeout_s=min(self.timeout_s, 900.0), output_limit=4_000_000)
            if listed.returncode == 0 and not listed.timed_out and not listed.error and "Verification tasks" in (listed.stdout or ""):
                listing = available_tests(listed.stdout or "")
        for module in found:
            module_tasks, module_matrix = _tasks(module, None if listing is None else listing.get(module["gradle_path"], []))
            matrix.update(module_matrix)
            if module["kind"] == "android" and module_tasks and not android_sdk and not (root / "local.properties").is_file():
                for task in module_tasks:
                    matrix[f"{module['gradle_path'] or ':'} {task.rsplit(':', 1)[-1]} (local)"] = "BLOCKED: no Android SDK (ANDROID_HOME) on this machine"
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
        command = [gradle, "--no-daemon", "--console=plain", "--continue", "-Dorg.gradle.jvmargs=-Xmx1g", *tasks]
        if not provisioned:
            command.insert(1, "--offline")
        result = run_command(command, root, env=env, timeout_s=self.timeout_s)
        run = RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.UNKNOWN, command=command,
                          exit_code=result.returncode, wall_clock_s=result.duration_s)
        run.limitations += FORMAT_LIMITS
        if listing is None and not args:
            run.limitations.append("Gradle's task list could not be read: test tasks were planned from the build scripts, not confirmed")
        run.metadata.update({"modules": found, "tasks": tasks, "offline": not provisioned,
                             "task_selection": "explicit" if args else "confirmed by Gradle's task list" if listing is not None else "planned from build scripts"})
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
