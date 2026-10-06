# Maven Surefire / Failsafe / JaCoCo Reports — 2026-10-06

Dated research behind `assertiva/adapters/maven.py`. Re-check before relying on details.

## Sources

- Surefire test report XSD (maven.apache.org/surefire-archives/surefire-3.5.6/maven-surefire-plugin/xsd/surefire-test-report.xsd; reports written by 3.6.0 declare report `version="3.0.2"`).
- maven.apache.org Surefire/Failsafe "Rerun Failing Tests" examples (`flakyFailure`/`flakyError`, `rerunFailure`/`rerunError`).
- Maven Central metadata (2026-10-06): JUnit BOM 6.1.3, maven-surefire-plugin 3.6.0, maven-failsafe-plugin 3.6.0, jacoco-maven-plugin 0.8.15, maven-compiler-plugin 3.16.0; Apache Maven 3.10.0; Temurin JDK 21.0.12.1.
- Real runs of `tests/fixtures/java-maven` and a variant copy (recorded under `tests/fixtures/maven-reports/`, system properties removed).

## Format (observed)

- One `target/surefire-reports/TEST-<class>.xml` per test class (Surefire, `test` phase) and `target/failsafe-reports/TEST-<class>.xml` (Failsafe, `integration-test` phase), plus `failsafe-summary.xml`.
- `<testsuite name tests errors skipped failures flakes time>`; `<properties>` holds **every JVM system property** of the forked JVM (paths, user name, host): never copied by Assertiva.
- `<testcase name classname time>`; JUnit Platform parameterized cases are named `method(ParamTypes)[n]`.
- `@Disabled("reason")` → `<skipped message="reason"/>`; assertion failure → `<failure>`; other exceptions → `<error>`.
- With `-Dsurefire.rerunFailingTestsCount=1`: a test failing every attempt has `<failure>` plus `<rerunFailure>` per rerun (`<error>` + `<rerunError>` likewise); a test passing on a rerun has only `<flakyFailure>`/`<flakyError>` (no `<failure>`).
- `-Dmaven.test.failure.ignore=true` records failures instead of stopping the build, so Failsafe still runs after Surefire failures.
- Selection: `-Dtest=Class#method,Other#m` (Surefire) and `-Dit.test=...` (Failsafe); `-Dtest` overrides includes, so naming an IT class there would run it in the test phase. Selection is per method: all parameterized cases of a method run. Failsafe's documented default includes are `**/IT*.java`, `**/*IT.java`, `**/*ITCase.java`.
- JaCoCo `report` goal writes `target/site/jacoco/jacoco.xml` with report-level `<counter type covered missed>`; `<sessioninfo id>` contains the host name.
- Failsafe without the `verify` goal never fails the build on integration-test failures.

## Decisions

- Maven + Surefire/Failsafe is the first Java slice; Gradle is not implemented.
- Each report is parsed by the generic JUnit XML parser; the Maven adapter adds phase, reruns/flaky, parameter identity, source file and JaCoCo coverage only.
- Maven runs offline (`-o`) with failures recorded; nothing is downloaded; the project's `mvnw` is never run (it may download Maven). Missing Maven is BLOCKED; missing local dependencies are BLOCKED with that reason.
- Only report files written by the current run are read (snapshot of existing reports before the run).
- Unit/integration is reported as the build's phase classification, not as proof of test scope.
- Build Verification Surface from `pom.xml`: Surefire (default lifecycle binding), Failsafe (gate depends on the `verify` goal), JaCoCo (`check` goal = enforced threshold, otherwise reporting only). Profiles and parent POMs are not resolved.
