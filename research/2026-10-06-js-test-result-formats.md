# JavaScript Test Result Formats — 2026-10-06

Dated research behind `assertiva/adapters/jest.py`. Re-check before relying on details.

## Jest (30.5.x)

Sources: jestjs.io CLI docs (`--json`, `--outputFile`, `--testLocationInResults`, `--passWithNoTests`, `--coverage`) and `jestjs/jest` sources `packages/jest-test-result/src/formatTestResults.ts`, `packages/jest-types/src/TestResult.ts` (main, fetched 2026-10-06).

- The documented `testResultsProcessor` structure (`testResults[].testResults[]`, `testFilePath`) is **not** the `--json` file. `--json` goes through `formatTestResults`: `testResults[]` has `name` (absolute test file path), `status` (`passed | failed | skipped | focused`), `message`, `assertionResults[]`.
- A test file that fails to run (syntax/import error) is `status: failed` with an empty `assertionResults` and the error in `message`.
- `assertionResults[]`: `ancestorTitles`, `title`, `fullName`, `status` (`passed | failed | skipped | pending | todo | disabled | focused`), `duration` (ms), `failureMessages`, optional `location` (with `--testLocationInResults`), `invocations`, `retryReasons`.
- Observed with a real run: `test.skip` is `pending`, `test.todo` is `todo`; `test.each` cases share the same `location`; a file containing pending/todo tests has file status `focused`; with `jest.retryTimes`, a test that passed on its second attempt reports `passed` with `invocations: 2` and (without extra configuration) no `retryReasons` — the first failure is not preserved.
- Output contains non-ASCII characters (`●`, `›`): read as UTF-8.
- Coverage: `--coverageReporters=json-summary` writes `coverage-summary.json` (istanbul) with `total.{lines,branches,functions,statements}.{total,covered,skipped,pct}`.

## Vitest (5.0.x)

Source: vitest.dev/guide/reporters (fetched 2026-10-06).

- The `json` reporter "generates a report of the test results in a JSON format compatible with Jest's `--json` option" (default `.vitest/json/output.json`, configurable with `outputFile`), with extra fields such as `meta`.
- Not implemented or verified by Assertiva yet: compatibility is the vendor's claim; a Vitest adapter needs its own fixture before any support is claimed.

## Decisions

- Run only the project's installed Jest (`node node_modules/jest/bin/jest.js`); never `npx` (it may download) and never install dependencies. Missing Node or Jest is BLOCKED.
- Table cases are grouped into one declaration only through Jest-reported locations.
- Retried tests are reported as passed with an explicit note and a run limitation, never as a plain pass.
