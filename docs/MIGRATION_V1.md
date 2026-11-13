# Migrating to Assertiva 1.0

These are the contract changes from 0.10.1 to 1.0.0. Each one
fixes a report that said more, or less, than its evidence. None changes a CLI default.

## Report JSON

| Change | Before (0.10.1) | Now | What to do |
|---|---|---|---|
| Execution counters exclude imported results | `test_invocations`, `passed`, `failed`, `errors`, `skipped`, `xfailed`, `xpassed`, `collection_errors`, `wall_clock_s` and `test_time_accumulated_s` summed every run, including JUnit, CTRF and Allure files | they count **runs Assertiva executed**; ingested cases are `imported_invocations`, `imported_passed`, `imported_failed`, `imported_errors`, `imported_skipped` and `imported_time_accumulated_s` (tier E2) | A consumer that reads `test_invocations` from a report that only ingests results must read `imported_invocations`. A report with no executed run has no `test_invocations` |
| An attempted mutation run that stopped is not an "unreadable report" | `MUTATION_REPORT_UNREADABLE` | `MUTATION_RUN_NOT_COMPLETED` with `stage` (`selection`, `baseline`, `runner`, `planning`, `budget`, `copy`, `results`, `environment`, `tool_selection`, `execution`). `MUTATION_REPORT_UNREADABLE` now means an imported report file could not be read | Match on both codes. A mutation run record has a new `stage` field (null for reports read from files) and `config.baseline.tests_ran` |
| unittest and Django runs carry their code identity | `source_identity`, `interpreter` and `temp_root` were `null` | filled in the same way as for pytest; `source_identity.in_artifact` exists for installed-artifact runs | Nothing to change. A `null` from an older report still means UNKNOWN |
| Installed-artifact tests must prove they imported the artifact | a green pytest run against the wheel was PASS whatever it imported | PASS needs `source_identity.status == INSTALLED_ARTIFACT`; otherwise the `tests` check is UNKNOWN. unittest projects are now run against the wheel | Expect some former PASS results to become UNKNOWN, with the reason in `limitations` |
| Collection causes and load errors | free text, first 300 characters | sanitized before the bound (credentials, known token shapes, e-mail addresses, absolute paths), with `collection_error_details` (`cause`, `type`, `kind`, `chain`, `sanitizer`) | Read `kind` instead of parsing the message |
| Cleanup record | the limitation named the absolute temp path | the limitation names the directory only; the artifact's `environment.cleanup` holds REMOVED or INCOMPLETE with the error types | Do not rely on the path in the text |
| New optional top-level `gate` | none | present only with `--fail-on` (schema updated) | none |
| Imported failures are not native failures | an imported JUnit, CTRF or Allure file with failures produced `NATIVE_TESTS_FAILING` / `NATIVE_COLLECTION_ERRORS` | `IMPORTED_TEST_RESULTS_FAILING` (high: `tests`, `collection_errors`, `sources` by adapter and file name, `provenance` EXTERNAL_UNVERIFIED, `revision` not verified); `NATIVE_*` only for runs Assertiva executed | A consumer that alerted on `NATIVE_TESTS_FAILING` for imported results must also match `IMPORTED_TEST_RESULTS_FAILING` |
| Local checks possibly run by a CI script | (PR #9 only, never released) the whole `LOCAL_CHECK_NOT_OBSERVED_IN_CI` became medium when any CI step was opaque | `LOCAL_CHECK_NOT_OBSERVED_IN_CI` lists NOT_OBSERVED checks at its default severity (`state`, `unlinked_opaque_ci_steps`); checks whose files a CI-reached script names move to `LOCAL_CHECK_POSSIBLY_RUN_BY_CI_SCRIPT` (medium, one entry per check with `state` POSSIBLY_COVERED, `chain`, `matched`, `basis` INFERRED) | Read both codes; 0.10.1 consumers saw such checks in `LOCAL_CHECK_NOT_OBSERVED_IN_CI` at high |

## Detection

- **Projects that declare no runner.** If every test file defines `unittest.TestCase` classes, nothing imports
  pytest, there is no plain test function, no `conftest.py`, and no dependency or tool file names pytest, the project
  is now run with **unittest**, with the arguments recorded as `INFERRED`. Before, it was pytest. To keep pytest,
  declare it: any pytest configuration, a `conftest.py`, pytest in a dependency file, or `[tests] runners =
  ["pytest-native"]` in `.assertiva.toml`.
- **CI parity findings.** A local package script that a CI step reaches through `npm run …` is now covered.
  Repetition is only claimed within one workflow file. A local check is POSSIBLY_COVERED only through a traceable
  link (a script CI reaches names a file the check runs); an opaque CI step without such a link changes nothing.
- **New effectiveness pattern.** A filter over loop cases is `FILTERED_LOOP_ASSERTION` (Python), no longer
  `CONDITIONAL_ASSERTION`.

## CLI

- New: `assertiva audit --fail-on CONDITION` (repeatable), exit 1 when the gate fails. Without it, exit codes are
  unchanged: 0 means the audit completed, 2 refusal or misuse, 3 a read-only violation.
