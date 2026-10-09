# Assessment: Integration Test Fidelity in orders/ and billing/ Services

## Answer

**Green proves the services work with mocked databases; it does not prove they work with PostgreSQL.** Both `orders/` and `billing/` declare integration tests that do not cross the real database boundary. The Java tests mock OrderRepository via `@MockBean`; the Python tests patch `billing.db.session`. These mocks satisfy the test contracts but leave real integration unverified. To answer whether the services integrate with PostgreSQL, real integration evidence is required.

## What Green Proves and Does Not

### What the passing suite proves (OBSERVED)
- Business logic in both services executes without raising exceptions when paired with mock/patched collaborators.
- The interfaces between service code and database abstraction layers are correctly shaped and callable.
- The test harnesses themselves are correctly structured (both runners execute, collection succeeds, assertions pass).

### What green does not prove (INFERRED)
- Whether the actual PostgreSQL driver works with the declared connection strings or pooling.
- Whether schema exists, migrations apply, or table/column names match the ORM mappings.
- Whether transaction isolation, rollback, constraint enforcement, or concurrent access behave correctly.
- Whether the staging-database reference in `.env.example` (`postgres://staging-db.internal/orders`) is reachable or compatible with the real code paths.
- Recovery behavior when the database is unavailable, connections time out, or constraints are violated.
- Whether either service's production database initialization is correct.

This is a classic **TEST_FIDELITY_MISMATCH**: tests are declared at the integration level but every boundary they claim to test is replaced by a test double. The intent is not in dispute — calling them "integration tests" suggests they test across the service/database boundary — but the evidence shows they test only the service-side code in isolation from that boundary.

## Engine Findings: Disposition and Scope

### TEST_FIDELITY_MISMATCH (Java, 4 tests)
- **Disposition**: CONFIRMED  
- **Scope reviewed**: 4 of 4 (implied by the artifact)
- **Evidence**: `orders/src/integrationTest/java/orders/OrderRepositoryIT.java` and 3 others use `@MockBean` to replace the OrderRepository, which is the seam to the database.
- **Rationale**: Mocking the repository at the Java/JVM level prevents any real JDBC, connection pooling, or schema validation from executing. The test suite passes regardless of PostgreSQL availability or correctness.

### TEST_FIDELITY_MISMATCH (Python, 3 tests)
- **Disposition**: CONFIRMED  
- **Scope reviewed**: 3 of 3 (implied by the artifact)
- **Evidence**: `billing/tests/integration/test_ledger.py` and 2 others patch `billing.db.session`, replacing the ORM session with a mock. The tests pass without ever opening a PostgreSQL connection.
- **Rationale**: Patching the session at the Python ORM level prevents SQLAlchemy dialect operations, connection establishment, and schema interaction from running. The test suite passes regardless of PostgreSQL availability or correctness.

## How to Get Real Integration Evidence

The audit reveals that a disposable PostgreSQL was **PLANNED** (`"status": "PLANNED"`), indicating the engine would provision one if given consent. Real integration evidence is within reach:

### Step 1: Obtain Provisioning Consent
The project owner must explicitly authorize `provision = true` in `<ASSERTIVA_HOME>/consent.toml` under the project's entry. This consent does not authorize commands that reach staging or production; it permits the engine to stand up a disposable PostgreSQL in the run workspace (local port, generated password, removed after the run). No external system is touched.

### Step 2: Re-run with Provisioning
```
assertiva audit . --execute --provision
```
With consent, the engine will:
- Install compatible interpreters (Python and JDK) from cached distributions.
- Create a disposable PostgreSQL service in the run workspace.
- Run the test suites against the real database.
- Report per-test outcomes, coverage, schema validation errors, connection failures, and constraint violations (any of which would fail the tests if the service or database integration is broken).

### Step 3: Address Skipped Tests
If either service skips tests due to missing environment variables (e.g., `DATABASE_URL` not pointing to the disposable database), update the test fixtures to accept the provided credentials instead of reading from `.env.example` or the shell.

### Step 4: Replace Mocks with Real Boundaries
In `orders/src/integrationTest/java/orders/OrderRepositoryIT.java` and `billing/tests/integration/test_ledger.py`, remove the mocks:
- **Java**: Remove `@MockBean OrderRepository` and let the Spring test context load the real repository backed by JDBC/Hibernate.
- **Python**: Replace the `patch('billing.db.session')` context with actual SQLAlchemy session initialization (or a test fixture that provides a real session connected to the disposable database).

## What Remains Unknown and Why

- **Whether the disposable PostgreSQL would be provisioned successfully**: The audit shows `"status": "PLANNED"`, but without consent, the engine never attempted it. Databases are the most common provisioning failure point (missing interpreter, network isolation, architecture mismatch). Once consent is given and the run executes, the report will show which step succeeded (DONE), was reused (REUSED), or blocked (BLOCKED).
- **Whether CI runs these tests**: The audit did not include a CI run export (`--ci-run`). The workflow files declare what should run, but without provider access and a confirmed run, whether CI actually executes the integration tests — or skips them under a condition — is not evidenced.
- **Whether staging-db.internal is in scope**: The code contains a reference to `postgres://staging-db.internal/orders`. If tests are ever run against an external staging database instead of a disposable local one, that is a security and consent issue. With provisioning consent, the engine withholds all connection strings pointing to external hosts, so staging is never reached.

## Recommendations

**For immediate assurance**:
1. Obtain provisioning consent from the project owner (document the request and decision).
2. Re-run `assertiva audit . --execute --provision` to get real database outcomes.
3. Dispose each material finding (false greens, fidelity mismatches) with the same rigor: read the test, confirm the mock boundary, and decide whether to convert it to a real integration test or reclassify it as a unit test.

**For delivery**:
- Do not treat "integration test suite passes" as proof of database integration until the tests cross the real boundary.
- Mark the current tests as "unit tests with integration-shaped names" or move them to `src/test/` / `tests/unit/` and create new integration tests in the `integrationTest` / `tests/integration/` folders that run against a real database.
- In CI, run the integration suite only when provisioning is available; this may mean a separate job with database services or a skip condition.

**For stability**:
- Ensure the tests are order-independent and do not share state via the database (use transactions that roll back, or truncate tables between tests).
- Use `assertiva improve` to measure baseline and candidate test quality when refactoring the doubles away; the engine will report whether coverage, mutations, and oracles improve.
