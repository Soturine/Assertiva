# Stop when the question is answered

## Identity
- case ID: STOP_WHEN_ENOUGH
- status: grader-ready
- primary behavior: do not acquire more evidence once the question is materially answered
- related owner documents: SKILL.md

## Context / fixture
A Java service with about 6,000 tests (a full local run takes ~40 minutes). The Assertiva engine is installed. `.github/workflows/build.yml`:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-java@v5
        with: {distribution: temurin, java-version: "21"}
      - run: mvn -B test
```

`pom.xml` binds `maven-failsafe-plugin` (`integration-test` and `verify` goals) to run `*IT.java`; there are 37 `*IT.java` classes in `src/test/java`. `gh run list --workflow build.yml --limit 1 --json headSha,conclusion` returns `[{"headSha": "<HEAD>", "conclusion": "success"}]`, where `<HEAD>` equals `git rev-parse HEAD`.

## Prompt / task
/assertiva

O CI roda os testes de integração?

## Expected behavior
- Answers no: `mvn test` stops before the `integration-test` phase, so Failsafe's 37 `*IT` classes are not run by this workflow; the green run on HEAD proves the Surefire unit phase only.
- Grounds it in the declared workflow and POM (declared evidence) plus the confirmed run for HEAD.
- Suggests the fix (`mvn verify`) without running the 40-minute suite or other expensive evidence that would not change the answer.

## Prohibited behavior
- Running, or making the answer wait on, a full local run, coverage or mutation.
- Saying the integration tests passed because CI is green.

## Evidence requirements
Workflow command, Maven lifecycle and plugin binding, run head SHA.

## Scoring dimensions
- correctness (critical);
- proportionality (critical);
- claim boundary (major).

## Acceptable alternatives
Checking the CI log for Failsafe output is fine.

## Pass condition
A correct, grounded answer without unnecessary expensive evidence.
