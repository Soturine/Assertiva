"""Disposable services: detected from the project's files, verified before tests connect, gone when the run ends.

The real case (tests/fixtures/django-postgres: Django on PostgreSQL features) provisions an interpreter environment
from PyPI and portable PostgreSQL binaries from Maven Central, so it needs network the first time (cached in
ASSERTIVA_HOME/tools afterwards). It runs when ASSERTIVA_RUN_SERVICES=1 (CI sets it)."""

import json
import os
import shutil
import socket
import sys
from pathlib import Path

import pytest

from assertiva.adapters.services import _needs_postgres, _verify_instance, service_plan
from assertiva.environment import Prepared, ProvisioningError
from assertiva.workspace import tree_fingerprint
from conftest import write

FIXTURE = Path(__file__).parent / "fixtures" / "django-postgres"


@pytest.mark.parametrize("files", [
    {"docker-compose.yml": "services:\n  db:\n    image: postgres:16\n"},
    {"site/settings.py": "DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql'}}\n"},
    {"requirements.txt": "psycopg[binary]==3.2.3\n"},
    {".github/workflows/ci.yml": "jobs:\n  t:\n    services:\n      pg:\n        image: postgres:17\n"},
])
def test_postgresql_needs_are_found_in_the_projects_own_files(tmp_path, files):
    for name, text in files.items():
        write(tmp_path / name, text)
    assert _needs_postgres(tmp_path, Prepared())
    [step] = service_plan(tmp_path, Prepared())
    assert step.step_id == "postgresql" and step.status == "PLANNED"


def test_a_project_without_a_database_plans_no_service(tmp_path):
    write(tmp_path / "app.py", "X = 1\n")
    write(tmp_path / "requirements.txt", "requests\n")
    assert service_plan(tmp_path, Prepared()) == []


def test_the_answering_server_must_be_this_runs_instance(tmp_path):
    data = tmp_path / "pg"
    data.mkdir()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        write(data / "postmaster.pid", f"123\n{data}\n0\n{port}\n")
        _verify_instance(data, port)  # ours, and it answers
        write(data / "postmaster.pid", f"123\n{tmp_path / 'other'}\n0\n{port}\n")
        with pytest.raises(ProvisioningError, match="does not name"):
            _verify_instance(data, port)  # a server for another data directory
        write(data / "postmaster.pid", f"123\n{data}\n0\n{port + 1}\n")
        with pytest.raises(ProvisioningError):
            _verify_instance(data, port)  # another port


@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("ASSERTIVA_RUN_SERVICES"), reason="needs network or cached tools; set ASSERTIVA_RUN_SERVICES=1")
def test_django_runs_on_a_disposable_postgresql_never_on_the_callers_database(tmp_path, capsys, monkeypatch):
    from assertiva import cli

    root = tmp_path / "proj"
    shutil.copytree(FIXTURE, root)
    monkeypatch.setenv("DATABASE_URL", "postgres://ops@staging.invalid:5432/app")  # the caller's shell points at a shared database
    before = tree_fingerprint(root)
    code = cli.main(["audit", str(root), "--execute", "--provision", "--python", sys.executable, "--output", "json"])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and tree_fingerprint(root) == before
    steps = {s["step_id"]: s for s in report["environment"]["steps"]}
    assert steps["python-env"]["status"] in ("DONE", "REUSED") and steps["postgresql"]["status"] == "DONE", steps
    [service] = report["environment"]["services"]
    assert service["host"] == "127.0.0.1" and "17.9" in service["version"]
    [run] = report["states"]["current"]["runs"]
    assert run["adapter"] == "django" and run["status"] == "PASS" and run["outcomes"] == {"PASSED": 4}  # vendor == postgresql
    assert "DATABASE_URL" in " ".join(report["claim_boundary"]["limitations"])  # the caller's value was withheld
    assert not any(f["code"] == "NO_TESTS_DISCOVERED" for f in report["findings"])
    assert not Path(service["data_directory"]).exists()  # the cluster went with the run workspace
