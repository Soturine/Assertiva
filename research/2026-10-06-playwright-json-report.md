# Playwright JSON Report — 2026-10-06

Dated research behind `assertiva/adapters/playwright.py`. Re-check before relying on details.

## Sources

- playwright.dev/docs/test-reporters (JSON reporter; fetched 2026-10-06).
- `JSONReport` types shipped in `playwright/types/testReporter.d.ts` of `@playwright/test` 1.63.0 (the installed fixture).
- Real runs of `tests/fixtures/js-playwright` (recorded under `tests/fixtures/playwright-json/`, machine paths replaced).

## Format

- `--reporter=json` prints to stdout unless `PLAYWRIGHT_JSON_OUTPUT_FILE` (full path; overrides `PLAYWRIGHT_JSON_OUTPUT_DIR` / `PLAYWRIGHT_JSON_OUTPUT_NAME`) or a config `outputFile` is set.
- `config.projects[]`: `id`, `name`, `testDir`, `retries`, `repeatEach`, `timeout`, `outputDir`, `metadata`... **No `use` / `browserName`**: the report does not record which browser a project runs.
- `config.projects` lists every project in the config even with `--project` filtering (observed): this is the DECLARED set.
- `suites[]` (one per file; nested `suites` for `describe`), `specs[]` with `title`, `file`, `line`, `column`, `tags`, `tests[]`. `suite.file` and `spec.file` are relative to the project's `testDir`, not to the config root.
- `tests[]`: one per project materialization: `projectName`, `projectId`, `expectedStatus`, `status` (`expected | unexpected | flaky | skipped`), `annotations`, `results[]`.
- `results[]`: one per attempt: `status` (`passed | failed | timedOut | skipped | interrupted`), `retry`, `duration` (ms), `error`, `errors`, `attachments[]` (`name`, `contentType`, `path` or `body`).
- `errors[]` at the top level: errors outside tests. A test file that throws while loading aborts the whole run: `suites` is empty and the error carries the file `location`.

## Observed behavior (1.63.0)

- `retries: 1` with a test failing only on its first attempt: `status: flaky`, two results; with `screenshot: only-on-failure` and `trace: on-first-retry`, the first attempt has `screenshot` + `error-context`, the retry has `trace`.
- A selected project whose browser is not installed: every attempt fails with `browserType.launch: Executable doesn't exist at ...` and the test is `unexpected`. This is a missing environment, not a behavior failure.
- `test.fail()`: `expectedStatus: failed`, `status: expected`. `test.fixme`: `status: skipped`, annotation `fixme`.
- Tests generated in a loop share the spec `line`/`column`.
- `--list` produces the same shape with `results: []` for every test.
- `playwright install` downloads from `cdn.playwright.dev`, which redirects to `storage.googleapis.com` for Chromium builds; networks that block that host cannot install browsers. Playwright can drive an installed Chromium-based browser through the `channel` option (`msedge`, `chrome`) without downloading.

## Decisions

- Run only the project's installed Playwright (`node node_modules/playwright/cli.js test --reporter=json`); never `npx`, never install dependencies or browsers.
- Projects: DECLARED (config), SELECTED (in the report), EXECUTED (an attempt actually ran). Engines (chromium/firefox/webkit) are inferred from project names and the report says so; an engine with no project is NOT_CONFIGURED. None of these is a failure by itself.
- Missing browser → NOT_RUN invocations plus a run limitation, never FAILED and never PASSED.
- Flaky → passed with the attempt count and a run limitation. Attachments are kept as name/type/attempt/relative path; files written in a disposable copy are removed with it.
- A literal non-local `baseURL` in the config blocks execution (no remote environments). A `baseURL` taken from the environment cannot be checked statically.
- Locator kinds (ROLE, LABEL, PLACEHOLDER, TEXT, TEST_ID, CSS, XPATH, OTHER, UNKNOWN) are static E3 evidence with an informational direction: coupling and semantics, not a score.
- No screenshot comparison or visual regression engine.
