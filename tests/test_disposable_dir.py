"""A failed cleanup of a temporary workspace is declared, never raised (Prescripta dogfood, 2026-11).

On Windows, ``audit --execute`` on a Python package ended with ``PermissionError: [WinError 5]`` while
``TemporaryDirectory`` removed a throwaway venv's ``python.exe`` that was still locked, and no report was
written. The evidence gathered before the cleanup must survive, and what stayed behind must be stated.
"""

import os
import stat
import sys
import tempfile
from pathlib import Path

import pytest

from assertiva.workspace import disposable_dir, remove_tree

LEFT_BEHIND = "a temporary workspace could not be fully removed"


def test_clean_exit_removes_the_directory_and_declares_nothing():
    limitations: list[str] = []
    with disposable_dir("assertiva-test-", limitations) as path:
        (path / "nested").mkdir()
        (path / "nested" / "file.txt").write_text("x", encoding="utf-8")
    assert not path.exists()
    assert limitations == []


def test_an_error_inside_still_propagates_and_still_cleans_up():
    limitations: list[str] = []
    with pytest.raises(ValueError, match="from the body"):
        with disposable_dir("assertiva-test-", limitations) as path:
            raise ValueError("from the body")
    assert not path.exists()
    assert limitations == []


@pytest.mark.skipif(os.name != "nt", reason="an open handle blocks deletion only on Windows")
def test_a_file_still_open_on_windows_is_declared_instead_of_crashing():
    # Negative control: the standard library raises in exactly this situation (the original crash).
    with pytest.raises(PermissionError):
        with tempfile.TemporaryDirectory(prefix="assertiva-test-") as raw:
            held = open(Path(raw) / "python.exe", "wb")  # noqa: SIM115 - the handle must outlive the block
    held.close()

    limitations: list[str] = []
    with disposable_dir("assertiva-test-", limitations) as path:
        handle = open(path / "python.exe", "wb")  # noqa: SIM115 - still open when cleanup runs
    try:
        assert path.exists()
        assert [item for item in limitations if LEFT_BEHIND in item and str(path) in item] == limitations
        assert len(limitations) == 1
    finally:
        handle.close()
        remove_tree(path)


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="POSIX permissions, non-root")
def test_an_undeletable_entry_on_posix_is_declared_instead_of_crashing():
    limitations: list[str] = []
    with disposable_dir("assertiva-test-", limitations) as path:
        locked = path / "locked"
        locked.mkdir()
        (locked / "python").write_text("x", encoding="utf-8")
        locked.chmod(stat.S_IRUSR | stat.S_IXUSR)  # no write: its entries cannot be unlinked
    try:
        assert path.exists()
        assert len(limitations) == 1 and LEFT_BEHIND in limitations[0]
    finally:
        locked.chmod(stat.S_IRWXU)
        remove_tree(path)


def test_the_artifact_qualification_uses_the_declaring_cleanup():
    """The site that crashed must not go back to a raising TemporaryDirectory."""
    source = Path(sys.modules["assertiva.workspace"].__file__).parent / "adapters" / "python_package.py"
    text = source.read_text(encoding="utf-8")
    assert 'disposable_dir("assertiva-artifact-", evidence.limitations)' in text
    assert 'TemporaryDirectory(prefix="assertiva-artifact-")' not in text
