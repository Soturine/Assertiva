"""DG-0101-06 (Derivanta M3 OBS-M3-02): an entry the project inventory cannot read — a Windows path past MAX_PATH, a
refused permission — is reported, never silently left out of the inventory, the copies and every result."""

import os
import sys
from pathlib import Path

import pytest

from assertiva import workspace
from assertiva.audit import _boundary_findings

from conftest import write


def test_a_directory_that_cannot_be_listed_is_reported_not_dropped(tmp_path, monkeypatch):
    write(tmp_path / "tests" / "test_a.py", "def test_a():\n    assert 1\n")
    write(tmp_path / "tests" / "locked" / "test_b.py", "def test_b():\n    assert 1\n")
    real = os.scandir

    def scandir(path):
        if Path(path).name == "locked":
            raise PermissionError(13, "refused", str(path))
        return real(path)

    monkeypatch.setattr(workspace.os, "scandir", scandir)
    report = workspace.boundary_report(tmp_path)
    assert workspace.project_files(tmp_path) == ["tests/test_a.py"]  # the inventory still cannot see it...
    assert report["unreadable"] == ["tests/locked"]  # ...but now says so (0.10.0: nothing)
    [finding] = [f for f in _boundary_findings(report) if f.code == "PROJECT_ENTRIES_UNREADABLE"]
    assert finding.severity == "high" and finding.evidence["count"] == 1


def test_a_readable_project_reports_nothing(tmp_path):
    write(tmp_path / "tests" / "test_a.py", "def test_a():\n    assert 1\n")
    assert workspace.boundary_report(tmp_path)["unreadable"] == []


@pytest.mark.skipif(sys.platform != "win32", reason="MAX_PATH is a Windows limit")
def test_a_path_past_max_path_is_reported_on_windows(tmp_path):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            enabled = winreg.QueryValueEx(key, "LongPathsEnabled")[0]
    except OSError:
        enabled = 0
    if enabled:
        pytest.skip("long paths are enabled on this machine: nothing is unreadable")
    write(tmp_path / "tests" / "test_a.py", "def test_a():\n    assert 1\n")
    prefix, current = "\\\\?\\", str(tmp_path / "tests")
    for part in ("d" * 90, "e" * 90, "f" * 90):
        current += "\\" + part
        os.mkdir(prefix + current)
    with open(prefix + current + "\\test_deep.py", "w") as handle:
        handle.write("def test_b():\n    assert 1\n")
    assert len(current) > 260
    assert workspace.boundary_report(tmp_path)["unreadable"]  # 0.10.0: the deep test vanished without a word
