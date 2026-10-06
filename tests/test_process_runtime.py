"""Runtime capability evidence is scoped to a run; traces never carry credentials."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from assertiva import process


def make_env(root: Path) -> tuple[Path, Path]:
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(root)], check=True)
    python = root / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    site = subprocess.run([str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
                          capture_output=True, text=True, check=True).stdout.strip()
    return python, Path(site)


@pytest.fixture
def env(tmp_path):
    return make_env(tmp_path / "env")


def probes(tmp_path, action):
    process.TRACE_PATH = tmp_path / "trace.jsonl"
    try:
        action()
    finally:
        process.TRACE_PATH = None
    lines = (tmp_path / "trace.jsonl").read_text(encoding="utf-8").splitlines() if (tmp_path / "trace.jsonl").exists() else []
    return [json.loads(line) for line in lines if json.loads(line)["event"] == "command_start"]


def test_same_run_reuses_a_probe(env, tmp_path):
    python, _ = env

    def run():
        with process.run_scope():
            assert process.module_available(python, "json")
            assert process.module_available(python, "json")

    assert len(probes(tmp_path, run)) == 1


def test_a_new_run_sees_a_module_installed_in_between(env):
    python, site = env
    with process.run_scope():
        assert not process.module_available(python, "probe_module_xyz")
        (site / "probe_module_xyz.py").write_text("X = 1\n")
        assert not process.module_available(python, "probe_module_xyz")  # same run: same evidence
    with process.run_scope():
        assert process.module_available(python, "probe_module_xyz")  # new run refreshes


def test_removed_module_is_not_remembered_across_runs(env):
    python, site = env
    (site / "gone_module_xyz.py").write_text("X = 1\n")
    with process.run_scope():
        assert process.module_available(python, "gone_module_xyz")
    (site / "gone_module_xyz.py").unlink()
    with process.run_scope():
        assert not process.module_available(python, "gone_module_xyz")


def test_interpreters_have_separate_evidence(tmp_path):
    first, first_site = make_env(tmp_path / "a")
    second, _ = make_env(tmp_path / "b")
    (first_site / "only_in_a.py").write_text("X = 1\n")
    with process.run_scope():
        assert process.module_available(first, "only_in_a")
        assert not process.module_available(second, "only_in_a")


def test_no_cache_outside_a_run(env):
    python, site = env
    assert not process.module_available(python, "late_module_xyz")
    (site / "late_module_xyz.py").write_text("X = 1\n")
    assert process.module_available(python, "late_module_xyz")


def test_nested_scopes_share_the_outer_run(env, tmp_path):
    python, _ = env

    def run():
        with process.run_scope():
            process.module_available(python, "json")
            with process.run_scope():
                process.module_available(python, "json")

    assert len(probes(tmp_path, run)) == 1


@pytest.mark.parametrize(
    ("argument", "secret"),
    [("--token=abc123secret", "abc123secret"), ("https://user:hunter2pass@example.com/repo.git", "hunter2pass"),
     ("PASSWORD=s3cr3tvalue", "s3cr3tvalue")],
)
def test_traces_redact_credentials_in_commands(tmp_path, argument, secret):
    events = probes(tmp_path, lambda: process.run_command([sys.executable, "-c", "pass", argument], tmp_path, timeout_s=30))
    text = json.dumps(events)
    assert secret not in text and "***" in text
