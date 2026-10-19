# Execution security: boundaries, fixes and residual risks

What protects the user and the audited project when Assertiva runs project code, prepares environments or starts
services; what the 0.7.3 re-audit fixed; and the risks this version does not eliminate. The claim boundary in
`STATUS.md` and the consent rules in `references/ENGINE.md` stay canonical; this page records the security review
behind them. Re-audited on 2026-10-19 against `v0.7.2` (`8de5a24`): `assertiva/process.py`, `assertiva/environment.py`,
`assertiva/workspace.py` (copies and links, read only), `assertiva/adapters/provisioning.py`, `assertiva/adapters/services.py`,
`assertiva/adapters/python_package.py` and the Gradle adapter's use of tool homes.

## Boundaries that hold (each with tests)

| Boundary | Mechanism | Evidence |
| --- | --- | --- |
| The audited tree is never written by an audit | fingerprint before and after; any change exits 3 | `tests/test_audit_exit_contract.py`, CI read-only invariant through the installed CLI |
| Project code runs only in a disposable copy | copies under `ASSERTIVA_HOME`, links never followed, removed without following links | `tests/test_boundaries.py` |
| Credentials and connection targets do not reach project code | `child_environment` withholds credential-looking names, URL passwords and connection variables; consent (`<ASSERTIVA_HOME>/consent.toml`, never the project) passes a variable, a connection only to a local host | `tests/test_execution_integrity.py` |
| Commands with effects outside the copy need the user's consent; deploy/publish never run | command classification + consent file | `tests/test_execution_integrity.py` |
| Downloads are verified and bounded | HTTPS only, size limit, sha256 before use, cached by checksum and re-hashed on reuse | `tests/test_provisioning.py` |
| Archives cannot escape their target | absolute paths, `..`, drive letters, outside links, devices and oversize refused before anything is written | `tests/test_provisioning.py` |
| A disposable database is the run's own | pid file, SCRAM-SHA-256 login in which the server proves it holds the generated password, reported data directory and port | `tests/test_services.py` |
| Timeouts end the whole process tree | own process group/session; `taskkill /T` on Windows, `killpg` on POSIX | `tests/test_execution_integrity.py` |

## Fixed in 0.7.3

- **A project value ran as probe code.** The artifact adapter checked whether the build backend is importable with
  `python -c "import <backend>"`, the backend name read from the project's `pyproject.toml`. A value such as
  `os;exec(bytes((...)))` (no `.` or `:`, so it survived the name split) ran in the user's working directory, outside
  the disposable copy, during `audit --execute`. Module probes now receive the name as an argument, refuse anything that
  is not a dotted module name without running it, and never search the start directory.
- **Probes imported the project's modules.** Interpreter probes (`version`, installed distributions, `-m venv`)
  started in the user's working directory; `python -c` and `-m` put that directory first on `sys.path`, so a
  `json.py` or `platform.py` at the root of a project the user stood in ran outside the copy. Probes now start in an
  empty temporary directory.
- **The provisioning plan named the wrong package source.** The plan said "PyPI (pip)" while the project's requirement
  files can redirect pip (`--index-url`, `--extra-index-url`, `--find-links`, `--trusted-host`); consent was asked for
  the wrong origin. The plan now lists the sources the project declares (credentials redacted) and drops PyPI when an
  index URL replaces it.
- **The generated database password was written with default permissions.** On POSIX the file `initdb` reads is
  now created owner-only (0600) before the password is written.
- **Command output was read whole into memory** to compute its digest. A test printing gigabytes could exhaust the
  auditor's memory. The digest is now computed in chunks and only the tail is read; digests and tails are unchanged.

Each fix has a test that fails on 0.7.2 (`tests/test_probe_boundaries.py`; the password-file test runs on POSIX only).

## Residual risks (not eliminated in 0.7.3)

Stated here so that no report or answer implies more isolation than exists. "Not verified" means no test exercises it.

1. **No sandbox.** Project code runs with the user's permissions and network (isolation level `DISPOSABLE_COPY`, never
   `SANDBOX`). It can read credential *files* the environment filter cannot withhold (`~/.aws/credentials`, `~/.npmrc`,
   `~/.pypirc`, `~/.docker/config.json`, `~/.kube/config`, SSH keys, git credential helpers, the OS keyring) and reach
   any network host, including a Docker socket the user can use. Container/VM confinement is a roadmap item, not a
   0.7.3 change.
2. **Shared tool caches are writable by the code that runs.** `GRADLE_USER_HOME` (`<tools>/gradle-home`), the pip and npm
   caches, and the extracted JDK, Gradle and PostgreSQL directories are shared between runs and projects. A provisioned
   tool is reused when its directory exists, without re-verification (downloads are re-hashed; extracted trees are
   not). Code from one audited project could plant a Gradle init script or alter an extracted tool that a later audit
   of another project uses. Mitigation available today: a dedicated `ASSERTIVA_TOOLS` per trust domain.
3. **Checksums come from the publisher over TLS, not signatures.** The JDK checksum comes from the same Adoptium API
   response as its link; Gradle and PostgreSQL checksums from the `.sha256` next to the artifact (or the project's
   wrapper properties, which can only make a download fail). This detects corruption and a changed file at rest, not a
   compromised publisher. PGP/Sigstore verification is not implemented.
4. **Package managers follow what the project's locks declare.** `npm ci` fetches each `resolved` URL in the lockfile
   (integrity hashes come from the same lockfile); pip honors index options and `-r` includes in requirement files. The
   plan names npm's registry and the pip sources it found at top level, not every URL a lockfile or nested file names.
   Whether `npm ci --ignore-scripts` runs `prepare` scripts of git dependencies in every npm version: not verified.
5. **Processes that leave their group survive a timeout.** A descendant that starts a new session (POSIX `setsid`,
   daemons) or breaks away from the job on Windows is not ended by the tree kill. The provisioned PostgreSQL is stopped
   by its own cleanup; servers a test starts are not tracked. Not verified by a test.
6. **Output files are bounded in memory, not on disk.** A command's full output is kept in temporary files until it
   ends (needed for the digest); a runaway writer can fill the temporary volume before its timeout.
7. **Local ports are not exclusive.** The disposable PostgreSQL's port is chosen free and then bound by the server;
   another local process can race for it. The identity checks make that a failed start, never a connection to the wrong
   server. Other local users can reach the port; the password is generated per run.

## When to revisit

Any change to `process.run_command`, `environment.extract`/`download`, consent, provisioning or services, a new tool
download, or a new probe that runs an interpreter re-opens this page: update the tables and add the test that proves
the boundary.
