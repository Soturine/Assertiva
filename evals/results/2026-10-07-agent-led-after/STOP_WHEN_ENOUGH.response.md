# Assessment: Does CI Run Integration Tests?

## Answer

**No. CI does not run the integration tests.**

The workflow runs only `mvn -B test`, which invokes maven-surefire-plugin and executes `*Test.java` unit tests. The 37 `*IT.java` integration test classes are configured in pom.xml to run under maven-failsafe-plugin's `integration-test` and `verify` goals, but the CI workflow never invokes those goals. Therefore, the integration tests never run in CI.

## Evidence

**CI workflow (DECLARED):**
`.github/workflows/build.yml` runs:
```yaml
- run: mvn -B test
```

This command is maven-surefire-plugin's default goal, which runs unit tests only.

**Project configuration (DECLARED):**
`pom.xml` binds maven-failsafe-plugin to `integration-test` and `verify` goals and runs `*IT.java` files (37 integration test classes exist). However, the CI workflow never calls these goals.

**What green CI proves (OBSERVED):**
The latest run succeeded (`conclusion: success`), with HEAD SHA confirmed. This proves that `mvn -B test` (unit tests) passed at HEAD. It does not prove that integration tests pass, because they were never run.

## How I know

- **DECLARED**: The workflow file explicitly states which command runs; configuration files declare what *should* run, not what did.
- **INFERRED**: Maven's standard behavior ties `mvn test` to surefire and integration test goals to `verify`/`integration-test`. The workflow omits the latter, so integration tests are not executed.

## What remains unknown

- Whether the integration tests themselves pass (they are never run in CI).
- Whether the local build (with `mvn verify`) passes the integration tests.
- Whether there are conditions, profile activations, or other configuration in pom.xml that might alter the mapping (not provided in context).

## Recommendation

Add `mvn verify` to the CI workflow (replacing or supplementing `mvn test`) if integration test assurance is a delivery requirement. Ensure the CI matrix and environment support any external dependencies or services integration tests need.
