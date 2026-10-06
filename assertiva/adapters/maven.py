"""Maven adapter: Surefire (test phase) and Failsafe (integration-test phase) results, JaCoCo coverage.

Each report file is read by the generic JUnit XML parser; this adapter adds only what that format
cannot know: which plugin and phase produced it, reruns and flaky passes, parameterized invocations
of one method, the test's source file, and the project's own JaCoCo report. System properties in
the reports (paths, user, host) are never copied. Maven runs offline (``-o``): only dependencies
already in the local repository are used; nothing is downloaded and the project's wrapper is not run.
"""

from __future__ import annotations

import os
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from assertiva.candidate import StageStatus
from assertiva.models import Outcome, RunEvidence, TestInvocation
from assertiva.process import execution_refusal, run_command
from assertiva.verification import GateMode, SupportLevel, VerificationCheck, VerificationKind, VerificationOrigin

from .base import AdapterCapability
from .coverage_reports import load_coverage_report
from .junit import load_junit

# (report directory, lifecycle phase, plugin)
_PHASES = (("surefire-reports", "test", "surefire"), ("failsafe-reports", "integration-test", "failsafe"))
_PARAMETERIZED = re.compile(r"^(?P<method>[^\[(]+)(?:\([^)]*\))?(?P<index>\[\d+\])$")
_FAILSAFE_DEFAULT = re.compile(r"(^IT[^.]*|IT|ITCase)$")  # Failsafe's documented default includes
_COSMETIC = {"-B", "--batch-mode", "-q", "--quiet", "-e", "--errors", "-ntp", "--no-transfer-progress", "-V", "--show-version"}
_NO_SELECTION = "AssertivaNoSelectedTests"
_NS = re.compile(r"^\{[^}]*\}")
FORMAT_LIMITS = [
    "Surefire runs tests in the test phase and Failsafe in the integration-test phase; this is how the build classifies them, not proof of their scope",
    "results come from the reports written by this Maven run; Maven ran offline with test failures recorded instead of stopping the build",
]


def _local(tag: str) -> str:
    return _NS.sub("", tag)


def _source(root: Path, classname: str) -> tuple[str, ...]:
    outer = classname.split("$", 1)[0]
    rel = Path("src", "test", "java", *outer.split(".")).with_suffix(".java")
    return (rel.as_posix(),) if (root / rel).is_file() else ()


def _maven_context(path: Path) -> list[tuple[str, str, int, int]]:
    """(classname, name, flaky attempts, failed reruns) per testcase, in document order."""
    cases = []
    for case in ET.parse(path).getroot().iter("testcase"):
        flaky = sum(1 for child in case if child.tag in ("flakyFailure", "flakyError"))
        reruns = sum(1 for child in case if child.tag in ("rerunFailure", "rerunError"))
        cases.append((case.get("classname") or "", case.get("name") or "", flaky, reruns))
    return cases


def report_state(root: str | Path) -> dict[str, tuple[int, int]]:
    """Report files already present (path -> mtime_ns, size), so a run only reads what it wrote."""
    target = Path(root) / "target"
    files = [*(p for d, _, _ in _PHASES for p in (target / d).glob("TEST-*.xml")), target / "site" / "jacoco" / "jacoco.xml"]
    return {str(p): (p.stat().st_mtime_ns, p.stat().st_size) for p in files if p.is_file()}


def parse_maven_reports(root: str | Path, previous: dict[str, tuple[int, int]] | None = None) -> RunEvidence:
    """Normalize the Surefire/Failsafe reports (and JaCoCo report) under ``root/target``.

    Files unchanged since ``previous`` (taken before a run) are stale and ignored.
    """
    root = Path(root)
    run = RunEvidence(adapter_id="maven", mode="execute", status=StageStatus.UNKNOWN)
    target = root / "target"

    def fresh(path: Path) -> bool:
        return previous is None or previous.get(str(path)) != (path.stat().st_mtime_ns, path.stat().st_size)

    reports = {phase: sorted(p for p in (target / directory).glob("TEST-*.xml") if fresh(p)) for directory, phase, _ in _PHASES}
    if not any(reports.values()):
        run.status = StageStatus.BLOCKED
        run.limitations.append("no Surefire or Failsafe report was produced by this run; test outcomes are unknown")
        return run
    run.limitations += FORMAT_LIMITS
    unreadable, retried = [], []
    matrix = {}
    for directory, phase, plugin in _PHASES:
        executed = False
        for path in reports[phase]:
            generic = load_junit(path)
            try:
                context = _maven_context(path)
            except (OSError, ET.ParseError):
                context = None
            if generic.status is StageStatus.BLOCKED or context is None or len(context) != len(generic.invocations):
                unreadable.append(path.name)
                continue
            for inv, (classname, name, flaky, reruns) in zip(generic.invocations, context):
                match = _PARAMETERIZED.match(name)
                method = match.group("method") if match else name.split("(", 1)[0]
                invocation_id = f"{classname}#{name}"
                message = inv.message
                if flaky and inv.outcome is Outcome.PASSED:
                    retried.append(invocation_id)
                    message = f"passed after {flaky + 1} attempts (earlier attempts failed)"
                elif reruns and inv.outcome in (Outcome.FAILED, Outcome.ERROR):
                    message = f"failed in all {reruns + 1} attempts" + (f": {message}" if message else "")
                executed = executed or inv.outcome is not Outcome.SKIPPED
                run.invocations.append(TestInvocation(
                    invocation_id=invocation_id, declaration_id=f"{classname}#{method}", materialization_id=f"{classname}#{method}",
                    parameters_id=match.group("index") if match else None, markers=(f"maven:{phase}",), outcome=inv.outcome,
                    duration_s=inv.duration_s, message=message, source_paths=_source(root, classname),
                ))
        matrix[f"phase {phase} ({plugin})"] = "EXECUTED" if executed else ("SELECTED" if reports[phase] else "NOT_RUN")
    run.metadata["matrix"] = matrix
    if unreadable:
        run.limitations.append("reports that could not be read provide no evidence: " + ", ".join(unreadable[:10]))
    if retried:
        run.limitations.append("retried tests passed only after earlier failed attempts: " + ", ".join(retried[:5]))
    jacoco = target / "site" / "jacoco" / "jacoco.xml"
    if jacoco.is_file() and fresh(jacoco):
        coverage = load_coverage_report(jacoco)
        run.coverage = replace(coverage, scope="project JaCoCo configuration (report goal)") if coverage.error is None else None
        if (target / "site" / "jacoco-it" / "jacoco.xml").is_file():
            run.limitations.append("a separate JaCoCo integration-test report exists and is not merged into this coverage")
    outcomes = {inv.outcome for inv in run.invocations}
    if outcomes & {Outcome.FAILED, Outcome.ERROR}:
        run.status = StageStatus.FAIL
    elif unreadable:
        run.status = StageStatus.BLOCKED
    elif not outcomes & {Outcome.PASSED}:
        run.status = StageStatus.UNKNOWN
        run.limitations.append("no test was executed; this is not evidence of a passing suite")
    else:
        run.status = StageStatus.PASS
    return run


def maven_arguments(args: list[str] | None = None) -> list[str]:
    """Offline Maven arguments; invocation ids (``Class#method``) become per-phase test selections."""
    args = list(args or [])
    selected = [a for a in args if "#" in a and not a.startswith("-")]
    rest = [a for a in args if a not in selected]
    command = ["-B", "-o", "-Dmaven.test.failure.ignore=true"]
    if selected:
        unit, integration = [], []
        for item in selected:
            classname, method = item.split("#", 1)
            match = _PARAMETERIZED.match(method)
            method = match.group("method") if match else method.split("(", 1)[0]
            simple = classname.rsplit(".", 1)[-1].split("$", 1)[0]
            bucket = integration if _FAILSAFE_DEFAULT.search(simple) else unit
            entry = f"{classname}#{method}"
            if entry not in bucket:
                bucket.append(entry)
        command += [f"-Dtest={','.join(unit) or _NO_SELECTION}", "-Dsurefire.failIfNoSpecifiedTests=false"]
        command += [f"-Dit.test={','.join(integration)}", "-Dfailsafe.failIfNoSpecifiedTests=false"] if integration else ["-DskipITs=true"]
    goals = [a for a in rest if not a.startswith("-")]
    return command + rest + ([] if goals else ["verify"])


class MavenAdapter:
    adapter_id = "maven"

    def __init__(self, python: str | None = None, timeout_s: float = 1200.0):
        self.timeout_s = timeout_s  # `python` is accepted for the common factory signature only

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / "pom.xml").is_file() else SupportLevel.UNSUPPORTED

    def capabilities(self) -> tuple[AdapterCapability, ...]:
        return (
            AdapterCapability("structured_results", SupportLevel.SUPPORTED, "Surefire/Failsafe XML via the generic JUnit XML parser"),
            AdapterCapability("parameter_identity", SupportLevel.SUPPORTED, "JUnit Platform invocation index"),
            AdapterCapability("phase_classification", SupportLevel.SUPPORTED, "Surefire test / Failsafe integration-test"),
            AdapterCapability("coverage", SupportLevel.SUPPORTED, "the project's JaCoCo report"),
            AdapterCapability("static_oracle_analysis", SupportLevel.UNSUPPORTED),
        )

    def _maven(self) -> str | None:
        configured = os.environ.get("ASSERTIVA_MAVEN")
        if configured:
            return configured if Path(configured).is_file() else None
        return shutil.which("mvn")

    def run(self, root: str | Path, args: list[str] | None = None, coverage: bool = False) -> RunEvidence:
        root = Path(root)

        def blocked(reason: str, **extra) -> RunEvidence:
            return RunEvidence(adapter_id=self.adapter_id, mode="execute", status=StageStatus.BLOCKED, limitations=[reason], **extra)

        refusal = execution_refusal()
        if refusal:
            return blocked(refusal)
        maven = self._maven()
        if not maven:
            return blocked("Maven was not found (PATH or ASSERTIVA_MAVEN); the project's Maven wrapper is not run because it may download Maven")
        command = [maven, *maven_arguments(args)]
        previous = report_state(root)
        result = run_command(command, root, timeout_s=self.timeout_s)
        run = parse_maven_reports(root, previous)
        if any(_PARAMETERIZED.match(a.split("#", 1)[-1]) for a in args or () if "#" in a):
            run.limitations.append("Maven selects tests per method: every parameterized case of a selected method ran")
        run.command, run.exit_code, run.wall_clock_s = command, result.returncode, result.duration_s
        output = f"{result.stdout}\n{result.stderr}"
        if run.status is StageStatus.BLOCKED:
            if "COMPILATION ERROR" in output:
                run.status = StageStatus.FAIL
                run.collection_errors.append("maven compilation")
                run.metadata["error_sources"] = {"maven compilation": "src"}
                run.limitations.insert(0, "the project or its tests did not compile")
            elif "offline" in output.lower() and "resolve" in output.lower():
                run.limitations.insert(0, "dependencies or plugins are missing from the local Maven repository; Assertiva runs Maven offline and never downloads them")
            elif result.error or result.timed_out:
                run.limitations.insert(0, f"Maven did not run: {result.summary()}")
        if coverage and run.coverage is None and run.invocations:
            run.limitations.append("coverage requires the project's own JaCoCo report goal; none was produced")
        return run

    def static_signals(self, root) -> dict[str, int]:
        return {}

    def static_negative_paths(self, root) -> dict[str, list[str]]:
        return {}

    def reproduction_args(self, check) -> list[str] | None:
        """Maven arguments reproducing a delivery check (`mvn ...` or `./mvnw ...`, run with Maven itself)."""
        if check.tool in ("mvn", "./mvnw") and check.command and "${{" not in check.command:
            return list(check.metadata.get("runner_args", []))
        return None

    def equivalent_to_default(self, args: list[str]) -> bool:
        flags = [a for a in args if a.startswith("-")]
        goals = [a for a in args if not a.startswith("-")]
        return all(a in _COSMETIC for a in flags) and goals in ([], ["verify"])


def _children(element: ET.Element | None, name: str) -> list[ET.Element]:
    return [] if element is None else [child for child in element if _local(child.tag) == name]


def _child(element: ET.Element | None, name: str) -> ET.Element | None:
    found = _children(element, name)
    return found[0] if found else None


def _text(element: ET.Element | None, name: str) -> str | None:
    found = _child(element, name)
    return (found.text or "").strip() if found is not None else None


class MavenBuildSurfaceAdapter:
    """The checks a Maven build declares in ``pom.xml`` (discovery only; nothing is executed)."""

    adapter_id = "maven-build"

    def supports(self, root: Path) -> SupportLevel:
        return SupportLevel.SUPPORTED if (Path(root) / "pom.xml").is_file() else SupportLevel.UNSUPPORTED

    def discover(self, root: Path) -> list[VerificationCheck]:
        def check(check_id, kind, gate, command, limitations=(), **metadata):
            return VerificationCheck(check_id=check_id, kind=kind, origin=VerificationOrigin.BUILD, gate=gate, command=command,
                                     tool="mvn", source="pom.xml", adapter_id=self.adapter_id, evidence_tier="E2",
                                     limitations=tuple(limitations), metadata={"runner_args": command.split()[1:], **metadata})

        try:
            project = ET.parse(Path(root) / "pom.xml").getroot()
        except (OSError, ET.ParseError) as exc:
            return [VerificationCheck(check_id="maven-build", kind=VerificationKind.UNKNOWN, origin=VerificationOrigin.BUILD,
                                      source="pom.xml", adapter_id=self.adapter_id, evidence_tier="E2",
                                      limitations=(f"pom.xml could not be read: {exc}"[:200],))]
        plugins = {
            _text(p, "artifactId"): p for p in _children(_child(_child(project, "build"), "plugins"), "plugin")
        }
        notes = ["plugins declared only in profiles or parent POMs are not resolved"]

        def goals(plugin) -> set[str]:
            return {(g.text or "").strip() for e in _children(_child(plugin, "executions"), "execution")
                    for g in _children(_child(e, "goals"), "goal")}

        def ignores_failures(plugin) -> bool:
            config = _child(plugin, "configuration")
            return any(_text(config, name) == "true" for name in ("testFailureIgnore", "skipTests", "skip"))

        surefire = plugins.get("maven-surefire-plugin")
        checks = [check("maven:test", VerificationKind.TEST,
                        GateMode.ADVISORY if surefire is not None and ignores_failures(surefire) else GateMode.BLOCKING,
                        "mvn test", ["Surefire is bound to the test phase by the default lifecycle", *notes])]
        failsafe = plugins.get("maven-failsafe-plugin")
        if failsafe is not None:
            declared = goals(failsafe)
            limitations = [] if "verify" in declared else ["Failsafe declares no verify goal: integration test failures never fail the build"]
            gate = GateMode.BLOCKING if "verify" in declared and not ignores_failures(failsafe) else GateMode.ADVISORY
            checks.append(check("maven:integration-test", VerificationKind.TEST, gate, "mvn verify", limitations, goals=sorted(declared)))
        jacoco = plugins.get("jacoco-maven-plugin")
        if jacoco is not None:
            declared = goals(jacoco)
            gate = GateMode.BLOCKING if "check" in declared else GateMode.ADVISORY
            limitations = [] if "check" in declared else ["JaCoCo only reports coverage; no check goal enforces a threshold"]
            checks.append(check("maven:jacoco", VerificationKind.COVERAGE, gate, "mvn verify", limitations, goals=sorted(declared)))
        return checks
