# Assertiva mode: semantic-only — engine invocation not authorized; deterministic evidence suppressed in this evaluation context.

## Question
O CI roda os testes de integração? (Does CI run the integration tests?)

## Answer: NO

**Evidence category: DECLARED FACT (E2)**

The CI workflow `.github/workflows/build.yml` declares a single Maven invocation:
```yaml
- run: mvn -B test
```

This executes the `test` goal only, which runs unit tests via maven-surefire-plugin.

**What the declared configuration does NOT run:**

The `pom.xml` binds `maven-failsafe-plugin` to the `integration-test` and `verify` goals for the 37 `*IT.java` integration test classes. However, the Maven `verify` goal is not invoked in the CI pipeline.

To run integration tests, the CI workflow would need to execute `mvn -B verify` (or `mvn -B integration-test`) instead of (or in addition to) `mvn -B test`.

**Verification surface finding:**

- **Present in repository:** `pom.xml` configuration for integration testing (37 IT classes discovered)
- **Present in CI:** Only unit-test execution
- **Gap:** Integration tests are defined but not executed in the delivery pipeline

**Recommendation:**

If integration tests are part of the release safety net, add the `verify` goal to CI or create a separate integration-test job. This closes the verification-surface gap between local development (where developers may run `mvn verify` locally) and the authoritative CI/CD pipeline.
