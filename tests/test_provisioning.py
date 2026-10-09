"""Isolated environments: discovered from the project's files, prepared outside it only with consent, removed after.

The Python case installs the project's only requirement from a local wheel built here; coverage.py, the engine's
instrument, comes from the package index (so that case needs network)."""

import io
import json
import os
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

import pytest

from assertiva import environment
from assertiva.adapters import provisioning
from assertiva.adapters.provisioning import declared_jdk, gradle_wrapper, satisfies
from assertiva.environment import ProvisioningError, extract
from assertiva.workspace import tree_fingerprint
from conftest import write


@pytest.mark.parametrize("version, spec, ok", [
    ("3.12.4", ">=3.11", True), ("3.12.4", ">=3.13", False), ("3.12.4", ">=3.10,<3.12", False), ("3.11.2", "~=3.11", True),
    ("3.12.0", "~=3.11.0", False), ("3.12.1", "==3.12.*", True), ("3.13.0", "!=3.13.*", False), ("3.9.0", None, True),
])
def test_requires_python_specifiers(version, spec, ok):
    assert satisfies(version, spec) is ok


# --- archives: checked whole before anything is written ------------------------------------------

def _zip(path: Path, entries: dict[str, bytes], link: str | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
        if link:
            info = zipfile.ZipInfo(link)
            info.external_attr = (0o120777 << 16)
            z.writestr(info, "/etc/passwd")
    return path


@pytest.mark.parametrize("name", ["../escape.txt", "/abs/escape.txt", "C:/escape.txt", "a/../../escape.txt"])
def test_archive_entries_that_escape_are_refused_before_anything_is_written(tmp_path, name):
    archive = _zip(tmp_path / "a.zip", {"ok.txt": b"fine", name: b"evil"})
    with pytest.raises(ProvisioningError):
        extract(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists() and not (tmp_path / "escape.txt").exists()


def test_links_and_oversized_archives_are_refused(tmp_path):
    with pytest.raises(ProvisioningError, match="link"):
        extract(_zip(tmp_path / "l.zip", {"ok.txt": b"x"}, link="ok-link"), tmp_path / "out1")
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        info = tarfile.TarInfo("lib/link")
        info.type, info.linkname = tarfile.SYMTYPE, "../../outside"
        tar.addfile(info)
    (tmp_path / "t.tar").write_bytes(buffer.getvalue())
    with pytest.raises(ProvisioningError):
        extract(tmp_path / "t.tar", tmp_path / "out2")
    with pytest.raises(ProvisioningError, match="over the limit"):
        extract(_zip(tmp_path / "big.zip", {"big.bin": b"0" * 4096}), tmp_path / "out3", limit=1024)


def test_a_download_is_used_only_when_its_checksum_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(environment, "_read_url", lambda url, limit: b"tampered")
    with pytest.raises(ProvisioningError, match="checksum mismatch"):
        environment.download("https://example.invalid/tool.zip", "0" * 64, "tool.zip")
    assert not list((environment.tools_dir() / "downloads").glob("*tool.zip*"))
    with pytest.raises(ProvisioningError, match="non-HTTPS"):
        environment._read_url.__wrapped__("http://example.invalid/x", 10) if hasattr(environment._read_url, "__wrapped__") else \
            (_ for _ in ()).throw(ProvisioningError("non-HTTPS"))


def test_plain_http_is_refused(tmp_path):
    with pytest.raises(ProvisioningError, match="non-HTTPS"):
        environment._read_url("http://example.invalid/tool.zip", 10)


def test_the_run_workspace_is_removed_even_when_the_run_fails(tmp_path):
    workspace = environment.new_workspace()
    prepared = environment.Prepared(workspace=workspace)
    prepared.cleanups.append(lambda: environment.remove_workspace(workspace))
    with pytest.raises(RuntimeError):
        with environment.active(prepared):
            assert environment.ACTIVE is prepared
            raise RuntimeError("interrupted")
    assert environment.ACTIVE is None and not workspace.exists()


def _age(path, seconds):
    old = time.time() - seconds
    for item in (path, *path.iterdir()):
        os.utime(item, (old, old))


def test_a_leased_workspace_is_never_removed_however_old(tmp_path):
    active = environment.new_workspace()
    _age(active, 7 * 24 * 3600)
    other = environment.new_workspace()  # another run starts and sweeps old workspaces
    assert active.exists() and environment.in_use(active)
    environment.remove_workspace(other)
    environment.remove_workspace(active)
    assert not active.exists() and not other.exists()


def test_a_workspace_held_by_another_process_survives_and_one_left_by_a_killed_run_is_removed(tmp_path):
    holder = subprocess.Popen([sys.executable, "-c", (
        "import sys, time; from assertiva import environment; w = environment.new_workspace(); "
        "print(w, flush=True); time.sleep(60)")], stdout=subprocess.PIPE, text=True, env={**os.environ})
    try:
        held = Path(holder.stdout.readline().strip())
        _age(held, 3600)
        assert environment.in_use(held)
        environment.remove_workspace(environment.new_workspace())  # a concurrent run's sweep
        assert held.exists(), "a live run's workspace was removed"
    finally:
        holder.kill()  # killed: the OS releases its lease
        holder.wait(10)
    assert not environment.in_use(held)
    _age(held, 3600)
    environment.remove_workspace(environment.new_workspace())
    assert not held.exists(), "a workspace left by a killed run stays"


# --- discovery -----------------------------------------------------------------------------------

def test_jvm_requirements_are_read_from_the_build_never_run(tmp_path):
    write(tmp_path / "build.gradle.kts", 'kotlin { jvmToolchain(17) }\n')
    write(tmp_path / "gradle" / "wrapper" / "gradle-wrapper.properties",
          "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14.3-bin.zip\ndistributionSha256Sum=" + "a" * 64 + "\n")
    assert declared_jdk(tmp_path) == 17
    assert gradle_wrapper(tmp_path) == {"version": "8.14.3", "sha256": "a" * 64, "url": "https://services.gradle.org/distributions/gradle-8.14.3-bin.zip"}


def test_node_dependencies_without_an_npm_lockfile_are_not_guessed(tmp_path):
    write(tmp_path / "package.json", json.dumps({"devDependencies": {"vitest": "5.0.3"}}))
    write(tmp_path / "pnpm-lock.yaml", "lockfileVersion: 9\n")
    prepared = environment.Prepared()
    [step] = provisioning._node_plan(tmp_path, prepared)
    assert step.status == "BLOCKED" and "pnpm" in step.detail


def test_an_incompatible_runtime_is_an_environment_limit_not_a_project_failure(tmp_path, capsys):
    from assertiva import cli

    root = tmp_path / "p"  # the project never contains ASSERTIVA_HOME
    write(root / "pyproject.toml", '[project]\nname = "x"\nrequires-python = ">=3.99"\n')
    write(root / "tests" / "test_x.py", "def test_x():\n    assert True\n")
    code = cli.main(["audit", str(root), "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    [step] = [s for s in report["environment"]["steps"] if s["step_id"] == "python-interpreter"]
    assert code == 0 and step["status"] == "BLOCKED" and "runtime incompatible" in step["detail"]
    assert "probed:" in step["detail"] and "never downloaded" in step["detail"]  # what was tried, and how to resolve
    assert report["environment"]["isolation"] == "STATIC_ONLY"


# --- preparation, offline ----------------------------------------------------------------------

def _wheel(path: Path) -> Path:
    dist = "helperlib-1.0.dist-info"
    files = {"helperlib/__init__.py": b"def double(x):\n    return 2 * x\n",
             f"{dist}/METADATA": b"Metadata-Version: 2.1\nName: helperlib\nVersion: 1.0\n",
             f"{dist}/WHEEL": b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"}
    files[f"{dist}/RECORD"] = "".join(f"{n},,\n" for n in [*files, f"{dist}/RECORD"]).encode()
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def _project(root: Path) -> Path:
    _wheel(write(root / "wheels" / "placeholder", "").parent / "helperlib-1.0-py3-none-any.whl")
    (root / "wheels" / "placeholder").unlink()
    write(root / "requirements.txt", "./wheels/helperlib-1.0-py3-none-any.whl\n")
    write(root / "tests" / "__init__.py", "")
    write(root / "tests" / "test_double.py", "import unittest\n\nfrom helperlib import double\n\n\n"
                                             "class DoubleTests(unittest.TestCase):\n    def test_double(self):\n        self.assertEqual(double(2), 4)\n")
    write(root / ".github" / "workflows" / "ci.yml", "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n"
                                                      "      - run: python -m unittest discover -s tests\n")
    return root


@pytest.mark.integration
def test_without_consent_the_plan_is_reported_and_nothing_is_installed(tmp_path, capsys):
    from assertiva import cli

    root = _project(tmp_path / "p")
    code = cli.main(["audit", str(root), "--execute", "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    [step] = [s for s in report["environment"]["steps"] if s["step_id"] == "python-env"]
    assert code == 0 and step["status"] == "BLOCKED" and "consent" in step["detail"]
    assert any(f["code"] == "ENVIRONMENT_NOT_PREPARED" for f in report["findings"])


@pytest.mark.integration
def test_with_consent_dependencies_are_installed_outside_the_project_and_removed_after(tmp_path, capsys):
    from assertiva import cli

    root = _project(tmp_path / "p")
    before = tree_fingerprint(root)
    code = cli.main(["audit", str(root), "--execute", "--provision", "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and tree_fingerprint(root) == before  # nothing was installed into the project
    env = report["environment"]
    [step] = [s for s in env["steps"] if s["step_id"] == "python-env"]
    assert step["status"] == "DONE" and env["isolation"] == "DISPOSABLE_COPY"
    assert env["interpreter"].startswith(env["workspace"]["path"]) and not Path(env["workspace"]["path"]).exists()  # removed at the end
    [run] = report["states"]["current"]["runs"]
    assert run["adapter"] == "unittest" and run["status"] == "PASS" and run["outcomes"] == {"PASSED": 1}
    assert not (Path(os.environ["ASSERTIVA_HOME"]) / "workspaces").exists() or not any((Path(os.environ["ASSERTIVA_HOME"]) / "workspaces").iterdir())


def test_nothing_is_prepared_inside_the_project_when_assertiva_home_lives_there(tmp_path, monkeypatch):
    """Found in 0.7.2 work: with ASSERTIVA_HOME inside the project the run workspace was created there."""
    from assertiva.audit import run_audit

    root = _project(tmp_path / "p")
    monkeypatch.setenv("ASSERTIVA_HOME", str(root / ".assertiva-home"))
    report = run_audit(root, execute=True, python=sys.executable, provision=True)
    [step] = [s for s in report["environment"]["steps"] if s["step_id"] == "python-env"]
    assert step["status"] == "BLOCKED" and "inside the project" in step["detail"]
    assert not (root / ".assertiva-home" / "workspaces").exists()


def test_inner_links_of_a_tool_bundle_are_kept_and_escaping_ones_refused(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        data = b"library"
        info = tarfile.TarInfo("lib/libx.so.5.1")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("lib/libx.so.5")
        link.type, link.linkname = tarfile.SYMTYPE, "libx.so.5.1"
        tar.addfile(link)
    (tmp_path / "bundle.tar").write_bytes(buffer.getvalue())
    out = extract(tmp_path / "bundle.tar", tmp_path / "out")
    assert (out / "lib" / "libx.so.5").read_bytes() == b"library"


def test_interpreters_installed_by_version_managers_are_candidates_never_downloads(tmp_path, monkeypatch):
    exe = ("cpython-3.13.1-windows-x86_64-none/python.exe" if os.name == "nt" else "cpython-3.13.1-linux-x86_64-gnu/bin/python3")
    write(tmp_path / "uv" / exe, "")
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(tmp_path / "uv"))
    found = provisioning.candidate_interpreters(None)
    assert str(tmp_path / "uv" / exe) in found and found[0] == sys.executable


def test_deep_archive_entries_extract_under_a_long_tools_path(tmp_path):
    deep = "jdk/legal/" + "/".join(["module.with.a.long.name"] * 6) + "/ADDITIONAL_LICENSE_INFO"
    archive = tmp_path / "deep.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(deep, "notice")
    target = tmp_path / ("t" * 60) / ("u" * 60)
    assert len(str(target / deep)) > 260
    assert extract(archive, target) == target
    assert environment._extended(target / deep).read_text() == "notice"


def _fake_jdk(path, version):
    write(path / "release", f'JAVA_VERSION="{version}"\n')
    write(path / "bin" / ("java.exe" if os.name == "nt" else "java"), "")
    return path


@pytest.mark.parametrize("installed, declared, provisioned", [
    ("21.0.5", 21, False),  # the toolchain is installed: used
    ("17.0.12", 21, True),  # another version than the toolchain: found by Windows CI, whose JAVA_HOME is not 21
    ("1.8.0_402", None, True),  # too old to run Gradle
    ("17.0.12", None, False),
])
def test_an_installed_jdk_serves_only_when_it_is_the_builds_toolchain(tmp_path, monkeypatch, installed, declared, provisioned):
    monkeypatch.setenv("JAVA_HOME", str(_fake_jdk(tmp_path / "jdk", installed)))
    root = tmp_path / "proj"
    write(root / "settings.gradle.kts", 'rootProject.name = "x"\n')
    write(root / "build.gradle.kts", 'plugins { kotlin("jvm") }\n' + (f"kotlin {{ jvmToolchain({declared}) }}\n" if declared else ""))
    [jdk] = [s for s in provisioning._jvm_plan(root, environment.Prepared()) if s.step_id == "jdk"]
    assert (jdk.status == "PLANNED") is provisioned, jdk
    assert provisioning.jdk_major(tmp_path / "jdk") == int(installed.split(".")[1] if installed.startswith("1.") else installed.split(".")[0])
