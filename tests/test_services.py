"""Disposable services: detected from the project's files, verified before tests connect, gone when the run ends.

The real case (tests/fixtures/django-postgres: Django on PostgreSQL features) provisions an interpreter environment
from PyPI and portable PostgreSQL binaries from Maven Central, so it needs network the first time (cached in
ASSERTIVA_HOME/tools afterwards). It runs when ASSERTIVA_RUN_SERVICES=1 (CI sets it)."""

import base64
import hashlib
import hmac
import json
import os
import shutil
import socket
import struct
import sys
import threading
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


def _fake_postgres(password: str, data_directory: str, mode: str = "scram"):
    """A minimal PostgreSQL wire-protocol server for one connection: SCRAM-SHA-256 with the given password (the
    server side of the exchange), then one row with the data directory and port it claims."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]

    def message(kind, payload):
        return kind + struct.pack("!i", len(payload) + 4) + payload

    def read(conn, typed=True):
        head = conn.recv(5 if typed else 4)
        size = struct.unpack("!i", head[1:] if typed else head)[0]
        body = b""
        while len(body) < size - 4:
            body += conn.recv(size - 4 - len(body))
        return body

    def serve():
        conn, _ = listener.accept()
        with conn:
            read(conn, typed=False)  # startup
            if mode == "not-postgres":
                conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
                return
            if mode == "trust":
                conn.sendall(message(b"R", struct.pack("!i", 0)) + message(b"Z", b"I"))
            else:
                conn.sendall(message(b"R", struct.pack("!i", 10) + b"SCRAM-SHA-256\0\0"))
                first = read(conn)
                client_first_bare = first.split(b"\0", 1)[1][4:].decode()[3:]
                nonce = client_first_bare.split("r=", 1)[1] + "srv"
                salt = b"0123456789abcdef"
                server_first = f"r={nonce},s={base64.b64encode(salt).decode()},i=4096"
                conn.sendall(message(b"R", struct.pack("!i", 11) + server_first.encode()))
                final = read(conn).decode()
                without_proof = final.rsplit(",p=", 1)[0]
                auth = f"{client_first_bare},{server_first},{without_proof}".encode()
                salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 4096)
                signature = hmac.new(hmac.new(salted, b"Server Key", hashlib.sha256).digest(), auth, hashlib.sha256).digest()
                conn.sendall(message(b"R", struct.pack("!i", 12) + b"v=" + base64.b64encode(signature))
                             + message(b"R", struct.pack("!i", 0)) + message(b"Z", b"I"))
            try:
                read(conn)  # the query
            except (struct.error, OSError):
                return
            row = b"".join(struct.pack("!i", len(v)) + v for v in (data_directory.encode(), str(port).encode()))
            conn.sendall(message(b"D", struct.pack("!h", 2) + row) + message(b"Z", b"I"))

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return listener, port, thread


@pytest.mark.parametrize("mode, password, claims_ours, refusal", [
    ("scram", "run-secret", True, None),
    ("scram", "someone-else", True, "could not prove"),  # another cluster cannot sign with this run's password
    ("trust", "run-secret", True, "without authenticating"),  # a server that lets anyone in is not ours
    ("scram", "run-secret", False, "another data directory"),
    ("not-postgres", "run-secret", True, "PostgreSQL protocol|closed the connection"),
])
def test_the_answering_server_must_prove_it_is_this_runs_instance(tmp_path, mode, password, claims_ours, refusal):
    data = tmp_path / "pg"
    data.mkdir()
    listener, port, thread = _fake_postgres(password, str(data if claims_ours else tmp_path / "other"), mode)
    with listener:
        write(data / "postmaster.pid", f"123\n{data}\n0\n{port}\n")
        if refusal is None:
            assert _verify_instance(data, port, "assertiva", "run-secret") == {"data_directory": str(data), "port": port}
        else:
            with pytest.raises(ProvisioningError, match=refusal):
                _verify_instance(data, port, "assertiva", "run-secret")
    thread.join(5)


def test_a_pid_file_for_another_directory_or_port_is_refused_before_connecting(tmp_path):
    data = tmp_path / "pg"
    data.mkdir()
    write(data / "postmaster.pid", f"123\n{tmp_path / 'other'}\n0\n5432\n")
    with pytest.raises(ProvisioningError, match="does not name"):
        _verify_instance(data, 5432, "assertiva", "x")
    write(data / "postmaster.pid", f"123\n{data}\n0\n5433\n")
    with pytest.raises(ProvisioningError, match="does not name"):
        _verify_instance(data, 5432, "assertiva", "x")


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
    assert steps["python-env"]["status"] in ("DONE", "REUSED") and steps["postgresql"]["status"] == "DONE", "\n".join(
        f"{s['step_id']}: {s['status']}: {s['detail']}" for s in steps.values())  # the full cause in a CI log
    [service] = report["environment"]["services"]
    assert service["host"] == "127.0.0.1" and "17.9" in service["version"]
    [run] = report["states"]["current"]["runs"]
    assert run["adapter"] == "django" and run["status"] == "PASS" and run["outcomes"] == {"PASSED": 4}  # vendor == postgresql
    assert "DATABASE_URL" in " ".join(report["claim_boundary"]["limitations"])  # the caller's value was withheld
    assert not any(f["code"] == "NO_TESTS_DISCOVERED" for f in report["findings"])
    assert not Path(service["data_directory"]).exists()  # the cluster went with the run workspace
