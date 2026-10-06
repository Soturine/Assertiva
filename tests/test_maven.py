"""Java slice: Maven Surefire/Failsafe results and JaCoCo coverage through the shared core.

The generic JUnit XML parser reads each report; the Maven adapter adds only build context."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from assertiva.adapters.maven import MavenAdapter, MavenBuildSurfaceAdapter, maven_arguments, parse_maven_reports, report_state
from assertiva.candidate import QualificationCheck, StageStatus
from assertiva.evidence import to_jsonable
from assertiva.models import Outcome
from assertiva.verification import GateMode, VerificationKind

from conftest import write

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT = FIXTURES / "java-maven"
VARIANTS = FIXTURES / "maven-reports" / "variants"  # real Surefire 3.6.0 / Failsafe 3.6.0 / JaCoCo 0.8.15 output


def by_id(run):
    return {inv.invocation_id.removeprefix("dev.assertiva.fixture."): inv for inv in run.invocations}


# --- reports: generic JUnit XML plus Maven context -------------------------------------------

def test_outcomes_phases_and_reruns_from_real_reports():
    run = parse_maven_reports(VARIANTS)
    tests = by_id(run)
    assert run.status is StageStatus.FAIL
    assert {k: v.outcome for k, v in tests.items()} == {
        "PriceTest#appliesTierDiscount(int, String, int)[1]": Outcome.PASSED,
        "PriceTest#appliesTierDiscount(int, String, int)[2]": Outcome.PASSED,
        "PriceTest#appliesTierDiscount(int, String, int)[3]": Outcome.PASSED,
        "PriceTest#rejectsNegativeTotals": Outcome.PASSED,
        "PriceTest#appliesCoupons": Outcome.SKIPPED,
        "VariantsTest#wrongExpectation": Outcome.FAILED,
        "VariantsTest#unexpectedException": Outcome.ERROR,
        "VariantsTest#passesOnRerun": Outcome.PASSED,
        "PriceIT#vipCheckoutEndToEnd": Outcome.PASSED,
        "BrokenIT#regularCheckout": Outcome.FAILED,
    }
    assert tests["PriceIT#vipCheckoutEndToEnd"].markers == ("maven:integration-test",)
    assert tests["PriceTest#rejectsNegativeTotals"].markers == ("maven:test",)
    assert "2 attempts" in tests["VariantsTest#passesOnRerun"].message
    assert "all 2 attempts" in tests["VariantsTest#wrongExpectation"].message
    assert any("passesOnRerun" in lim for lim in run.limitations)
    assert any("integration-test phase" in lim and "not proof" in lim for lim in run.limitations)
    assert run.metadata["matrix"] == {"phase test (surefire)": "EXECUTED", "phase integration-test (failsafe)": "EXECUTED"}


def test_parameterized_invocations_share_one_declaration():
    tests = by_id(parse_maven_reports(VARIANTS))
    cases = [v for k, v in tests.items() if "appliesTierDiscount" in k]
    assert {c.declaration_id for c in cases} == {"dev.assertiva.fixture.PriceTest#appliesTierDiscount"}
    assert sorted(c.parameters_id for c in cases) == ["[1]", "[2]", "[3]"]


def test_jacoco_counts_from_the_projects_report():
    coverage = parse_maven_reports(VARIANTS).coverage
    assert coverage.tool == "jacoco" and "JaCoCo" in coverage.scope
    assert coverage.counts["line"] == {"covered": 5, "total": 5} and coverage.counts["branch"] == {"covered": 6, "total": 6}


def test_source_files_are_resolved_from_class_names():
    run = parse_maven_reports(_reports_project(PROJECT, VARIANTS))
    tests = by_id(run)
    assert tests["PriceTest#rejectsNegativeTotals"].source_paths == ("src/test/java/dev/assertiva/fixture/PriceTest.java",)
    assert tests["VariantsTest#wrongExpectation"].source_paths == ()  # not in this project's sources


def _reports_project(sources: Path, reports: Path) -> Path:
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="maven-reports-"))
    shutil.copytree(sources / "src", root / "src")
    shutil.copy2(sources / "pom.xml", root / "pom.xml")
    shutil.copytree(reports / "target", root / "target")
    return root


def test_machine_system_properties_are_never_copied(tmp_path):
    report = (VARIANTS / "target" / "surefire-reports" / "TEST-dev.assertiva.fixture.PriceTest.xml").read_text(encoding="utf-8")
    report = report.replace('flakes="0">', 'flakes="0">\n  <properties>\n    <property name="user.home" value="/home/secret-user"/>\n  </properties>', 1)
    write(tmp_path / "target" / "surefire-reports" / "TEST-dev.assertiva.fixture.PriceTest.xml", report)
    run = parse_maven_reports(tmp_path)
    assert run.invocations and "secret-user" not in json.dumps(to_jsonable(run))


def test_malformed_missing_and_stale_reports_are_not_evidence(tmp_path):
    missing = parse_maven_reports(tmp_path)
    assert missing.status is StageStatus.BLOCKED and any("no Surefire or Failsafe report" in lim for lim in missing.limitations)

    write(tmp_path / "target" / "surefire-reports" / "TEST-Broken.xml", "<testsuite name=")
    malformed = parse_maven_reports(tmp_path)
    assert malformed.status is StageStatus.BLOCKED and any("TEST-Broken.xml" in lim for lim in malformed.limitations)

    stale = tmp_path / "stale"
    shutil.copytree(VARIANTS / "target", stale / "target")
    before = report_state(stale)  # e.g. a previous run in the same copy
    run = parse_maven_reports(stale, before)
    assert run.status is StageStatus.BLOCKED and run.coverage is None and not run.invocations
    rewritten = stale / "target" / "failsafe-reports" / "TEST-dev.assertiva.fixture.PriceIT.xml"
    rewritten.write_text(rewritten.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert [i.invocation_id for i in parse_maven_reports(stale, before).invocations] == ["dev.assertiva.fixture.PriceIT#vipCheckoutEndToEnd"]


# --- execution safety ------------------------------------------------------------------------

def test_command_is_offline_and_selects_invocations():
    args = maven_arguments(["dev.x.PriceTest#appliesTierDiscount(int, String, int)[1]", "dev.x.PriceIT#vip", "dev.x.Other#a"])
    assert args[:2] == ["-B", "-o"] and "-Dmaven.test.failure.ignore=true" in args and args[-1] == "verify"
    # Failsafe's documented default includes decide the phase: each test runs only where it belongs.
    assert "-Dtest=dev.x.PriceTest#appliesTierDiscount,dev.x.Other#a" in args and "-Dit.test=dev.x.PriceIT#vip" in args
    assert "-Dsurefire.failIfNoSpecifiedTests=false" in args and "-Dfailsafe.failIfNoSpecifiedTests=false" in args
    assert maven_arguments(["-B", "test"])[-1] == "test" and "verify" not in maven_arguments(["-B", "test"])


def test_reproduction_and_equivalence():
    from assertiva.adapters.commands import classify_command
    from assertiva.verification import VerificationCheck, VerificationOrigin

    def check(command):
        cls = classify_command(command)
        return VerificationCheck(check_id="ci", kind=cls.kind, origin=VerificationOrigin.CI, command=command, tool=cls.tool,
                                 metadata={"runner_args": list(cls.runner_args)})

    adapter = MavenAdapter()
    assert adapter.reproduction_args(check("mvn -B verify")) == ["-B", "verify"]
    assert adapter.equivalent_to_default(["-B", "verify"]) and adapter.equivalent_to_default(["--no-transfer-progress", "verify"])
    assert not adapter.equivalent_to_default(["test"])
    assert adapter.reproduction_args(check("pytest -q")) is None


# --- discovery: the build's own verification surface ------------------------------------------

def test_build_surface_from_pom():
    checks = {c.check_id: c for c in MavenBuildSurfaceAdapter().discover(PROJECT)}
    assert checks["maven:test"].kind is VerificationKind.TEST and checks["maven:test"].gate is GateMode.BLOCKING
    assert checks["maven:integration-test"].gate is GateMode.BLOCKING
    assert checks["maven:jacoco"].kind is VerificationKind.COVERAGE and checks["maven:jacoco"].gate is GateMode.ADVISORY


def test_failsafe_without_verify_never_fails_the_build(tmp_path):
    pom = (PROJECT / "pom.xml").read_text(encoding="utf-8").replace("              <goal>verify</goal>\n", "")
    pom = pom.replace("<goal>report</goal>", "<goal>report</goal>\n              <goal>check</goal>")
    write(tmp_path / "pom.xml", pom)
    checks = {c.check_id: c for c in MavenBuildSurfaceAdapter().discover(tmp_path)}
    failsafe = checks["maven:integration-test"]
    assert failsafe.gate is GateMode.ADVISORY and any("never fail the build" in lim for lim in failsafe.limitations)
    assert checks["maven:jacoco"].gate is GateMode.BLOCKING  # a check goal enforces coverage rules


def test_unreadable_pom_is_reported_not_guessed(tmp_path):
    write(tmp_path / "pom.xml", "<project><build>")
    [check] = MavenBuildSurfaceAdapter().discover(tmp_path)
    assert check.kind is VerificationKind.UNKNOWN and "could not be read" in check.limitations[0]


# --- real Maven runs (JDK, Maven and the fixture's dependencies in the local repository) -------

def _maven():
    return os.environ.get("ASSERTIVA_MAVEN") or shutil.which("mvn")


@pytest.fixture
def java_project(tmp_path):
    maven = _maven()
    if not maven or not Path(maven).is_file() or not (os.environ.get("JAVA_HOME") or shutil.which("java")):
        reason = "requires a JDK, Maven and the fixture's dependencies resolved once (mvn -f tests/fixtures/java-maven verify)"
        if os.environ.get("ASSERTIVA_REQUIRE_JAVA"):
            pytest.fail(reason)
        pytest.skip(reason)
    root = tmp_path / "java-project"
    shutil.copytree(PROJECT / "src", root / "src")
    shutil.copy2(PROJECT / "pom.xml", root / "pom.xml")
    write(root / ".gitignore", "target/\n")
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)
    return root


@pytest.mark.integration
@pytest.mark.jvm
def test_real_maven_run_through_audit(java_project):
    from assertiva.audit import run_audit
    from assertiva.report import render_html

    report = run_audit(java_project, execute=True)
    [run] = [r for r in report["states"]["current"]["runs"] if r["adapter"] == "maven"]
    assert (run["status"], run["invocations"]) == ("PASS", 6), run
    assert run["matrix"] == {"phase test (surefire)": "EXECUTED", "phase integration-test (failsafe)": "EXECUTED"}
    metrics = report["states"]["current"]["metrics"]
    assert metrics["line_covered"]["value"] == 5 and metrics["branch_coverage"]["value"] == 100 and metrics["skipped"]["value"] == 1
    assert {"maven:test", "maven:integration-test", "maven:jacoco"} <= {c["check_id"] for c in report["verification_surface"]}
    assert "maven:integration-test" in render_html(report)


@pytest.mark.integration
@pytest.mark.jvm
def test_real_maven_candidate_qualification(java_project):
    from assertiva.improve import discard_session, qualify_candidate, start_improve

    session = start_improve(java_project)
    try:
        test_dir = session.workspace / "src" / "test" / "java" / "dev" / "assertiva" / "fixture"
        write(test_dir / "BoundaryTest.java",
              "package dev.assertiva.fixture;\n\nimport static org.junit.jupiter.api.Assertions.assertEquals;\n\n"
              "import org.junit.jupiter.api.Test;\n\nclass BoundaryTest {\n    @Test\n    void zeroTotal() {\n"
              '        assertEquals(0, Price.discount(0, "VIP"));\n    }\n}\n')
        q = qualify_candidate(session, stability_reruns=0).qualification
        stages = {c.check: c.status for c in q.checks}
        assert stages[QualificationCheck.CANDIDATE_TESTS] is StageStatus.PASS
        assert stages[QualificationCheck.ORIGINAL_REGRESSION] is StageStatus.PASS
        source = session.workspace / "src" / "main" / "java" / "dev" / "assertiva" / "fixture" / "Price.java"
        source.write_text(source.read_text(encoding="utf-8").replace("total * 90", "total * 80"), encoding="utf-8")
        broken = {c.check: c.status for c in qualify_candidate(session, stability_reruns=0).qualification.checks}
        assert broken[QualificationCheck.ORIGINAL_REGRESSION] is StageStatus.FAIL
    finally:
        discard_session(session)


@pytest.mark.integration
@pytest.mark.jvm
def test_real_selection_runs_each_test_in_its_own_phase_and_ignores_stale_reports(java_project):
    adapter = MavenAdapter()
    unit = adapter.run(java_project, args=["dev.assertiva.fixture.PriceTest#rejectsNegativeTotals"])
    assert [i.invocation_id for i in unit.invocations] == ["dev.assertiva.fixture.PriceTest#rejectsNegativeTotals"]
    integration = adapter.run(java_project, args=["dev.assertiva.fixture.PriceIT#vipCheckoutEndToEnd"])
    assert [i.invocation_id for i in integration.invocations] == ["dev.assertiva.fixture.PriceIT#vipCheckoutEndToEnd"]
    assert integration.metadata["matrix"] == {"phase test (surefire)": "NOT_RUN", "phase integration-test (failsafe)": "EXECUTED"}
