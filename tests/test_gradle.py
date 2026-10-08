"""Gradle: Kotlin/JVM, Java, Android local tests and Kotlin Multiplatform, run by a prepared Gradle, never the wrapper jar.

The real runs download a JDK and a Gradle distribution (sha256-verified, into ASSERTIVA_HOME/tools) and the builds'
dependencies, so they run when ASSERTIVA_RUN_GRADLE=1 (and ASSERTIVA_RUN_ANDROID=1 with an Android SDK); CI sets them."""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from assertiva.adapters import runner_adapters
from assertiva.adapters.gradle import GradleAdapter, _declaration, _tasks, modules
from assertiva.workspace import tree_fingerprint

FIXTURES = Path(__file__).parent / "fixtures"


def test_modules_plugins_frameworks_and_source_sets_are_read_statically():
    found = {m["path"]: m for m in modules(FIXTURES / "gradle-kotlin")}
    assert found["pricing"]["kind"] == "kotlin-jvm" and found["pricing"]["frameworks"] == ["JUnit 5", "kotlin.test"]
    assert found["legacy"]["kind"] == "java" and found["legacy"]["frameworks"] == ["JUnit 4"]
    assert found["pricing"]["coverage"] == ["jacoco"] and found["."]["kind"] == "unknown"  # `apply false` applies nothing


def test_android_local_and_instrumented_tests_are_kept_apart():
    [app] = [m for m in modules(FIXTURES / "android-notes") if m["path"] == "app"]
    assert app["kind"] == "android" and set(app["test_source_sets"]) == {"test", "androidTest"}
    tasks, matrix = _tasks(app)
    assert tasks == [":app:testDebugUnitTest"]
    assert matrix[":app connectedAndroidTest (instrumented)"].startswith("NOT_RUN: needs a device or emulator")


def test_multiplatform_targets_are_related_to_their_hosts():
    [module] = modules(FIXTURES / "kmp-totals")
    tasks, matrix = _tasks(module)
    assert module["kind"] == "kmp" and tasks == [":jvmTest"]  # a passing jvmTest proves nothing about iOS or JS
    assert matrix[": iosTest"] == "NOT_RUN: needs a macOS host with Xcode" and matrix[": jsTest"].startswith("NOT_RUN")


def test_junit_platform_names_keep_or_admit_their_declaration():
    assert _declaration("demo.A", "vip()") == ("demo.A#vip", None)
    assert _declaration("demo.A", "squares(int)[1]") == ("demo.A#squares", "1")
    assert _declaration("demo.A", "[2] 100, 100") == (None, "[2] 100, 100")  # display name only: the method is unknown


def test_without_a_gradle_distribution_the_run_is_blocked_and_the_wrapper_is_never_run(tmp_path, monkeypatch):
    shutil.copytree(FIXTURES / "gradle-kotlin", tmp_path / "p")
    (tmp_path / "p" / "gradlew").write_text("#!/bin/sh\necho ran > wrapper-ran\n", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None)
    run = GradleAdapter().run(tmp_path / "p")
    assert run.status.value == "BLOCKED" and "gradle-wrapper.jar is never executed" in run.limitations[0]
    assert not (tmp_path / "p" / "wrapper-ran").exists()


def test_a_ci_gradle_test_step_is_reproduced_through_the_adapter_only_for_test_tasks():
    from assertiva.adapters.ci_common import command_check
    from assertiva.verification import GateMode

    adapter = GradleAdapter()
    test = command_check("gha", "c1", "./gradlew :pricing:test", "ci.yml", GateMode.UNKNOWN, {})
    publish = command_check("gha", "c2", "./gradlew publish", "ci.yml", GateMode.UNKNOWN, {})
    assert adapter.reproduction_args(test) == [":pricing:test"]
    assert publish.kind.value == "DEPLOY" and adapter.reproduction_args(publish) is None


def _audit(root: Path, capsys) -> dict:
    from assertiva import cli

    code = cli.main(["audit", str(root), "--execute", "--provision", "--python", sys.executable, "--output", "json"])
    assert code == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("ASSERTIVA_RUN_GRADLE"), reason="downloads a JDK, Gradle and dependencies; set ASSERTIVA_RUN_GRADLE=1")
def test_kotlin_and_java_modules_run_with_per_module_results_and_coverage(tmp_path, capsys):
    root = tmp_path / "proj"
    shutil.copytree(FIXTURES / "gradle-kotlin", root)
    before = tree_fingerprint(root)
    report = _audit(root, capsys)
    assert tree_fingerprint(root) == before  # build/, .gradle/ and caches went to the copy and the tools cache
    [run] = report["states"]["current"]["runs"]
    assert run["adapter"] == "gradle" and run["status"] == "PASS"
    assert run["outcomes"] == {"PASSED": 7, "SKIPPED": 1} and set(run["matrix"]) == {":pricing test", ":legacy test"}
    assert run["declaration_identity"] == "UNKNOWN"  # parameterized cases are named by display only
    metrics = report["states"]["current"]["metrics"]
    assert metrics["line_coverage"]["value"] == 100 and "test_declarations" not in metrics


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("ASSERTIVA_RUN_GRADLE"), reason="downloads a JDK, Gradle and dependencies; set ASSERTIVA_RUN_GRADLE=1")
def test_a_failing_kotlin_test_fails_the_run_and_a_broken_test_source_is_a_collection_error(tmp_path, capsys):
    root = tmp_path / "proj"
    shutil.copytree(FIXTURES / "gradle-kotlin", root)
    source = root / "pricing" / "src" / "main" / "kotlin" / "demo" / "pricing" / "Discount.kt"
    source.write_text(source.read_text(encoding="utf-8").replace("total * 90", "total * 80"), encoding="utf-8")
    [run] = _audit(root, capsys)["states"]["current"]["runs"]
    assert run["status"] == "FAIL" and run["outcomes"]["FAILED"] == 1
    (root / "legacy" / "src" / "test" / "java" / "demo" / "legacy" / "StockTest.java").write_text("class Broken {", encoding="utf-8")
    [run] = _audit(root, capsys)["states"]["current"]["runs"]
    assert run["status"] == "FAIL" and run["collection_errors"]


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("ASSERTIVA_RUN_GRADLE"), reason="downloads a JDK, Gradle and dependencies; set ASSERTIVA_RUN_GRADLE=1")
def test_multiplatform_runs_jvm_tests_and_lists_the_other_targets(tmp_path, capsys):
    root = tmp_path / "proj"
    shutil.copytree(FIXTURES / "kmp-totals", root)
    [run] = _audit(root, capsys)["states"]["current"]["runs"]
    assert run["status"] == "PASS" and run["outcomes"] == {"PASSED": 4}  # 3 common + 1 JVM-only, on the JVM
    assert run["matrix"][": jvmTest"] == "EXECUTED" and run["matrix"][": iosTest"].startswith("NOT_RUN")


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("ASSERTIVA_RUN_GRADLE"), reason="downloads a JDK and Gradle; set ASSERTIVA_RUN_GRADLE=1")
def test_android_local_tests_run_with_an_sdk_and_instrumented_ones_never_without_a_device(tmp_path, capsys, monkeypatch):
    root = tmp_path / "proj"
    shutil.copytree(FIXTURES / "android-notes", root)
    if not os.environ.get("ASSERTIVA_RUN_ANDROID"):
        monkeypatch.delenv("ANDROID_HOME", raising=False)
        monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    [run] = _audit(root, capsys)["states"]["current"]["runs"]
    assert run["matrix"][":app connectedAndroidTest (instrumented)"].startswith("NOT_RUN")
    if os.environ.get("ASSERTIVA_RUN_ANDROID"):
        assert run["status"] == "PASS" and run["outcomes"] == {"PASSED": 2} and run["matrix"][":app testDebugUnitTest"] == "EXECUTED"
    else:
        assert run["status"] == "BLOCKED" and run["matrix"][":app testDebugUnitTest (local)"].startswith("BLOCKED: no Android SDK")
