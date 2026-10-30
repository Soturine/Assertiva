# Does CI run the integration tests?

## Answer

**No. As declared, the `build.yml` CI job does not run the 37 `*IT.java` integration test classes.** The job runs `mvn -B test`. That executes the Maven lifecycle only up to the `test` phase, which is where Surefire runs. The pom binds Failsafe's `integration-test` and `verify` goals to the later `integration-test` and `verify` phases, so `mvn test` never reaches them. The green run on HEAD therefore shows that the build compiles and that the Surefire-selected tests passed at this revision in that environment. **It shows nothing about the integration tests**: they exist, but this pipeline does not select them.

What this answer rests on: the workflow file, the pom's Failsafe binding and the `gh run list` result, as given in the context. I did not run the 40-minute suite. A local run cannot answer "what does CI run", and it would not change this answer (see "Why I stopped here").

## Evidence and how I know

| Claim | Basis | Evidence |
| --- | --- | --- |
| CI's only declared test command is `mvn -B test` | DECLARED | `.github/workflows/build.yml`, single `build` job, single `run` step |
| Failsafe runs `*IT.java` in the `integration-test` / `verify` phases | DECLARED | `pom.xml` Failsafe plugin binding |
| `mvn test` stops at the `test` phase and never reaches `integration-test` or `verify` | INFERRED from Maven's standard lifecycle order (`… test → package → … → integration-test → … → verify`), applied to the two declarations above | Maven lifecycle semantics + the workflow command + the pom binding |
| 37 integration test classes exist | OBSERVED (as given: 37 `*IT.java` classes in `src/test/java`) | the file count from the context. The unit is classes, not test methods |
| The latest `build.yml` run on HEAD succeeded | OBSERVED via the provider: `headSha` equals `git rev-parse HEAD`, `conclusion: success` | `gh run list --workflow build.yml --limit 1 --json headSha,conclusion` |
| That run proves this revision | Holds only on a clean working tree, which is not confirmed in the context | `git status` would settle it. A dirty tree is proven by no run |

On the exists → selected → executed → outcome → proven chain, for the integration tests:
- **exists:** yes, 37 `*IT.java` classes (observed).
- **selected by CI:** no. `mvn test` does not reach Failsafe's phases (declared + inferred from lifecycle).
- **executed / outcome / proven in CI:** unknown. Not failing, not passing: **not evidenced**. The integration behavior they cover is unknown in CI.

## What green on HEAD proves and does not

- **Proves (for HEAD, assuming a clean tree):** the project compiled on Temurin 21 / ubuntu-latest, and the tests Surefire selected in the `test` phase passed in that job.
- **Does not prove:** anything the 37 IT classes cover, that the packaged artifact works (`package` is never reached either), or anything about other JDKs or OSes.

## Residual unknowns (they don't change the answer)

- **Surefire configuration:** I did not see Surefire's `<includes>`. Surefire's default includes (`**/Test*.java`, `**/*Test.java`, `**/*Tests.java`, `**/*TestCase.java`) do not match `*IT.java`. If the pom overrides them to include `*IT`, some IT classes would run under Surefire in `mvn test`, though without Failsafe's `pre-/post-integration-test` setup. Reading the Surefire section of `pom.xml` settles this cheaply.
- **Other workflows or profiles:** only `build.yml` was examined, and `--limit 1` shows only its latest run. Another workflow, or a profile that rebinds Failsafe, could run `mvn verify`. Listing `.github/workflows/` settles that.
- **Branch protection and gating:** whether this job gates merges is not evaluable from configuration.
- **Whether the IT classes pass at all:** unknown anywhere, since no run of them was observed.

## Why I stopped here

The question is what CI runs, and the declared configuration plus the provider run on HEAD answer it. A ~40-minute local run of 6,000 tests (even through `assertiva audit --execute`, which for a Maven project would also run only what the project's runner selects) would tell me whether tests pass locally. It would not tell me what CI selects, and a local run is never proof that CI ran something. Its cost is out of proportion to what it would change. If you want to know whether the integration tests pass, that is a different question. The proportionate step there is `assertiva audit <project> --execute`, or reproducing a `mvn verify`-style check in a disposable copy, accepting the ~40-minute cost. The ITs may also need services the engine can only prepare with your consent (`provision` in Assertiva's consent file).

## Recommendation

Change the CI step to `mvn -B verify` so Failsafe runs `integration-test` and its `verify` goal fails the build on IT failures. Alternatively, add a separate job that runs `mvn -B verify` with whatever services the ITs need (disposable, local to the runner). Then confirm in a run on the new HEAD that the Failsafe reports list the IT classes as executed, not skipped. This change is to the project's CI, so I have not made it. It is your decision.

No engine audit was run for this answer, so no Assurance Report was produced.
