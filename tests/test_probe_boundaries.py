"""Interpreter probes run Assertiva's own code, never the project's.

`python -c` puts the current directory first on sys.path, so a probe started inside a project imports the project's
modules (a `json.py`, a `platform.py` at its root) outside any disposable copy; and a probe that interpolates a value
from the project into its code runs that value. Both were found by the 0.7.3 security re-audit.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

from assertiva import process
from assertiva.adapters import provisioning
from assertiva.adapters.python_package import PythonPackageAdapter
from conftest import write

PLANT = "from pathlib import Path\nPath({marker!r}).write_text('ran', encoding='utf-8')\n"


def _plant(project: Path, module: str, marker: Path) -> None:
    write(project / f"{module}.py", PLANT.format(marker=str(marker)))


@pytest.mark.parametrize("module", ["json", "platform"])
def test_interpreter_probe_started_in_a_project_does_not_import_its_modules(tmp_path, monkeypatch, module):
    project, marker = tmp_path / "project", tmp_path / "marker"
    _plant(project, module, marker)
    monkeypatch.chdir(project)
    probe = provisioning._probe(sys.executable)
    assert probe and probe["version"]
    assert not marker.exists()


def test_installed_distribution_probe_does_not_import_project_modules(tmp_path, monkeypatch):
    project, marker = tmp_path / "project", tmp_path / "marker"
    _plant(project, "json", marker)
    monkeypatch.chdir(project)
    assert provisioning._missing(sys.executable, ["pytest", "no-such-distribution-assertiva"]) == ["no-such-distribution-assertiva"]
    assert not marker.exists()


def test_module_probe_imports_installed_modules_only(tmp_path, monkeypatch):
    project, marker = tmp_path / "project", tmp_path / "marker"
    _plant(project, "inproject_backend", marker)
    monkeypatch.chdir(project)
    assert process.module_available(sys.executable, "json")
    assert not process.module_available(sys.executable, "inproject_backend")  # in the project, not installed
    assert not marker.exists()


def test_a_project_value_is_never_run_as_probe_code(tmp_path):
    marker = tmp_path / "marker"
    code = f"open({str(marker)!r},'w')"
    payload = "os;exec(bytes((" + ",".join(str(b) for b in code.encode()) + ")))"  # no ':' or '.': survives the backend split
    write(tmp_path / "project" / "pyproject.toml", f'[build-system]\nrequires = []\nbuild-backend = "{payload}"\n')
    adapter = PythonPackageAdapter(python=sys.executable)
    assert adapter._backend_is_local(tmp_path / "project", tmp_path / "project") is False
    assert not marker.exists()


@pytest.mark.parametrize("name", ["os;print(1)", "a b", "", "os\nprint(1)", "__import__('os')", "1abc", "a..b"])
def test_module_names_that_are_not_names_are_refused_without_running(name):
    assert process.module_available(sys.executable, name) is False


def test_output_digest_and_tail_are_unchanged_when_read_in_bounded_chunks(tmp_path):
    # multibyte characters across the cut and output well beyond the tail
    script = write(tmp_path / "emit.py", "import sys\nsys.stdout.buffer.write(('é€😀' * 50000 + 'END').encode())\n"
                                         "sys.stderr.buffer.write(b'warn' * 3000)\n")
    result = process.run_command([sys.executable, str(script)], tmp_path, timeout_s=60)
    full_out = ("é€😀" * 50000 + "END").encode()
    full_err = b"warn" * 3000
    assert result.ok
    assert result.output_sha256 == hashlib.sha256(full_out + b"|" + full_err).hexdigest()
    assert result.stdout == full_out.decode()[-process.OUTPUT_LIMIT:]
    assert result.stderr == full_err.decode()[-process.OUTPUT_LIMIT:]


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_the_generated_database_password_file_is_readable_only_by_its_owner(tmp_path, monkeypatch):
    from assertiva.adapters import services
    from assertiva.environment import Prepared, ProvisioningError, Step

    modes = []

    def fake_run(command, cwd, **kwargs):
        pwfile = Path(command[command.index("--pwfile") + 1])
        modes.append(pwfile.stat().st_mode & 0o777)
        return process.CommandResult(command=command, cwd=str(cwd), started_at="", duration_s=0, timeout_s=1, returncode=1)

    monkeypatch.setattr(services, "run_command", fake_run)
    monkeypatch.setattr(services, "_portable_binaries", lambda: tmp_path / "pg")
    prepared = Prepared(workspace=tmp_path / "ws")
    (tmp_path / "ws" / "env").mkdir(parents=True)
    with pytest.raises(ProvisioningError):
        services.prepare_service(Step("postgresql", "service", "", "", detail='{"installed": false}'), prepared)
    assert modes == [0o600]


def test_the_plan_names_the_package_sources_the_project_declares(tmp_path):
    write(tmp_path / "requirements.txt", "--index-url https://user:s3cret@mirror.example.invalid/simple\n"
                                         "--extra-index-url=https://extra.example.invalid/simple\nno-such-dist-assertiva==1.0\n")
    write(tmp_path / "tests" / "test_a.py", "def test_a():\n    assert True\n")
    from assertiva.environment import Prepared

    [step] = provisioning._python_plan(tmp_path, sys.executable, [], Prepared())
    downloads = " ".join(step.downloads)
    assert "PyPI" not in downloads  # an index URL replaces PyPI
    assert "mirror.example.invalid" in downloads and "extra.example.invalid" in downloads
    assert "s3cret" not in downloads + " ".join(step.divergences)
    assert any("beyond PyPI" in d for d in step.divergences)


def test_a_plan_without_declared_sources_still_names_pypi(tmp_path):
    write(tmp_path / "requirements.txt", "no-such-dist-assertiva==1.0\n")
    write(tmp_path / "tests" / "test_a.py", "def test_a():\n    assert True\n")
    from assertiva.environment import Prepared

    [step] = provisioning._python_plan(tmp_path, sys.executable, [], Prepared())
    assert step.downloads == ["PyPI (pip)"] and not any("beyond PyPI" in d for d in step.divergences)
