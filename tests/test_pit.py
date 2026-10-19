"""PIT through the project's own Maven build: when it applies, how its report is read, and a real run on a copy.

The real run needs a JDK, Maven and the fixture's build and PIT plugin resolved once into the local repository
(``mvn -f tests/fixtures/java-pit/pom.xml test-compile org.pitest:pitest-maven:mutationCoverage``); Assertiva runs
Maven offline. It skips without them, and fails instead with ASSERTIVA_REQUIRE_JAVA=1 (the CI java job).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from assertiva import cli
from assertiva.adapters import pit
from assertiva.adapters.mutation import load_mutation_report, mutation_tools, run_mutation_tool
from assertiva.workspace import tree_fingerprint

from conftest import write

PROJECT = Path(__file__).parent / "fixtures" / "java-pit"
_MATRIX = """<?xml version="1.0" encoding="UTF-8"?>
<mutations partial="false">
<mutation detected="true" status="KILLED" numberOfTestsRun="2">
<sourceFile>Pricing.java</sourceFile><mutatedClass>dev.assertiva.pit.Pricing</mutatedClass>
<mutatedMethod>discountCents</mutatedMethod><methodDescription>(IZ)I</methodDescription><lineNumber>9</lineNumber>
<mutator>org.pitest.mutationtest.engine.gregor.mutators.ConditionalsBoundaryMutator</mutator>
<indexes><index>{index}</index></indexes><blocks><block>1</block></blocks>
<killingTests>dev.assertiva.pit.PricingTest.[engine:junit-jupiter]/[class:dev.assertiva.pit.PricingTest]/[method:theThresholdIsInclusive()]</killingTests>
<succeedingTests></succeedingTests><description>changed conditional boundary</description>
</mutation>
</mutations>
"""


def test_a_pit_mutant_keeps_its_identity_and_names_its_junit_test(tmp_path):
    report = write(tmp_path / "mutations.xml", _MATRIX.format(index=7))
    run = load_mutation_report(report)
    [mutant] = run.mutants
    assert mutant.stable_id.endswith(":discountCents(IZ)I:9:org.pitest.mutationtest.engine.gregor.mutators.ConditionalsBoundaryMutator:7")
    [killer] = mutant.killed_by
    assert run.test_names[killer] == "PricingTest.theThresholdIsInclusive" and run.killers_complete is True
    other = load_mutation_report(write(tmp_path / "other.xml", _MATRIX.format(index=8))).mutants[0]
    assert other.stable_id != mutant.stable_id  # another instruction of the same line is another mutant


def test_pit_applies_only_to_a_build_that_declares_it(tmp_path):
    write(tmp_path / "pom.xml", "<project><build><plugins><plugin><groupId>org.apache.maven.plugins</groupId>"
                                "<artifactId>maven-surefire-plugin</artifactId></plugin></plugins></build></project>")
    [option] = [o for o in mutation_tools(tmp_path, sys.executable) if o["tool"] == "pit"]
    assert not option["applies"] and "no build declares" in option["why"]
    run = run_mutation_tool(tmp_path, sys.executable, ["src/main/java/A.java"], tool="pit")
    assert "no integrated mutation tool applies" in run.error and run.counts == {}


def test_pit_through_gradle_is_recognized_and_blocked_with_the_import_route(tmp_path):
    write(tmp_path / "build.gradle.kts", 'plugins {\n    id("info.solidsoft.pitest") version "1.19.0"\n}\n')
    [option] = [o for o in mutation_tools(tmp_path, sys.executable) if o["tool"] == "pit"]
    assert option["applies"] and option["runner"] == "gradle" and "--mutation-report" in option["blocked"]


def test_a_pit_target_must_be_a_main_source_reached_without_links(tmp_path):
    shutil.copytree(PROJECT, tmp_path / "p", ignore=shutil.ignore_patterns("target", "strengthened"))
    root = tmp_path / "p"
    assert pit.unsafe_target(root, "src/main/java/dev/assertiva/pit/Pricing.java") is None
    assert "src/main/java" in pit.unsafe_target(root, "src/test/java/dev/assertiva/pit/PricingTest.java")
    assert pit.unsafe_target(root, "pom.xml")


def _maven_ready() -> None:
    maven = os.environ.get("ASSERTIVA_MAVEN") or shutil.which("mvn")
    if not maven or not (os.environ.get("JAVA_HOME") or shutil.which("java")):
        reason = "requires a JDK, Maven and the PIT fixture resolved once (see this module's docstring)"
        if os.environ.get("ASSERTIVA_REQUIRE_JAVA"):
            pytest.fail(reason)
        pytest.skip(reason)


def _run(capsys, *args) -> dict:
    capsys.readouterr()
    cli.main([*args, "--output", "json"])
    return json.loads(capsys.readouterr().out)


@pytest.mark.integration
@pytest.mark.jvm
def test_pit_proves_the_protection_a_strengthened_junit_test_adds(tmp_path, capsys):
    _maven_ready()
    root = tmp_path / "project"
    shutil.copytree(PROJECT, root, ignore=shutil.ignore_patterns("target", "strengthened"))
    write(root / ".gitignore", "target/\n")
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fixture"]):
        subprocess.run([*git, *args], cwd=root, check=True, capture_output=True)
    before = tree_fingerprint(root)
    target = "src/main/java/dev/assertiva/pit/Pricing.java"

    audit = _run(capsys, "audit", str(root), "--execute", "--mutate", target)
    [run] = audit["states"]["current"]["mutation"]
    assert run["error"] is None, run["error"]
    assert run["tool"] == "PIT" and run["tool_version"] == "1.30.0" and run["matches_state"] is True and run["killers_complete"] is True
    assert run["counts"].get("SURVIVED", 0) > 0 and run["config"]["selected"] == "pit" and run["config"]["offline"] is True

    workspace = Path(_run(capsys, "improve", str(root))["candidate_workspace"])
    shutil.copy(PROJECT / "strengthened" / "PricingTest.java", workspace / "src/test/java/dev/assertiva/pit/PricingTest.java")
    report = _run(capsys, "improve", str(root), "--mutate", target)
    protection = report["candidate_qualification"]["protection"]
    gained = [e for e in protection["gained"] if e["kind"] == "mutant"]
    assert gained and protection["lost"] == [] and all(e["attribution"] == "TEST" for e in gained)
    assert any("PricingTest.theThresholdIsInclusive (src/test/java/dev/assertiva/pit/PricingTest.java)" in e["detected_by"]
               for e in gained)

    cli.main(["improve", str(root), "--discard"])
    assert tree_fingerprint(root) == before
