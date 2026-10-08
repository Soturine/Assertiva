"""Disposable services for tests (PostgreSQL first): detected from the project's configuration, prepared only on
this machine, verified before tests connect, removed at the end of the run.

Detection reads Compose files, CI service declarations, Django settings and drivers in the dependencies. The
instance is a new cluster in the run workspace (initdb), on a free local port, with a generated password, owned by
this run; tests receive its URL (``DATABASE_URL`` and libpq's ``PG*``), which the process layer lets through
only because it points at localhost. Binaries: an installed PostgreSQL (``initdb``/``pg_ctl`` on PATH), else the
portable build published to Maven Central (``io.zonky.test.postgres:embedded-postgres-binaries-*``, Apache-2.0
packaging of PostgreSQL) verified against Central's sha256. Docker is not required. A service that cannot be
prepared leaves the tests that need it BLOCKED, never failed.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
import shutil
import socket
from pathlib import Path

from assertiva.environment import Prepared, ProvisioningError, Step, download, extract, published_sha256, tools_dir
from assertiva.process import run_command

POSTGRES_VERSION = "17.9.0"
_CENTRAL = "https://repo1.maven.org/maven2/io/zonky/test/postgres"


def _needs_postgres(root: Path, prepared: Prepared) -> str | None:
    """Why the project needs PostgreSQL, or None (the same evidence the report header uses)."""
    from .technologies import _python_dependencies, _service_images, _settings_engines

    files = [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts][:20000]
    for tid, evidence in [*_service_images(root, files), *_settings_engines(root, files)]:
        if tid == "postgresql":
            return evidence
    if _python_dependencies(root) & {"psycopg", "psycopg2", "psycopg2-binary", "asyncpg"}:
        return "a PostgreSQL driver is a declared dependency"
    return None


def service_plan(root: Path, prepared: Prepared) -> list[Step]:
    reason = _needs_postgres(Path(root), prepared)
    if not reason:
        return []
    have = shutil.which("initdb") and shutil.which("pg_ctl")
    prepared.requirements.append({"ecosystem": "service", "service": "postgresql", "reason": reason, "binaries": "installed" if have else None})
    return [Step("postgresql", "service", "start a disposable PostgreSQL in the run workspace (local port, generated password)",
                 reason, downloads=[] if have else ["repo1.maven.org (portable PostgreSQL binaries)"],
                 detail=json.dumps({"installed": bool(have)}))]


def _verify_instance(data: Path, port: int) -> None:
    """The listener on 127.0.0.1:port is the server whose data directory is ``data`` (this run's), or this raises."""
    try:
        lines = (data / "postmaster.pid").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise ProvisioningError(f"no postmaster.pid in the run's data directory: {exc}") from exc
    if len(lines) < 4 or Path(lines[1]).resolve() != data.resolve() or lines[3].strip() != str(port):
        raise ProvisioningError(f"the server's postmaster.pid does not name this run's data directory and port {port}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(5)
        if s.connect_ex(("127.0.0.1", port)) != 0:
            raise ProvisioningError(f"nothing accepts connections on 127.0.0.1:{port}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _portable_binaries() -> Path:
    system = {"Windows": "windows", "Darwin": "darwin", "Linux": "linux"}.get(platform.system())
    arch = {"amd64": "amd64", "x86_64": "amd64", "arm64": "arm64v8", "aarch64": "arm64v8"}.get(platform.machine().lower())
    if not system or not arch:
        raise ProvisioningError(f"no portable PostgreSQL build for {platform.system()} {platform.machine()}")
    home = tools_dir() / "postgresql" / f"{POSTGRES_VERSION}-{system}-{arch}"
    if (home / "bin").is_dir():
        return home
    artifact = f"embedded-postgres-binaries-{system}-{arch}"
    url = f"{_CENTRAL}/{artifact}/{POSTGRES_VERSION}/{artifact}-{POSTGRES_VERSION}.jar"
    jar = download(url, published_sha256(url + ".sha256"), f"{artifact}-{POSTGRES_VERSION}.jar")
    staging = home.with_name(home.name + ".staging")
    shutil.rmtree(staging, ignore_errors=True)
    extract(jar, staging / "jar")
    [txz] = list((staging / "jar").glob("*.txz"))
    extract(txz, staging / "pg")
    home.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(home, ignore_errors=True)
    os.replace(staging / "pg", home)
    shutil.rmtree(staging, ignore_errors=True)
    if os.name != "nt":
        for tool in (home / "bin").iterdir():
            tool.chmod(0o755)
    return home


def prepare_service(step: Step, prepared: Prepared) -> None:
    if step.step_id != "postgresql":
        raise ProvisioningError(f"no preparation for {step.step_id}")
    installed = json.loads(step.detail).get("installed")
    bin_dir = Path(shutil.which("initdb")).parent if installed else _portable_binaries() / "bin"
    exe = ".exe" if os.name == "nt" else ""
    data = prepared.workspace / "env" / "pg"
    password = secrets.token_urlsafe(18)
    pwfile = prepared.workspace / "env" / "pg-password"
    pwfile.write_text(password, encoding="utf-8")
    created = run_command([str(bin_dir / f"initdb{exe}"), "-D", str(data), "-U", "assertiva", "--pwfile", str(pwfile),
                           "-A", "scram-sha-256", "-E", "UTF8", "--no-instructions"], Path.cwd(), timeout_s=300)
    pwfile.unlink(missing_ok=True)
    if not created.ok:
        raise ProvisioningError(f"initdb failed: {created.summary()}")
    port = _free_port()
    log = prepared.workspace / "env" / "postgresql.log"
    if os.name != "nt":  # a Unix socket path is limited to ~107 characters: a short directory of its own
        import tempfile

        socket_dir = tempfile.mkdtemp(prefix="apg")
        prepared.cleanups.append(lambda: shutil.rmtree(socket_dir, ignore_errors=True))
        options = f"-p {port} -k {socket_dir}"
    else:
        options = f"-p {port}"
    options += " -c listen_addresses=127.0.0.1 -c fsync=off"
    started = run_command([str(bin_dir / f"pg_ctl{exe}"), "-D", str(data), "-l", str(log), "-o", options, "-w", "-t", "60", "start"],
                          Path.cwd(), timeout_s=120)
    stop = [str(bin_dir / f"pg_ctl{exe}"), "-D", str(data), "-m", "immediate", "-w", "stop"]
    prepared.cleanups.append(lambda: run_command(stop, Path.cwd(), timeout_s=60))
    if not started.ok:
        raise ProvisioningError(f"PostgreSQL did not start: {started.summary()}")
    # Verify the target before any test connects: the server answering on this port is ours (its data directory).
    # Verify the target before any test connects, without a client or credentials: the server's own postmaster.pid,
    # in this run's data directory, must name that directory and the port, and the port must accept connections.
    _verify_instance(data, port)
    url = f"postgresql://assertiva:{password}@127.0.0.1:{port}/postgres"
    prepared.env.update({"DATABASE_URL": url, "PGHOST": "127.0.0.1", "PGPORT": str(port), "PGUSER": "assertiva",
                         "PGPASSWORD": password, "PGDATABASE": "postgres"})
    version = run_command([str(bin_dir / f"postgres{exe}"), "--version"], Path.cwd(), timeout_s=30).stdout.strip()
    prepared.services.append({"service": "postgresql", "version": version, "host": "127.0.0.1", "port": port,
                              "data_directory": str(data), "binaries": "installed" if installed else f"portable {POSTGRES_VERSION}",
                              "verified": "postmaster.pid in this run's data directory names it and the port; the port accepts connections",
                              "credentials": "generated for this run"})
    step.detail = f"{version} on 127.0.0.1:{port}"
