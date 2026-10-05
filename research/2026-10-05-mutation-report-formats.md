# Mutation Report Formats — 2026-10-05

Dated research behind `assertiva/adapters/mutation.py`. Formats change; re-check sources before relying on details.

## mutation-testing-elements JSON (Stryker family)

Source: `stryker-mutator/mutation-testing-elements`, `packages/report-schema/src/mutation-testing-report-schema.json` (master, fetched 2026-10-05).

- Top level requires `schemaVersion`, `thresholds`, `files`; optional `framework` (`name`, `version`), `testFiles`, `projectRoot`, `performance`, `system`, `config`.
- `files[path]` requires `language`, `source` (full original source), `mutants`.
- Mutant requires `id`, `mutatorName`, `location` (`start`/`end` with `line`/`column`), `status`; optional `replacement`, `description`, `killedBy`, `coveredBy`, `duration` (ms), `statusReason`, `testsCompleted`, `static`.
- Status enum: `Killed`, `Survived`, `NoCoverage`, `CompileError`, `RuntimeError`, `Timeout`, `Ignored`, `Pending`.
- Produced by StrykerJS, Stryker.NET and Stryker4s JSON reporters and by other tools that target the schema.
- Because the report embeds each file's `source`, Assertiva can check that a report belongs to the measured state.

## PIT `mutations.xml`

Sources: `hcoles/pitest`, `DetectionStatus.java` and `XMLReportListener.java` (master, fetched 2026-10-05).

- Root `<mutations>` (optional `partial`); each `<mutation detected=… status=… numberOfTestsRun=…>` with `sourceFile`, `mutatedClass`, `mutatedMethod`, `methodDescription`, `lineNumber`, `mutator`, `indexes`, `blocks`, `killingTest` (or `killingTests`/`succeedingTests`/`coveringTests` with full matrix, `|`-separated), `description`.
- Status: `KILLED`, `SURVIVED`, `TIMED_OUT`, `NON_VIABLE`, `MEMORY_ERROR`, `NOT_STARTED`, `STARTED`, `RUN_ERROR`, `NO_COVERAGE`, `EQUIVALENT`.
- No source text or revision: a PIT report cannot be tied to a revision by content alone.

## mutmut 3

Source: `boxed/mutmut`, `src/mutmut/__main__.py` and `stats.py` (main, fetched 2026-10-05).

- `mutmut export-cicd-stats` writes `mutants/mutmut-cicd-stats.json` with aggregate counts: `killed`, `survived`, `total`, `no_tests`, `skipped`, `suspicious`, `timeout`, `check_was_interrupted_by_user`, `segfault`.
- Per-mutant results live in mutmut's own working state and CLI output (`mutmut results`), not a documented exchange format.
- Assertiva ingests the stats file as aggregate-only evidence.

## Cosmic Ray

Source: `sixty-north/cosmic-ray`, `tools/xml.py`, `work_item.py` (master, fetched 2026-10-05).

- Results live in a session SQLite database; `cr-xml` renders a JUnit-like `testsuite`.
- In `cr-xml`, survived **and** incompetent mutants become `<failure>`, worker exceptions become `<error>`, and both killed and *pending* work items have no child element.
- Decision: not supported. Pending and killed mutants are indistinguishable in that output, which would be a false green. A future adapter should read the session database or `cr-report` instead.

## Normalization used

| Normalized | mutation-testing-elements | PIT | mutmut stats |
| --- | --- | --- | --- |
| KILLED | Killed | KILLED | killed |
| SURVIVED | Survived | SURVIVED | survived |
| NO_COVERAGE | NoCoverage | NO_COVERAGE | no_tests |
| TIMEOUT | Timeout | TIMED_OUT | timeout |
| ERROR | CompileError, RuntimeError | NON_VIABLE, MEMORY_ERROR, RUN_ERROR | segfault |
| IGNORED | Ignored | — | skipped |
| EQUIVALENT | — | EQUIVALENT | — |
| UNKNOWN | Pending, any other value | NOT_STARTED, STARTED, any other value | suspicious, interrupted, unaccounted |

The native status is always preserved next to the normalized one.
