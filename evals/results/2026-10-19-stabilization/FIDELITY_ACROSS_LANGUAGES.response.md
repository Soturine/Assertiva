# Integration tests of `orders` (Java) and `billing` (Python)

## Answer

The tests declared as integration in both services do not cross the database boundary. Their PASS results show that the service code behaves as expected against a double of the repository (`orders`) and a patched session (`billing`). They say nothing about entity-to-table mapping, SQL, schema, constraints, transactions or PostgreSQL behaviour. Real integration evidence does not exist yet. The PostgreSQL step is only PLANNED, because the project owner has not given provisioning consent. The staging `DATABASE_URL` must not be used for any of this.

## What the evidence shows

- **OBSERVED (read):** the Java integration tests use `@MockBean OrderRepository`. The Python integration tests patch `billing.db.session`.
- **OBSERVED (engine, run `e2c91f47a08b3d65`, `--execute`):** all tests PASS. Two `TEST_FIDELITY_MISMATCH` findings:
  - JVM: 4 tests declared integration, each replacing every boundary it crosses (DATABASE). Named: `OrderRepositoryIT.savesAndLoadsOrder` plus 3 more.
  - Python: 3 tests declared integration, same shape. Named: `billing/tests/integration/test_ledger.py::test_posts_entry` plus 2 more.
  - The engine's basis for both is INFERRED.
- **Scope limit:** the context confirms I read the Java and Python examples named above. It does not say I read the other 5 tests. For those, the fidelity claim is a lead, not a confirmed finding. The same pattern is likely but unverified.
- **DECLARED:** both services use PostgreSQL in production. The doubles therefore replace the very dialect and boundary the integration label claims to cover.
- **OBSERVED (engine):** the `postgresql` environment step is `PLANNED`, not executed. Isolation is `DISPOSABLE_COPY`.
- **DECLARED, not used:** `.env.example` points at a staging database host. The user's shell `DATABASE_URL` points at the staging database. The engine withholds connection-target variables. Running anything against that target would reach a shared system, so it is excluded.

## What green proves and does not

- **Proves (OBSERVED, on doubles only):** the service logic returns the expected results when the repository or session is faked.
- **Does not prove:** entity-to-table mapping, query correctness, constraints, applied migrations, commit and rollback behaviour, isolation levels, or behaviour on the production PostgreSQL version. Nothing shows that either service works against a real database.
- The "integration" label is not evidence. A class name, a marker or a folder does not make a test cross a boundary.

## Findings, ranked by consequence

1. **High: no real persistence boundary is exercised in either service.** A broken mapping, migration or query would stay green. Basis: INFERRED from the doubles I read plus the engine's fidelity signal.
2. **Unknown: whether CI runs these tests.** The context has no workflow or run data. If CI runs them, its green still reflects doubles only.
3. **Unknown: whether any test in either service touches a real database.** Not in the context. A DB-backed test elsewhere would change finding 1.

## Unknowns

- The 5 flagged tests not named in the context (4 JVM minus 1 named, 3 Python minus 1 named, roughly; exact list not given).
- Whether CI selects `integrationTest` or the integration marker.
- Whether Docker (for Testcontainers) is available on the machine.
- Whether rollback or constraint behaviour is tested anywhere.
- No Assurance Report: the context gives no `report_path`, and I did not write an assessment file.

## How to get real integration evidence

**Rule:** use only a disposable PostgreSQL on localhost, either a container or a local server. Never the staging database.

**Orders (Java/Spring)**
- In the integration source set, remove `@MockBean OrderRepository`. Let Spring Data bind to a datasource set by test properties pointing at the local disposable database, not the environment `DATABASE_URL`.
- Use Testcontainers PostgreSQL if Docker is present, or the disposable database from `--provision`.
- Rewrite `savesAndLoadsOrder` as save, flush, clear the persistence context, reload by id, assert the fields. Add a test that a constraint violation is rejected by the database, and one that a rollback leaves no row.
- Apply the real migrations (the tool is not named in the context) so the schema under test is the one shipped.

**Billing (Python)**
- Replace the `billing.db.session` patch with a real session bound to the disposable PostgreSQL, created by a fixture. Apply migrations.
- `test_posts_entry`: commit, then read back through a fresh session or connection. Add one rollback check.
- Keep the double-based tests as fast unit tests. Keep the integration label only where a real boundary is crossed.

**Obtaining the evidence**
- **Preferred:** the owner adds `provision = true` for this project in `<ASSERTIVA_HOME>/consent.toml`. The user writes that file, not the project. Then `assertiva audit . --execute --provision` prepares a disposable PostgreSQL, and the report shows the step as DONE or BLOCKED. Those rewritten tests would run in the disposable copy with per-test outcomes.
- **Prerequisite:** the new tests must exist first. Write them in the user's own copy, or in the candidate workspace from `assertiva improve`. Audit never modifies the project.
- **Without consent:** run the integration suite in a copy outside the tree against a local disposable PostgreSQL, and ingest the JUnit XML with `--junit-xml`. This is local evidence, not CI proof.
- **To tie a run to CI:** export the provider run for `git rev-parse HEAD` and pass it with `--ci-run`. Only `SAME_REVISION` on a clean tree proves that revision.
- **If CI declares an integration check:** `--run-check <CHECK_ID>` reproduces it in a disposable copy. Commands with effects need consent.

**Decision needed from the user:** consent for localhost-only provisioning for these two projects, or a go-ahead to run the local-copy path. Once given, I can proceed.

Assurance Report: not produced in this context.
