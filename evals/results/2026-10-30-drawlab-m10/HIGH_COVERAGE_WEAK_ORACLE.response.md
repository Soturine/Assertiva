# 98% line coverage with status-only API assertions

## Answer

The suite proves that **almost every line runs during the tests, and that the API endpoints answer HTTP 200** on the paths exercised. It does **not** prove that responses are correct, that data is persisted correctly, or that business invariants hold. The API tests check only the status code, so a wrong body, a missing or wrong write, or a broken invariant leaves every test green. The 98% figure describes execution, not checking. This is a classic false green.

## What can be claimed

| Claim | Basis | Evidence |
| --- | --- | --- |
| 98% of lines executed during the test run, for the reported scope | OBSERVED (if read from a coverage report of this run) or DECLARED (if only quoted) | the coverage report. Its metric kind (line), numerator, denominator, scope and exclusions must be stated. |
| The API tests assert only `status == 200` | OBSERVED, by reading the tests | the test files' assertions |
| The exercised endpoints return 200 for the inputs the tests use, without crashing | OBSERVED only if a run was seen passing; otherwise UNKNOWN | the run's per-test outcomes |
| Persistence and business invariants are not checked by these tests | INFERRED from the status-only oracles plus the code paths that write state | the tests read together with the handlers and repositories |

## What cannot be claimed

- "98% covered, so well tested." Coverage says what executed, not what was checked. It is a diagnostic, never a quality score.
- "The API behaves correctly." A 200 status does not cover the response body, headers, error contracts or side effects.
- "Data is saved correctly" or "invariants hold." No assertion observes persisted state, so a dropped commit, a wrong value, a partial write or a violated invariant (a negative balance, duplicate state, a broken total) would pass.
- "Negative paths are tested." Status-only tests that expect 200 do not exercise rejection or rollback. Even if some expect 4xx, a bare status does not check the error code or field, or the state after rejection.
- "The tests pass at this revision," unless a run of this revision was observed. Coverage alone does not tell you whether they passed.

## What I would do next

1. **Get a run if one has not been observed.** `assertiva audit <project> --execute` runs the suite in a disposable copy. It gives per-test outcomes and measured coverage, with metric kind and scope, and its oracle signals (`WEAK_ORACLE_SIGNAL`, `ERROR_STATUS_ONLY_SIGNAL`) are leads to check.
2. **Read the tests together with the code they cover.** Confirm that the status-only signal applies to every API test, not a sample. Check helpers, fixtures and custom matchers, which may assert more than the test body shows. List which tests are truly status-only.
3. **Map the invariants.** From the domain code or requirements, list the business rules and persistence effects (what must be written, what must never happen). Tie each one to a test that observes it: response body, database state, emitted event. Any rule with no observing test is a gap.
4. **Settle the false green with mutation or negative controls.** Run `assertiva audit --execute --mutate <file>` on the persistence and business-rule modules: drop a save, flip a condition in an invariant, change a computed value. Surviving mutants on covered lines are the direct evidence that coverage is not protection. Interpret each survivor by its witness, because some may be equivalent.
5. **Check harness fidelity.** Find out whether the API tests hit a real database or a mocked repository or in-memory store, and whether transactions are rolled back per test. A mocked persistence layer cannot prove persistence even with stronger assertions.
6. **Improve, only after the audit and with approval.** Use `assertiva improve`. Strengthen tests with assertions whose expected values come from the contract: the response body, persisted rows after the request, invariants after success and after rejection, and specific error contracts. Qualify them with `--mutate` on the baseline and the candidate, so that the protection gained is shown, not just a pass. The human approves the specific change IDs.

## What remains unknown

- **Whether the tests pass at this revision.** No run is stated. A run settles it.
- **Coverage scope.** Line or branch, which files are included, and whether test files or generated code are excluded. The report metadata settles it.
- **Whether helpers or fixtures assert more than the test bodies show.** Reading them settles it.
- **Whether any other test layer (unit or integration tests of the repositories or domain) checks the invariants.** Reading the rest of the suite and mapping invariants to tests settles it. This is why "invariants are unprotected" stays INFERRED until that mapping is done.
- **Which specific defects would go undetected.** Mutation runs or negative controls settle it.
- **Whether CI runs this suite on this revision.** The workflow files and provider runs whose head SHA matches HEAD settle it.

What this answer rests on: only the situation described. No run, report or source was observed here.
