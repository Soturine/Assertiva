"""PIT (Java/Kotlin mutation testing) through the project's own Maven build, run by Assertiva on a disposable copy.

Assertiva neither installs PIT nor adds it to a build: the project's pom.xml must declare ``org.pitest:pitest-maven``
(with the test-framework plugin its tests need, such as ``pitest-junit5-plugin``), and Maven runs offline (``-o``), so
the plugin must already be in the local Maven repository; otherwise the run is BLOCKED with that reason. PIT copies
nothing into the project, but the build writes ``target/``, so it only runs inside a copy, and its XML report is
written outside that copy. The full mutation matrix is requested, so each mutant names every test that detects it.
Configuration the project declares for the plugin in its pom is Maven's to apply and wins over these properties.

Gradle builds that apply the PIT Gradle plugin are recognized but not run yet; their ``mutations.xml`` can be imported.
"""

from __future__ import annotations

import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from assertiva.models import MutationRun
from assertiva.process import execution_refusal, run_command

TOOL = "PIT"
KEY = "pit"
_SOURCE_ROOTS = ("src/main/java", "src/main/kotlin")
_TEST_ROOTS = ("src/test/java", "src/test/kotlin")
_SUFFIXES = (".java", ".kt")
_NS = re.compile(r"^\{[^}]*\}")
_LIMITS = [
    "mutants were executed by Assertiva on a disposable copy of this state through the project's Maven build, offline",
]


def _local(tag: str) -> str:
    return _NS.sub("", tag)


def _declares_plugin(pom: Path) -> bool:
    try:
        root = ET.parse(pom).getroot()
    except (OSError, ET.ParseError):
        return False
    for plugin in root.iter():
        if _local(plugin.tag) != "plugin":
            continue
        fields = {_local(child.tag): (child.text or "").strip() for child in plugin}
        if fields.get("groupId") == "org.pitest" and fields.get("artifactId") == "pitest-maven":
            return True
    return False


def build(root: Path) -> str | None:
    """``maven`` when the pom declares the PIT plugin, ``gradle`` when a Gradle build applies the PIT Gradle plugin."""
    root = Path(root)
    if (root / "pom.xml").is_file() and _declares_plugin(root / "pom.xml"):
        return "maven"
    for name in ("build.gradle", "build.gradle.kts"):
        try:
            if "info.solidsoft.pitest" in (root / name).read_text(encoding="utf-8", errors="replace"):
                return "gradle"
        except OSError:
            continue
    return None


def applies(root: Path) -> bool:
    return build(root) is not None


def _maven() -> str | None:
    from assertiva.adapters.maven import MavenAdapter

    return MavenAdapter()._maven()


def availability(root: Path) -> str | None:
    """Why PIT cannot run here, or None."""
    kind = build(root)
    if kind is None:
        return "the build does not declare the PIT plugin (org.pitest:pitest-maven); Assertiva does not add it"
    if kind == "gradle":
        return "PIT through Gradle is not run by Assertiva yet; import the build's mutations.xml with --mutation-report"
    if not _maven():
        return "Maven was not found (PATH or ASSERTIVA_MAVEN); the project's Maven wrapper is not run because it may download Maven"
    return None


def describe(root: Path, python: str, origin: Path) -> dict:
    """Applies to a build that declares the PIT plugin; Assertiva never adds it."""
    kind = build(root)
    return {"applies": kind is not None, "runner": kind, "blocked": availability(root) if kind else None,
            "why": f"the {kind} build declares the PIT plugin" if kind else "no build declares the PIT plugin"}


def execute(state_root: Path, python: str, targets: list[str], origin: Path, option: dict) -> MutationRun:
    return run(state_root, targets)


def unsafe_target(root: Path, target: str) -> str | None:
    """Why PIT must not mutate ``target`` under ``root``; see ``mutation.unsafe_target``. A target must also be a source
    of the main source set, since PIT mutates compiled classes named after it."""
    from assertiva.adapters.mutation import unsafe_target as check

    reason = check(root, target, _SUFFIXES)
    if reason is None and _class_name(target) is None:
        reason = f"not under {' or '.join(_SOURCE_ROOTS)}"
    return reason


def _class_name(target: str) -> str | None:
    posix = target.replace("\\", "/")
    for source_root in _SOURCE_ROOTS:
        if posix.startswith(source_root + "/"):
            return posix[len(source_root) + 1:].rsplit(".", 1)[0].replace("/", ".")
    return None


def run(state_root: str | Path, targets: list[str], timeout_s: float = 3600.0) -> MutationRun:
    """Mutate the classes of ``targets`` (source files relative to ``state_root``) with the project's PIT plugin."""
    from assertiva.adapters.mutation import load_mutation_report
    from assertiva.workspace import remove_tree, snapshot

    state_root = Path(state_root)
    result = MutationRun(source=f"{TOOL} run by Assertiva on {', '.join(targets)}", tool=TOOL, orchestrated=True,
                         targets=tuple(targets), limitations=list(_LIMITS))
    refusal = execution_refusal() or availability(state_root)
    if refusal:
        result.error = refusal
        return result
    bad = {t: reason for t in targets if (reason := unsafe_target(state_root, t))}
    if not targets or bad:
        result.error = ("mutation targets must be Java or Kotlin sources of the main source set, reached without links: "
                        + ("; ".join(f"{t}: {why}" for t, why in bad.items()) or "none given"))
        return result
    classes = sorted({c for t in targets for c in (_class_name(t), f"{_class_name(t)}$*")})
    with tempfile.TemporaryDirectory(prefix="assertiva-mutation-") as tmp:
        tmp = Path(tmp)
        copy = snapshot(state_root, tmp / "state")
        try:
            in_copy = {t: reason for t in targets if (reason := unsafe_target(copy, t))}
            if in_copy:
                result.error = "mutation targets are not plain files in the copy: " + "; ".join(f"{t}: {why}" for t, why in in_copy.items())
                return result
            reports = tmp / "pit-reports"
            properties = {"targetClasses": ",".join(classes), "outputFormats": "XML", "fullMutationMatrix": "true",
                          "timestampedReports": "false", "reportsDirectory": str(reports), "withHistory": "false",
                          "skipFailingTests": "false", "threads": "2"}
            command = [_maven(), "-B", "-o", "test-compile", "org.pitest:pitest-maven:mutationCoverage",
                       *(f"-D{key}={value}" for key, value in properties.items())]
            result.config = {"build": "maven", "offline": True, "goal": "org.pitest:pitest-maven:mutationCoverage",
                             **{k: v for k, v in properties.items() if k != "reportsDirectory"}}
            executed = run_command(command, copy, timeout_s=timeout_s, output_limit=1 << 22)
            report = reports / "mutations.xml"
            if not report.is_file():
                output = f"{executed.stdout}\n{executed.stderr}"
                if "offline" in output.lower() and "resolve" in output.lower():
                    why = "the PIT plugin or a dependency is missing from the local Maven repository; Assertiva runs Maven offline and never downloads them"
                elif "COMPILATION ERROR" in output:
                    why = "the project or its tests did not compile"
                elif "tests did not pass without mutation" in output.lower():
                    why = "the tests do not pass on this state before mutation; no mutant was run"
                else:
                    why = f"PIT wrote no mutations.xml ({executed.summary()})"
                result.error = why
                return result
            parsed = load_mutation_report(report)
            if parsed.error:
                result.error = parsed.error
                return result
            by_suffix = {t.replace("\\", "/").split("/", 3)[-1]: t for t in targets}  # package/File.java -> target
            parsed.mutants = [replace(m, path=by_suffix.get(m.path or "", m.path)) for m in parsed.mutants]
            for killer, location in list(parsed.test_locations.items()):
                for test_root in _TEST_ROOTS:
                    for suffix in _SUFFIXES:
                        if (copy / test_root / (location + suffix)).is_file():
                            parsed.test_locations[killer] = f"{test_root}/{location}{suffix}"
            if not executed.ok:
                result.limitations.append(f"{TOOL} exited with an error ({executed.summary()}); results it did not finish are UNKNOWN")
            for field in ("mutants", "counts", "test_locations", "test_names", "killers_complete", "tool_version"):
                setattr(result, field, getattr(parsed, field))
            result.limitations += [x for x in parsed.limitations if "does not record which revision" not in x]
            result.sources = {t: (copy / t).read_text(encoding="utf-8") for t in targets}
            result.test_sources = {p.relative_to(copy).as_posix(): p.read_text(encoding="utf-8", errors="replace")
                                   for test_root in _TEST_ROOTS if (copy / test_root).is_dir()
                                   for p in sorted((copy / test_root).rglob("*")) if p.suffix in _SUFFIXES}
        finally:
            remove_tree(copy)
    return result
