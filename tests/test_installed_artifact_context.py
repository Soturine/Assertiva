"""Self-tests that must hold in the context wheel qualification runs them in.

Ordinary test runs have a full Git checkout and an editable install, so a test can lean on ``.git``, on the source
package beside it or on the checkout's identity without anyone noticing. Artifact qualification runs the same tests from
a copy without ``.git`` and without the source package, against the installed wheel. This builds that context from
this repository with the adapter's own build and install steps and runs the tests that read repository files in it.
"""

import json
import re
import sys
from pathlib import Path

import pytest

from assertiva.adapters import python_package as package_adapter
from assertiva.adapters.python_package import PythonPackageAdapter
from assertiva.workspace import snapshot

ROOT = Path(__file__).resolve().parents[1]

# Test modules that read repository files, locate the package or report the runtime's identity.
# A module that does any of that belongs here.
CONTEXT_SENSITIVE_TESTS = ("tests/test_report_ui.py", "tests/test_semantic_eval.py")
FAST_ONLY = "not integration and not artifact and not browser and not jvm"

pytestmark = pytest.mark.artifact


@pytest.fixture(scope="module")
def installed_context(tmp_path_factory):
    """(venv python, copy): the repository's tests beside an installed wheel, with no .git and no source package."""
    if not (ROOT / "assertiva").is_dir() or not (ROOT / "pyproject.toml").is_file():
        pytest.skip("already running without the source package: there is nothing to build the wheel from")
    pytest.importorskip("build", reason="no local build tool: the wheel cannot be built without network access")
    pytest.importorskip("setuptools", reason="no local build backend: the wheel cannot be built without network access")
    tmp = tmp_path_factory.mktemp("installed-context")
    adapter = PythonPackageAdapter()
    outside = tmp / "outside"
    outside.mkdir()

    work = snapshot(ROOT, tmp / "src")  # what artifact qualification builds from: project files, never .git
    built = adapter._run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", tmp / "dist"], work)
    assert built.ok, built.summary()
    wheel = next((tmp / "dist").glob("*.whl"))
    sites = adapter._run([sys.executable, "-c", package_adapter._SITE_PROBE], outside)
    installed, _ = adapter._install(tmp / "venv", wheel, outside, json.loads(sites.stdout) if sites.ok else [])
    assert installed.ok, installed.summary()

    copy = snapshot(work, tmp / "tests-copy")
    for name in ("assertiva",):  # exactly what qualification removes before running the tests
        for base in (copy, copy / "src"):
            package_adapter.shutil.rmtree(base / name, ignore_errors=True)
    return package_adapter._venv_python(tmp / "venv"), copy


def test_the_context_really_is_gitless_sourceless_and_installed(installed_context):
    python, copy = installed_context
    assert not (copy / ".git").exists() and not (copy / "assertiva").exists()
    probe = PythonPackageAdapter()._run(
        [python, "-c", "import assertiva, json; from assertiva.identity import runtime_identity as r; print(json.dumps([assertiva.__file__, r()]))"], copy
    )
    assert probe.ok, probe.summary()
    imported, identity = json.loads(probe.stdout.strip().splitlines()[-1])
    assert Path(imported).resolve().is_relative_to(Path(python).resolve().parents[1])  # the wheel, not the checkout
    assert identity["install"] == "installed-package" and identity["revision"] is None and identity["dirty"] is None


def test_self_tests_that_read_the_repository_hold_without_git_source_or_editable_install(installed_context):
    python, copy = installed_context
    run = PythonPackageAdapter()._run(
        [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", "-m", FAST_ONLY, *CONTEXT_SENSITIVE_TESTS], copy
    )
    assert run.ok, run.summary() + "\n" + run.stdout[-2500:]
    assert re.search(r"\d+ passed", run.stdout) and "failed" not in run.stdout.splitlines()[-1] and "error" not in run.stdout.splitlines()[-1]
    # what needs a Git checkout is skipped with its reason, never silently dropped or failed
    assert "needs a Git checkout" in run.stdout
