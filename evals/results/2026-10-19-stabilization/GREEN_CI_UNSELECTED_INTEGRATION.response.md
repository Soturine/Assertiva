# Answer: are partial refunds covered?

**No, not yet.** The green CI run on `9f2c1e7` shows that the five mocked unit tests in `src/refunds/refunds.test.ts` passed. It does not show that partial refunds are tested against the database. The seven integration tests in `tests/integration/refunds.int.test.ts` were never selected by CI and did not run in this audit. I would not tell the release manager "covered" yet.

## What the green run proves

- **Revision and job.** The provider run has `head_sha` 9f2c1e7, identity `SAME_REVISION`, provenance `EXTERNAL_VERIFIED`, and the `test` job concluded `success` (OBSERVED). The tree was clean, so this run is valid for that revision.
- **What CI runs.** The only test step is `npm test`, which is `vitest run`. Its config includes `src/**/*.test.ts` only. The check `github-actions:ci.yml:test:2` is declared as `gate: true`, `selected: UNCONDITIONAL` (DECLARED). Its `executed` field stays `UNKNOWN` in the surface, so per-test execution in CI is not confirmed by the export.
- **The 5 mocked unit tests.** They are under `src/`, so they are selected by CI. They passed as part of the job (INFERRED from the job's success and the selection). The export gives only an aggregate (`vitest`, 212 invocations, 212 PASSED), not per-test outcomes, so I cannot confirm from this context that the five refund tests are among the 212.
- **What those 5 tests can prove.** They replace the gateway client and the refunds repository with `vi.mock`. They check that the service calls `gateway.refund` with the computed amount. Two check the error on over-refund. Against doubles, they prove the arithmetic and the call contract. They do not prove the balance in the database, the ledger rows, or the concurrency behavior. If the over-refund check lives in the mocked repository, those two tests check the double's behavior, not the real rule (lead, not confirmed; the code was not read).

## What the integration tests would prove, and what is unknown

| Step | Status | Evidence |
| --- | --- | --- |
| exists | Declared: 7 tests in `tests/integration/refunds.int.test.ts` | DECLARED (your description and the config) |
| selected | No. `package-script:test:integration` is `NOT_IN_CI`. `vitest.config.ts` does not include `tests/integration/**`, and `ci.yml` has no step for the integration config. | DECLARED / observed in the surface |
| executed | Not run. The check is `NOT_RUN`. The engine withheld `DATABASE_URL`, so `--execute` could not reach a database. | OBSERVED (`NOT_RUN`) |
| outcome | UNKNOWN. Not run, so neither passed nor failed. | UNKNOWN |
| proven | UNKNOWN for the balance, the ledger and the unique-constraint rejection. Nothing crossed the real database boundary in this audit or in CI. | UNKNOWN |

The real-database behavior you are asking about (remaining balance after two partial refunds, the concurrent double refund rejected by the unique constraint, ledger rows) is therefore **unknown**, not passing.

## Why I did not obtain more evidence

- The shell's `DATABASE_URL` points at a staging database. Running the integration config with it would write to a shared system. I did not run it and I do not recommend it. The engine's withholding of that variable was correct.
- Running the integration tests needs a disposable local PostgreSQL (a container or a local instance), and a consent entry for that command in the user's consent file. Setting that up is the user's decision.
- The audit ran `--execute` with the CI export. Per-test CI outcomes are not in the export, so that gap needs the CI log, which I did not have.

## What would settle it

1. Show the per-test outcomes of the CI `test` job, or confirm that the five refund unit tests appear in its log, to close the gap on the unit side.
2. Run `tests/integration/refunds.int.test.ts` against a disposable local PostgreSQL, using `--run-check` or `--provision` with the user's consent. Record the exit code and per-test outcomes.
3. Read the 5 unit tests and the over-refund rule to check whether the error assertions test the real rule or the double.

## Recommendations

- For the release manager, state precisely: "The amount sent to the payment gateway for partial refunds is unit-tested with mocks, and that suite passed on this commit in CI. The database behavior (balance, ledger, concurrent double refund) is not run by CI and has not been verified."
- Add the integration suite to CI, as a gating job with a disposable PostgreSQL service container, so it runs on every change. Until then, its existence in the repository is not evidence of coverage.
- Keep `DATABASE_URL` for staging out of any test run.

## Claims summary

- OBSERVED: CI job `test` success on `9f2c1e7` (`SAME_REVISION`, `EXTERNAL_VERIFIED`); integration check `NOT_IN_CI` and `NOT_RUN`; 212 vitest invocations all PASSED (aggregate).
- DECLARED: `npm test` scope, `vitest.config.ts` include pattern, the integration config's include pattern and `DATABASE_URL` read.
- INFERRED: the 5 unit tests passed as part of the job; the mocked unit tests do not prove database behavior.
- UNKNOWN: per-test outcomes in CI; whether the two over-refund assertions test the real rule; any outcome of the 7 integration tests.

Assurance Report: not given in this context (no `report_path` was provided).
