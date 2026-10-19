# Mutation testing: competitive research for Assertiva (source level)

Date consulted: 2026-10-19. Method: `git clone --depth 1` into separate empty directories under
`scratchpad/research-src/mutation/`. Nothing was installed, built or run from the clones. Cloned content was treated as data.
On Windows the first checkout came out incomplete because of path length. Every clone was repaired with `core.longpaths=true` + `git checkout -- .`, and `git status` was clean before reading.
Labels used below: **CONFIRMED** means read in code, and the `path:line` given is relative to that repo root. **DECLARED** means stated only in docs or the README.
Maintenance signals come from `git log -1` and `gh api .../releases/latest` on 2026-10-19. Star counts were not used.

| Repo | Commit (HEAD) | Last commit | Latest release | License |
|---|---|---|---|---|
| stryker-mutator/stryker-js | c931a93237816901f1e9f48da411170beeb3dfca | 2026-10-10 | v10.0.0 (2026-08-14) | Apache-2.0 |
| stryker-mutator/stryker-net | 66513343265390b3226513b8c2f506f7c353185f | 2026-10-14 | dotnet-stryker@5.0.0 (2026-09-11) | Apache-2.0 |
| stryker-mutator/mutation-testing-elements | 140f211984e8a0c926ec305a550da425f9bb8d69 | 2026-10-19 | v3.9.0 (2026-07-27) | Apache-2.0 |
| hcoles/pitest | f7fe5adfa5fb6e727c12d2403a48f5e4e9dd2fc6 | 2026-10-14 | 1.30.1 (2026-10-14) | Apache-2.0 |
| pitest/pitest-history (OSS incremental plugin) | 6374d597be7971370738c5e8c19d1169295b3eff | 2026-05-29 | none checked | Apache-2.0 |
| STAMP-project/pitest-descartes | 20cbecff6fab5a3bdfcdc048371981cbae973fd5 | 2026-09-29 (dependabot merge) | descartes-1.3.4 (2025-09-19) | LGPL-3.0 |
| boxed/mutmut | e687da39dccc3e94aa165f8f5037fe4b24a3a3be | 2026-10-15 | 3.8.0 (2026-09-12) | BSD-3-Clause |
| sixty-north/cosmic-ray | f6550adf46ead19865285f18db528fcc4e38a3a7 | 2026-10-15 | v8.7.0 (2026-08-09) | MIT |
| sourcefrog/cargo-mutants | 5c06912ca4c9372c03c435d0f55e1e088ce70b8d | 2026-10-08 | v27.1.0 (2026-06-02) | MIT |

The Assertiva code compared against is in the working tree on branch `release/0.7.3`: `assertiva/adapters/mutation.py`, `assertiva/effectiveness.py:159-186`, `assertiva/improve.py:288-355`, `assertiva/models.py:20-66`, `assertiva/report.py:99,108-114`, and the earlier note `research/2026-10-05-mutation-report-formats.md`.

---

## 0. Findings that change Assertiva's behavior (read first)

1. **`killedBy` is usually incomplete, and Assertiva treats it as complete.** By default, StrykerJS, PIT and mutmut stop testing a mutant at its first failing test.
   - StrykerJS: `disableBail` defaults to `false` (`packages/api/schema/stryker-core.json:499-503`). Mocha sets `suite.bail` (`packages/mocha-runner/src/mocha-test-runner.ts:165`) and Vitest sets `bail: 1` (`packages/vitest-runner/src/vitest-test-runner.ts:152`), so the failed list holds one test. Jest passes `reportAllKillers=disableBail` (`packages/jest-runner/src/jest-test-runner.ts:203`), so `killedBy` is `[failedTests[0].id]` (`packages/api/src/test-runner/run-result-helpers.ts:42-44`).
   - PIT: unless `fullMutationMatrix` is set, PIT runs an early-exit group (`pitest/src/main/java/org/pitest/mutationtest/execute/MutationTestWorker.java:194-198`). It writes `<killingTest>` (single) instead of `<killingTests>` (`pitest-entry/.../report/xml/XMLReportListener.java:99-102`).
   - mutmut runs `pytest -x` (`src/mutmut/runners/harness.py:140`) and records no killer at all.

   Consequences:
   - `mutation_contribution()` counts ("kills", "exclusive") are lower bounds, so a test with 0 kills under bail is not evidence of redundancy.
   - `_retirement()` (`assertiva/improve.py:300-302`) can raise a false `RETIRED_TEST_EXCLUSIVE_DETECTION` when the retired test was simply first in the planner's order.
   - The report itself says whether `killedBy` is complete. MTE carries `config.disableBail` because StrykerJS writes `config: this.options` (`packages/core/src/reporters/mutation-test-report-helper.ts:252`). PIT XML uses the `killingTests` versus `killingTest` element. The adapter ignores both.
2. **Killed mutants with no named killer are silently skipped.** `_retirement()` only considers `mutant.killed_by` when it is non-empty (`assertiva/improve.py:301`). Three cases produce detected mutants with no killer:
   - Stryker.NET baseline reuse copies only the status (`src/Stryker.Core/Stryker.Core/MutantFilters/BaselineMutantFilter.cs:103-109`).
   - Timeouts have no killer anywhere.
   - Test ids that cannot be mapped.

   In these cases "retired tests detect no known mutant the remaining tests miss" (`improve.py:306`) is an overclaim, because the passing message is reachable while detected-but-unattributed mutants exist. This is a false-green risk.
3. **Carried-over results look the same as executed results.**
   - StrykerJS incremental mode reuses `status`, `statusReason` and `testsCompleted` from the old report and adds no reuse marker (`packages/core/src/mutants/incremental-differ.ts:186-195`).
   - PIT's history plugin returns stored KILLED, SURVIVED or TIMED_OUT results with no marker (`pitest-history: src/main/java/org/pitest/mutationtest/incremental/IncrementalAnalyser.java:71-101`).
   - Stryker.NET does mark them: `statusReason = "Result based on previous run"` (`BaselineMutantFilter.cs:108`). Its `--since` mode marks unchanged mutants `Ignored` with reason "Mutant not changed compared to target commit" (`MutantFilters/SinceMutantFilter.cs:87-90`).

   Assertiva's evidence ladder (exists → selected → executed → outcome → proven) needs this split, and the adapter currently drops `statusReason` and `config`.
4. **Cosmic Ray claim verified, and the problem is worse than recorded.** In `src/cosmic_ray/tools/xml.py`:
   - Pending items (`:39-41`) and killed items (`:63-76`, no child element) both produce a bare `<testcase>`.
   - `ABNORMAL` (segfault-like) and `SKIPPED` outcomes are counted in the `errors` and `skips` attributes (`:28-33`) but get no child element. Only `EXCEPTION` gets `<error>` (`:67-70`).
   - The root `failures` attribute counts *killed* items (`:30-31`, `is_killed`), while `<failure>` elements mark *survived* and incompetent ones (`:79-83`).
   - Timeouts are recorded as `KILLED` (`src/cosmic_ray/testing.py:70-74`).

   A lossless alternative exists: `cosmic-ray dump` emits JSON lines `[work_item, result|null]`, and `null` means pending (`src/cosmic_ray/cli.py:202-231`).
5. **PIT incremental analysis is no longer in OSS PIT core.** Since 1.23.0 (#1455, `README.md:84`), core ships an `ErroringHistoryFactory` that throws "History has been enabled but no history plugin has been installed" (`pitest-entry/.../incremental/ErroringHistoryFactory.java:15-16`). The OSS implementation lives in `pitest/pitest-history`. The `+GIT` diff-targeting feature is an arcmutate (commercial) feature (DECLARED, from the error message text).
6. **mutmut 3.8 added statuses that its CI export leaves out.**
   - `not checked` (exit code `None`) and `caught by type check` (37) are in `status_by_exit_code` (`src/mutmut/stats.py:15-36`).
   - `save_cicd_stats` writes `total` including them, but writes no separate key for either (`src/mutmut/__main__.py:701-716`).
   - Assertiva's "unaccounted → UNKNOWN" (`assertiva/adapters/mutation.py:97-99`) is therefore correct and necessary. It merges "pending" with "invalid (type-check)", which the per-file `.meta` files would separate (`src/mutmut/mutation/data.py:121-130`).

---

## 1. Deep dives

### 1.1 StrykerJS (+ mutation-testing-elements schema)

**Scope:** JS/TS mutation testing with Mocha, Jest, Vitest, Karma, Jasmine, Cucumber and Tap runners, plus a generic `command` runner. **Non-goals:** detecting equivalent mutants (there is no Equivalent status in the schema) and detecting changes to non-mutated files in incremental mode (DECLARED, `docs/incremental.md:55-63`).

**Architecture (CONFIRMED).** Paths are under `packages/core/src/`.
- `process/1-prepare-executor.ts` → `2-mutant-instrumenter-executor.ts` → `3-dry-run-executor.ts` → `4-mutation-test-executor.ts`.
- Instrumentation uses *mutant schemata*: every mutant is compiled into the file behind `global.activeMutant === id ? mutated : original` (`packages/instrumenter/src/mutant-placers/expression-mutant-placer.ts:184`, `util/syntax-helpers.ts:73`). One build serves all mutants.
- Dry run: the initial run must be green (`3-dry-run-executor.ts:124-128`, throwing `ConfigError('There were failed tests in the initial test run.')`) and must execute some tests (`:100-101`). It records per-test coverage (`coverageAnalysis` defaults to `perTest`, `stryker-core.json:288-291`), hit counts, and timing overhead (`:106`).
- Planning: `mutants/mutant-test-planner.ts:88-138` (`planMutant`):
  - A pre-set status (ignored, or reused by incremental) produces an EarlyResult plan.
  - With coverage, a mutant runs only the tests that cover it (`testFilter: coveredBy`).
  - A static mutant (executed at module load) runs all tests with an environment reload, or becomes `Ignored` when `ignoreStatic` is set (`:114-121`).
  - Without coverage, all tests run.
  - Timeout = `timeoutFactor * netTime + timeoutMS + timeOverheadMS` (`:184`).
  - Hit limit = dry-run hits × 100 (`:37, :185-187`). This catches infinite loops without waiting for the wall clock.
  - Hot-swap happens only for non-static mutants that have a test filter (`:192`).
- Execution pipeline (`4-mutation-test-executor.ts:102-117`): early results, then checkers (for example the TypeScript checker turning a mutant into `CompileError`), then an empty `testFilter` → `NoCoverage` (`:137-147`), then the test-runner pool. Plans that need a reload are sorted last (`:261-272`).
- Run result → status: `run-result-helpers.ts:20-66` (failed tests → Killed and `killedBy`; none → Survived; error → RuntimeError; timeout → Timeout). `reporters/mutation-test-report-helper.ts:130-160` maps these to the schema statuses.
- Workers are child processes. They restart on crash (`test-runner/retry-rejected-decorator.ts`), time out per mutant (`timeout-decorator.ts`), and recycle after N runs (`max-test-runner-reuse-decorator.ts:24-29`).
- Isolation: a sandbox copy of the project (`sandbox/sandbox.ts`) with `node_modules` symlinked (`:77`). `--inPlace` overwrites the user's files and keeps a backup (`:55-60`).
- **Incremental** (`mutants/incremental-differ.ts`):
  - Mutant identity is file + mutator + location + replacement, and test identity is name + file + location (`:40-43`).
  - Old locations are re-mapped through Google diff-match-patch (`:481-...`).
  - Reuse rules (`:394-436`): with no coverage data, always reuse. A previously `Ignored` mutant is re-run. A `Killed` mutant is reused if any old killing test is unchanged ("same"). Any other status is reused unless a new covering test was added.
  - `--force` disables reuse (`:172`).
  - Old mutants outside the mutate scope are carried over (`:206-235`).
  - Known issue: Vitest test ids that change between runs blow up the incremental diff ([stryker-js#6004](https://github.com/stryker-mutator/stryker-js/issues/6004), open since 2026-05-13).

**I/O.** The input is the project plus `stryker.config.*`. The output is the mutation-testing-elements JSON (`schemaVersion: '1.0'`, `config`, `framework`, `testFiles`, `projectRoot`; `mutation-test-report-helper.ts:246-256`), plus HTML and the dashboard. Short example:
```json
{"schemaVersion":"1.0","thresholds":{"high":80,"low":60},"config":{"disableBail":false,"incremental":true},
 "files":{"src/calc.ts":{"language":"typescript","source":"...","mutants":[
  {"id":"3","mutatorName":"EqualityOperator","replacement":"a <= b","location":{"start":{"line":4,"column":10},"end":{"line":4,"column":16}},
   "status":"Killed","killedBy":["7"],"coveredBy":["7","9"],"testsCompleted":1,"static":false}]}},
 "testFiles":{"test/calc.spec.ts":{"tests":[{"id":"7","name":"calc compares"}]}}}
```

**MTE schema (CONFIRMED, `packages/report-schema/src/mutation-testing-report-schema.json`):**
- Required top-level fields are `schemaVersion`, `thresholds` and `files` (`:7`). Each mutant requires `id`, `mutatorName`, `location` and `status` (`:41`).
- Status enum (`:92`): `Killed, Survived, NoCoverage, CompileError, RuntimeError, Timeout, Ignored, Pending`. There is **no Equivalent status**.
- Optional fields: `coveredBy`, `killedBy`, `static` (`:84-86`), `statusReason`, `testsCompleted` ("can differ from coveredBy because of bailing", `:98-100`).
- Test states Killing, Covering and NotCovering are derived in `packages/metrics/src/model/test-model.ts:104-110`.
- Metrics are documented in `docs/mutant-states-and-metrics.md` (Timeout counts as detected; Pending and Ignored are excluded from the score).
- Real-time SSE events `mutant-tested` and `finished` (`docs/implementing-real-time-reporting.md`).
- Schema validation is exercised by the fixtures in `packages/report-schema/testResources/` (strict v1/v2 and missing-field variants).

**Quality evidence.**
- Unit specs exist for the planner, incremental differ and coverage (`packages/core/test/unit/mutants/*.spec.ts`).
- E2E projects cover the specific behaviors: `e2e/test/disable-bail/verify/verify.js:62-68` asserts that a mutant has exactly 2 `killedByTests` when bail is disabled, and there are `incremental`, `incremental-interrupt`, `hit-limit`, `ignore-static` and `in-place` projects.
- None of these were run here.

**Confirmed vs declared.** CONFIRMED: everything above with a `path:line`. DECLARED only: the incremental limitations (`docs/incremental.md:55-63`) and the runner support table for test-location reporting.

**Limitations and not investigated:** mutator internals and per-runner coverage instrumentation were not read; the dashboard reporter was not read.

### 1.2 Stryker.NET

**Scope:** C# via Roslyn, with VsTest and Microsoft Testing Platform runners. It writes the same MTE JSON.

**What it adds over StrykerJS (CONFIRMED):**
- **`--since` diff targeting** (`src/Stryker.Core/Stryker.Core/MutantFilters/SinceMutantFilter.cs`):
  - Unchanged mutants become `Ignored` with "Mutant not changed compared to target commit" (`:87-90`).
  - Mutants in changed files become `Pending` (`:96-101`).
  - Changing a non-C# file in the test project resets everything (`:107-112`).
  - Changed covering tests reset their mutants (`:118-135`).
  - Diff source: `DiffProviders/GitDiffProvider.cs`.
- **Baselines** stored on disk, the Stryker dashboard, Azure File Share or S3 (`Baseline/Providers/*.cs`). Reused results carry `statusReason "Result based on previous run"`, and ambiguous matches become `Pending` with "…was inconclusive" (`MutantFilters/BaselineMutantFilter.cs:103-116`). Only the status is copied, not `killedBy`.
- **A failing baseline test is not fatal.** A mutant covered only by already-failing tests is marked `Survived` with "Only covered by already failing tests." (`CoverageAnalysis/CoverageAnalyser.cs:145-150`).
- A test-host crash becomes `RuntimeError` with an explicit reason (`Mutants/Mutant.cs:44-51`).
- `DisableBail` is an optimisation flag (`src/Stryker.TestRunner.VsTest/VsTestRunner.cs:132`).
- `KilledBy` is serialised from `KillingTests` (`Reporters/Json/SourceFiles/JsonMutant.cs:47`).

**Not investigated:** the Roslyn mutators, the MTP runner and solution handling.

### 1.3 PIT (pitest) + pitest-history

**Scope:** JVM bytecode mutation, run through Maven, Gradle (third party), Ant or the CLI.

**Flow (CONFIRMED):**
- `pitest-entry/.../tooling/MutationCoverage.java:104-173` first scans for mutants without coverage (`:233-245`), so a project with no mutants skips the expensive coverage step. It then does `history.initialize()`, computes coverage limited by history (`:160-163`), and builds analysis units (`:173`).
- Tests for each mutant are ordered by the prioritiser (`build/DefaultTestPrioritiser.java:47-48`, time-weighted).
- Each minion is a child JVM (`execute/MutationTestMinion.java`). The worker hot-swaps the mutated class (`MutationTestWorker.java:145-155`):
  - A failed insert gives `NON_VIABLE` (`:156-161`).
  - No relevant tests inside the minion gives `RUN_ERROR`, with the comment "should have been detected in the outer process" (`:118-127`).
- Timeout = `normal*factor + constant` (`build/PercentAndConstantTimeoutStrategy.java:37-38`). The child exit code maps to `MEMORY_ERROR`, `TIMED_OUT` or `RUN_ERROR` (`DetectionStatus.java:91-99`).

**Statuses (CONFIRMED, `pitest/src/main/java/org/pitest/mutationtest/DetectionStatus.java:22-75`).** `detected=true` covers KILLED, TIMED_OUT, NON_VIABLE, MEMORY_ERROR, RUN_ERROR and **EQUIVALENT**. `detected=false` covers SURVIVED, NOT_STARTED, STARTED and NO_COVERAGE. The XML `detected` attribute uses this flag (`XMLReportListener.java:83-84`), so `detected='true'` is not "killed". Assertiva maps these errors to ERROR (not evaluated), which is stricter, and should stay that way.

**Equivalent mutants.** PIT does not label equivalent mutants; it **filters them out before execution** through interceptors under `pitest-entry/.../build/intercept/`: `equivalent/EquivalentReturnMutationFilter.java` ("bytecode equivalent to the unmutated class", `:58`), `DivisionByMinusOneFilter`, `EqualsPerformanceShortcutFilter`, `NullFinalFieldAssignmentFilter`, plus the `javafeatures/*`, `timeout/Infinite*LoopFilter`, `logging/LoggingCallsFilter` and `staticinitializers` filters. Filtered mutants do not appear in `mutations.xml`, and no OSS code path sets `EQUIVALENT`. A grep found it only in `pitest-html-report/.../ResultComparator.java`.

**Incremental (CONFIRMED, pitest-history `IncrementalAnalyser.java:67-101`).** If the class is unchanged:
- TIMED_OUT is reused (`:78-79`).
- KILLED is reused if a killing test's class is unchanged (`:82-95`).
- SURVIVED is reused if the class's coverage is unchanged (`:98-101`).
- Anything else goes back to NOT_STARTED.
- A reused previous killer is prioritised (`:125-...`).

Change detection is class-level hashing (`CodeHistory`). There is no reuse marker in the output.

**I/O.** `mutations.xml` (the format is covered in the earlier note). `fullMutationMatrix` adds `killingTests`, `succeedingTests` and `coveringTests` (`XMLReportListener.java:99-...`). Example:
```xml
<mutation detected='true' status='KILLED' numberOfTestsRun='2'><sourceFile>Calc.java</sourceFile>
<mutatedClass>a.Calc</mutatedClass><mutatedMethod>max</mutatedMethod><lineNumber>4</lineNumber>
<mutator>org.pitest...ConditionalsBoundaryMutator</mutator><killingTest>a.CalcTest.[engine:junit-jupiter]/...</killingTest></mutation>
```

**Quality evidence.** Not read in depth. `pitest-maven-verification` holds the integration projects. There is 1 open issue page item (count not meaningful).

### 1.4 Descartes (extreme mutation for PIT)

**Scope:** a PIT engine that replaces whole method bodies, with void, null, empty, constant, `this`, argument-propagation, `Optional` and new-instance operators (`src/main/java/eu/stamp_project/descartes/operators/*.java`). It skips short methods and "stop methods" such as getters, setters and logging (`interceptors/SkipShortMethodsFilter.java`, `interceptors/stopmethods/StopMethodMatchers.java`), and honours `@DoNotMutate`.

**Classification (CONFIRMED, `reporting/models/MethodClassification.java:10-50`):**
- `tested`: all extreme mutants detected.
- `pseudo-tested`: none detected.
- `partially-tested`: mixed.
- `not-covered`.
- `error`: an error is present, or not-covered is mixed with anything else.

PIT statuses are mapped in `ExtremeMutationResult.java:28-36`. The output is `methods.json` from the `METHODS` listener (`reporting/MethodTestingListener.java:29,73`), with `methods[]` holding `name, desc, class, package, file, line, classification, tests, mutations`, plus `time` and `mutators`. **License LGPL-3.0:** consuming its JSON is fine, but code must not be copied. Maintenance is slow, with releases yearly-ish and dependabot merges. Paper: Vera-Pérez et al., "Descartes: a PITest engine to detect pseudo-tested methods", ESEC/FSE 2018 demo. The concept comes from Niedermayr et al. 2016, "Will my tests tell me if I break this code?" (recalled, not re-fetched).

### 1.5 mutmut 3.8

**Scope:** Python and pytest only. It requires `fork`, so Windows needs WSL (`README.rst:35-36`).

**Flow (CONFIRMED, `ARCHITECTURE.rst` and `src/mutmut/__main__.py`):**
- Source is copied to `./mutants/` and mutated there with a trampoline that switches functions by `MUTANT_UNDER_TEST`.
- Stats run: which tests reach which function, with durations (`stats.py:146-173`, `record_trampoline_hit`).
- **Clean tests** must pass (`__main__.py:988-991`).
- **Forced-fail control:** every mutant is set to raise, and at least one test must fail. Otherwise it reports "FAILED: Unable to force test failures" (`__main__.py:241-251`). This is a built-in negative control on the harness itself.
- Each mutant runs in a forked process with only the tests that reached the function, sorted by estimated time (`:1014`), using `pytest -x` (`runners/harness.py:140`).
- Timeout is enforced by SIGXCPU from a watchdog (`workers/timeout.py:13-27`).
- Status comes from the exit code (`stats.py:15-36`).

**Incremental/caching (CONFIRMED):**
- Results are stored per function hash in `mutants/<file>.meta` (`exit_code_by_key`, `hash_by_function_name`, `durations_by_key`; `mutation/data.py:121-130`). When a function's hash changes, its mutants are reset to `None` (= not checked) (`__main__.py:200-212`).
- `mutmut-stats.json` stores function hashes, call-dependency edges, a config fingerprint, hashes of watched dependency files (`pyproject.toml`, lock files…, `:404-414`) and `git_commit` (`stats.py:132-146`).
- A config change does a selective reset: test_execution or test_selection changes trigger a full reset, timeout changes reset only timeouts, and type_check changes reset only the flipped results (`__main__.py:624-656`).

This is the most careful cache-invalidation model of the tools examined.

**I/O.** `mutmut-cicd-stats.json` holds aggregate counts only (`:701-716`). Per-mutant results live in `.meta` JSON, an internal format that is not documented as an interface.

**Quality evidence.** `tests/e2e/` covers config, coverage, forkserver, py3.14 and type checking against `e2e_projects/*`. `tests/mutation/` covers mutation, trampoline and pragma handling.

### 1.6 Cosmic Ray 8.7

**Scope:** Python; any test command. Work is distributed locally or over HTTP workers. The session lives in SQLite (`work_db.py`).

**Execution (CONFIRMED):**
- **It mutates the file in the working tree** and restores it afterwards (`mutating.py:98-113`, `use_mutation` / `restore_contents`). Assertiva may only ever orchestrate it inside a disposable copy.
- The test command's exit code decides the outcome: non-zero → KILLED, a timeout → KILLED (output "timeout"), an exception → INCOMPETENT (`testing.py:70-82`).
- `is_killed` means `test_outcome != SURVIVED` (`work_item.py:51-53`), so INCOMPETENT counts as killed there.
- Filters: git diff (`tools/filters/git.py:31`, `git diff --relative -U0 <branch>`), pragma, operators and lines.

**Outputs:** `cr-xml` (lossy, see §0.4), `cr-report`, `cr-html`, and `cosmic-ray dump` JSONL (lossless, with pending items as `null`; `cli.py:202-231`).

### 1.7 cargo-mutants 27.1

**Scope:** Rust via cargo or nextest. Granularity is the whole test command, so there is **no killing-test attribution**.

**Flow (CONFIRMED):**
- The source tree is copied to a temp build dir, respecting `.gitignore` and skipping `target` and `mutants.out*` (`src/copy_tree.rs:95-109`; `src/build_dir.rs:55`). `--in-place` is optional (`:42-48`). The tool refuses to overwrite symlinks or non-regular files (`build_dir.rs:101-114`).
- **The baseline must pass**, otherwise "no mutants were tested" (`src/lab.rs:69-85`).
- Test timeout = `max(minimum, baseline × 5)` unless set explicitly (`src/timeouts.rs:56-66`). A build timeout is optional (`:80-86`).
- Parallel jobs each use their own copied build dir (`lab.rs:94-107`).
- Phases run in order Check → Build → Test (`outcome.rs:35-38`). Status (`outcome.rs:262-288`): build or check failure → Unviable, timeout → Timeout, test failure → CaughtMutant, test pass → MissedMutant.
- Mutant genres: FnValue (replace the body with type-appropriate values such as `Default::default()`, `Ok(Default::default())` or `vec![]`; `src/fnvalue.rs:21-...`), plus BinaryOperator, UnaryOperator, MatchArm, MatchArmGuard and StructField (`src/mutant.rs:20-33`). FnValue is effectively the Descartes "extreme mutation" idea.
- **`--in-diff`** keeps mutants whose span touches changed lines (`src/in_diff.rs:93-157`). It **rejects a diff whose new text does not match the tree** (`check_diff_new_text_matches`, `:159-...`, `MismatchedDiff`), which binds the result to a revision.
- `--iterate` skips mutants listed in `caught.txt`, `previously_caught.txt` or `unviable.txt` (`src/output.rs:26-28,252-275`). This is DECLARED as a heuristic in `book/src/iterate.md:31`.
- Sharding: `src/shard.rs`.

**I/O.** `mutants.out/` contains `outcomes.json`, `mutants.json`, `caught.txt`, `missed.txt`, `timeout.txt`, `unviable.txt`, `log/*.log`, `diff/*.diff` and `lock.json`. A previous directory is rotated to `mutants.out.old` (`output.rs:22-23,111-121`). `outcomes.json` follows the `LabOutcome` struct (`outcome.rs:60-72`): `outcomes[]` (including the **baseline** scenario), the totals `total_mutants, missed, caught, timeout, unviable, success`, `start_time`, `end_time` and `cargo_mutants_version`. Each scenario has `scenario, summary, log_path, diff_path, phase_results[{phase, duration, process_status, argv}]` (`:180-184,320-323`). Mutant fields: `name, package, file, function, span, replacement, genre` (`mutant.rs:342-348`). Example:
```json
{"outcomes":[{"scenario":"Baseline","summary":"Success","phase_results":[{"phase":"Test","duration":3.1,"process_status":"Success","argv":["cargo","test"]}]},
 {"scenario":{"Mutant":{"name":"src/lib.rs:4:5: replace max -> i32 with 0","file":"src/lib.rs","function":{"function_name":"max"},"genre":"FnValue"}},
  "summary":"MissedMutant","log_path":"log/src_lib.rs_line_4.log","diff_path":"diff/src_lib.rs_line_4.diff","phase_results":[...]}],
 "total_mutants":1,"missed":1,"caught":0,"timeout":0,"unviable":0,"success":0,"cargo_mutants_version":"27.1.0"}
```
The nesting of `scenario` and `function` was inferred from the serde derive and not checked against a real file. Check it against `tests/snapshots` before writing an adapter.

**Quality evidence.** There are 275 `#[test]` functions in `src/`, `tests/main.rs` with insta snapshots, and about 50 `testdata/` trees, including `already_failing_tests`, `hang_when_mutated`, `diff0`/`diff1`, `unviable`-producing `typecheck_fails` and `symlink`.

---

## 2. Peripheral projects (from repo metadata via `gh api` on 2026-10-19; not cloned)

- **Stryker4s** (Scala; Apache-2.0; pushed 2026-10-19; v1.1.1 on 2026-07-30). It writes the same MTE JSON, so it is covered by the existing adapter. https://github.com/stryker-mutator/stryker4s
- **Mull** (C/C++ via an LLVM plugin; Apache-2.0; release 0.34.2 on 2026-10-17). It emits mutation-testing-elements JSON through its Elements reporter (DECLARED in the docs, not verified here). That would make it ingestible through the existing MTE path. https://github.com/mull-project/mull
- **Infection** (PHP; BSD-3-Clause; release 0.35.8 on 2026-10-14). It has a JSON log and, per its docs, a Stryker-dashboard/MTE-compatible HTML/JSON report. Not verified. https://github.com/infection/infection
- **Gremlins** (Go; Apache-2.0; v0.6.0 on 2025-12-06, last push 2026-06): slow cadence. **go-mutesting (avito-tech fork)** (MIT; v2.3.1 on 2025-12-26). Report formats were not verified. https://github.com/go-gremlins/gremlins, https://github.com/avito-tech/go-mutesting
- **mutant** (Ruby; license reported as NOASSERTION by GitHub, historically a commercial license for private use; pushed 2026-10-18; v0.16.2). The license makes it a REJECT for bundling, but an "ingest only" path is fine if it emits a usable format (unverified). https://github.com/mbj/mutant
- **Major** (Java, compiler-integrated; by R. Just): `rjust/major` returned 404 on GitHub. It is distributed from mutation-testing.org. Not investigated.
- **Research:**
  - Google's diff-based, operator-history-filtered mutation: Petrović, Ivanković, Fraser, Just, "Practical Mutation Testing at Scale: A view from Google", TSE 2021, https://arxiv.org/abs/2102.11378. Its ideas are to mutate changed lines only, suppress "unproductive" mutants, and pick operators by historical usefulness.
  - Trivial Compiler Equivalence: Papadakis, Jia, Harman, Le Traon, ICSE 2015, https://discovery-pp.ucl.ac.uk/id/eprint/1499169. It detected ~7% equivalent and ~21% duplicate mutants and found about 30% of the equivalent ones. PIT's bytecode-equivalence filter is the same idea.
  - Predictive Mutation Testing: Zhang et al., ISSTA 2016. This is a citation from memory, and the DOI was not verified by search.
  - Pseudo-tested methods: Niedermayr et al. 2016; Vera-Pérez et al., EMSE 2019 (recalled, not re-fetched).

---

## 3. Comparison with Assertiva, by capability

For each capability: what the tools do better, what Assertiva does or only plans, the gap, the decision, the concrete changes to existing modules, and the tests that would prove the improvement.

### C1. Ingesting per-mutant reports (MTE, PIT)
- **Theirs:** MTE carries `statusReason`, `coveredBy`, `testsCompleted`, `static`, and the complete `config` (including `disableBail`, `incremental`, `coverageAnalysis`, `mutate`). PIT XML says whether the matrix is complete through the element name.
- **Assertiva today:** IMPLEMENTED for status, location, operator, `killedBy`, `testFiles` and `duration` (`adapters/mutation.py:39-60,63-88`). `statusReason`, `coveredBy`, `static`, `testsCompleted` and `config` are dropped. `MutantRecord` has no field for them (`models.py:36-46`). Mutation summaries in the report are untyped in `schemas/assurance-report.schema.json`, which has no mutation definition (grep found none).
- **Gap:** the adapter cannot tell whether a run had complete killers, used reuse, or used incremental or since filtering.
- **Decision: INTEGRATE (extend the adapter).**
  - `MutantRecord`: add `status_reason`, `covered_by`, `tests_completed`, `static`.
  - `MutationRun`: add `killers_complete: bool|None`, `reused: int` and `config` facts.
  - MTE: set `killers_complete = config.get("disableBail") is True`; treat an absent `config` as None/unknown.
  - PIT: `killers_complete = True` iff any `<killingTests>` element is present, else False if `<killingTest>` is present.
  - Count `statusReason == "Result based on previous run"` as reused (Stryker.NET), and flag `config.incremental is True` (StrykerJS) as "may contain carried-over results".
  - Add a `$defs/mutationRun` to the schema covering the existing `_mutation_summary` keys plus the new ones.
- **Tests (in `tests/test_mutation.py`):**
  - An MTE fixture with `config.disableBail=false` → `killers_complete is False`; with true → True; without config → None.
  - A PIT fixture with `<killingTests>` → True.
  - A Stryker.NET-style fixture with the reuse reason → `reused == n`.
  - A schema-validation test for the new definition.

### C2. Per-test contribution and retiring tests safely
- **Theirs:** MTE metrics derive Killing, Covering and NotCovering per test (`metrics/src/model/test-model.ts:104-110`). None of the tools turns this into a retirement decision. That part is Assertiva's own territory.
- **Assertiva:** IMPLEMENTED (`effectiveness.py:159-186`, `improve.py:288-306`). It has two soundness gaps (§0.1, §0.2).
- **Decision: BUILD (fix).**
  - In `mutation_contribution`: when any contributing run has `killers_complete is not True`, label the counts "lower bound (first killer only)" and turn "exclusive" into "exclusive in this report; another test may also detect it".
  - In `_retirement`:
    - (a) If `killers_complete is False` and the result is an exclusive hit, return it as **unknown** ("re-run with disableBail / fullMutationMatrix to decide"), not as a failure.
    - (b) Count detected mutants (KILLED or TIMEOUT) whose `killed_by` is empty. If any exist, add an unknown entry instead of the passing message.
  - Add a matching line to `SKILL.md` and `references/TEST_QUALITY.md`: a killer list from a bailing run proves that a test detects a mutant, not that it is the only one that does.
- **Tests:**
  - A bail-mode MTE fixture where tests A and B both detect a mutant but `killedBy=[A]`: retiring A gives UNKNOWN, not FAIL.
  - The same with `disableBail=true` and `killedBy=[A,B]`: retiring A passes.
  - A Killed mutant with empty `killedBy`: the passing message is suppressed.
  - An eval case in `evals/cases/` (for example `EFFECTIVENESS_CANDIDATE_REJECTED.md`) extended with a bail variant.

### C3. Executed vs carried-over vs filtered (evidence ladder)
- **Theirs:** Stryker.NET marks reuse and since-filtering in `statusReason`. StrykerJS and PIT-history do not. cargo-mutants `--iterate` drops previously caught mutants from the run entirely and records them in `previously_caught.txt`. mutmut keeps cached exit codes keyed by function hash.
- **Assertiva:** the ladder is SPECIFIED in SKILL.md, and the M4 statuses are PLANNED (`ROADMAP.md:116`). The adapter has no notion of reuse.
- **Decision: ADAPT-CONCEPT plus INTEGRATE.** Normalise each mutant to `executed_in_this_run: true|false|unknown`:
  - false: Stryker.NET reuse reason, and `Ignored` with the since reason.
  - unknown: StrykerJS when `config.incremental` is true, and any PIT report (history cannot be detected).
  - true: StrykerJS with `incremental` false. Even then, `Ignored` stays not-executed.

  `_mutation_stage` should never print "all N evaluated mutants detected" (`improve.py:351`) when some of them were carried over. It should say "N detected (k carried over from a previous run)" and add an unknown entry.
- **Tests:** fixtures for Stryker.NET baseline reuse and StrykerJS incremental, asserting the wording and that a carried-over Killed never appears among the "executed" counts. HTML report (`report_html.py:1874 _mutation`): show a carried-over column.

### C4. Coverage of more report formats
- **cargo-mutants `outcomes.json`:** INTEGRATE (MIT, active, stable named struct). Mapping: CaughtMutant→KILLED, MissedMutant→SURVIVED, Timeout→TIMEOUT, Unviable→ERROR, Failure→UNKNOWN. The baseline scenario must be `Success`; otherwise BLOCKED. Set `per_mutant=True` and `killed_by=()` with the limitation "test-command granularity: no per-test killers". Add a `_cargo_mutants()` branch keyed on `"cargo_mutants_version" in data and "outcomes" in data` in `load_mutation_report`.
  - Tests: a fixture built from a cargo-mutants snapshot shape (check against `tests/snapshots`); a baseline Failure → error; Unviable is not counted as evaluated.
- **Cosmic Ray:** keep cr-xml REJECTED (claim verified, §0.4). INTEGRATE `cosmic-ray dump` JSONL instead. Mapping: `null`→UNKNOWN (pending); worker `exception`/`abnormal`→ERROR; `skipped`→IGNORED; `no-test`→NO_COVERAGE; test `survived`→SURVIVED; `incompetent`→ERROR; `killed`→KILLED, or TIMEOUT if `output == "timeout"` (`testing.py:74`). Note the limitation "no killing tests; no revision".
  - Tests: a JSONL fixture with each outcome, one pending line, and a cr-xml file still rejected with the explicit message.
- **mutmut:** keep the aggregate stats. Optionally ADAPT reading of `.meta` files (`exit_code_by_key` + `status_by_exit_code`) for per-mutant identity, version-gated because the format is internal. Map 37 "caught by type check" → ERROR and `None` → UNKNOWN. Recommendation: wait until an exported format exists, or pin to mutmut ≥3.8 with a format sniff.
  - Tests: fixture `.meta`; reject unknown keys.
- **Descartes `methods.json`:** INTEGRATE as method-level evidence. `pseudo-tested` and `partially-tested` methods become `FALSE_GREEN`/`WEAK_ORACLE` *candidates* with basis "extreme mutation executed" (CONFIRMED tier), which is distinct from M2's hypothetical pseudo-mutation. LGPL only affects code reuse, not data ingestion.
  - Tests: a fixture with all five classifications; `not-covered` is not a pseudo-tested finding; `error` → unknown.
- **Mull, Infection, Stryker4s:** verify they emit MTE and add a fixture per producer to `tests/test_mutation.py` (`framework.name` differs). No new code is expected.

### C5. Orchestrating native tools (M4, PLANNED)
- **Theirs:**
  - StrykerJS and cargo-mutants work in sandbox or temp copies. Cosmic Ray mutates in place. StrykerJS `--inPlace` overwrites user files.
  - Baseline gating: StrykerJS (`3-dry-run-executor.ts:124-128`), cargo-mutants (`lab.rs:69-85`), mutmut clean tests plus a forced-fail control (`__main__.py:241-251,988-999`).
  - Timeouts: factor × baseline + constant in all of them, with the hit-count limit as a StrykerJS extra.
  - Targeting: StrykerJS `mutate` with line ranges, Stryker.NET `--since`, cargo `--in-diff` with a diff/tree consistency check, Cosmic Ray git filter, PIT `targetClasses` (+ history plugin).
- **Assertiva:** PLANNED (M4). The execution safety rules are SPECIFIED (`docs/EXECUTION_SECURITY.md`, untracked new file).
- **Decision: INTEGRATE (orchestrate, do not re-implement mutation).** Concretely:
  1. Always run the native tool inside Assertiva's disposable copy. Refuse `--inPlace` (StrykerJS) and `--in-place` (cargo-mutants), and run Cosmic Ray only in the copy.
  2. Always request complete killers when the run feeds a retirement decision: `--disableBail` (StrykerJS), `DisableBail` (Stryker.NET), `fullMutationMatrix=true` + XML (PIT). Record the extra cost in the budget decision.
  3. For targeting, pass the changed-line ranges as StrykerJS `mutate` `file:line-line`, use `--since` for Stryker.NET and `--in-diff` for cargo-mutants. Bind the run to the revision (Assertiva computes the diff, and cargo checks it matches the tree).
  4. Disable incremental and baseline reuse by default (`--force`, no `--iterate`, no history) when the result is used as "executed" evidence. Allow it only as an explicitly labelled cost saving.
  5. Adopt mutmut's forced-fail idea as a harness check inside the FAULT_SENSITIVITY pillar: before trusting "survived", prove that the harness can fail.
- **Tests:** benchmark fixtures (synthetic, generic) in each ecosystem. Survived, NoCoverage and Timeout must surface. A run with a red baseline must end BLOCKED, not as mutation evidence. A request for retirement must yield `killers_complete=True`. Record cost (wall time and test runs) per run.

### C6. Equivalent mutants
- **Theirs:** PIT filters likely-equivalent mutants silently before running them (bytecode-equivalence, TCE-like). MTE has no Equivalent status. Stryker docs give guidance only (`docs/equivalent-mutants.md`). Nothing labels a *surviving* mutant as equivalent with evidence.
- **Assertiva:** EQUIVALENT is IMPLEMENTED only when a tool says so (PIT enum). The agent stating "inconclusive" is SPECIFIED by the skill.
- **Decision: ADAPT-CONCEPT.** Have the agent propose `equivalent?` as a **hypothesis** with an explicit argument, kept separate from tool statuses and never counted as detected. Optionally run a TCE-style check (compile original vs mutant and compare the outputs) only in orchestrated runs, as a later M2/M4 item. REJECT auto-labelling, because it would be an unverifiable green.
- **Tests:** an eval case where a surviving mutant is truly equivalent. The agent must mark it as a hypothesis with its reasoning, and the stage must stay non-pass or "inconclusive", never pass.

### C7. Pseudo-tested methods / pseudo-mutation (M2)
- **Theirs:** Descartes (method-level classification) and cargo-mutants FnValue actually execute extreme mutation.
- **Assertiva:** PLANNED ("targeted pseudo-mutation as explicit hypothesis").
- **Decision:** INTEGRATE Descartes output (C4). For other ecosystems, ADAPT the concept: the agent names a method whose body could be replaced by a default value, then either runs it through the native tool (cargo-mutants FnValue, StrykerJS BlockStatement mutator on that line range) or labels it a hypothesis.
- **Tests:** a fixture where a method's body result is never asserted. Expected outcome: pseudo-tested confirmed when the executed evidence is present, and only a hypothesis when no tool ran.

---

## 4. Capability gap matrix

Legend: IMPLEMENTED / PARTIAL / SPECIFIED / PLANNED / UNSUPPORTED / UNKNOWN. Assertiva = engine + skill.

| Capability | StrykerJS | Stryker.NET | PIT (+history plugin) | Descartes | mutmut 3.8 | Cosmic Ray | cargo-mutants | Assertiva |
|---|---|---|---|---|---|---|---|---|
| Generates and executes mutants | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED (via PIT) | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | UNSUPPORTED (by design; M4 PLANNED orchestration) |
| Per-test coverage-based test selection | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED (PIT) | IMPLEMENTED (function reach) | UNSUPPORTED | UNSUPPORTED | n/a |
| Complete killing-test matrix | PARTIAL (opt-in `disableBail`) | PARTIAL (opt-in) | PARTIAL (opt-in `fullMutationMatrix`) | PARTIAL | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | PARTIAL (consumes killers, but cannot tell whether they are complete) |
| Baseline must pass before mutating | IMPLEMENTED | PARTIAL (failing tests excluded) | IMPLEMENTED (DECLARED; not read) | IMPLEMENTED (PIT) | IMPLEMENTED + forced-fail control | PARTIAL (`baseline` command) | IMPLEMENTED | PARTIAL (negative controls in improve; no harness forced-fail) |
| Isolation from user tree | IMPLEMENTED (sandbox; `--inPlace` opt-out) | IMPLEMENTED | IMPLEMENTED (child JVMs, bytecode) | IMPLEMENTED | IMPLEMENTED (`mutants/` copy) | UNSUPPORTED (in-place + restore) | IMPLEMENTED (temp copy; `--in-place` opt) | SPECIFIED (disposable copies) |
| Timeout / infinite-loop handling | IMPLEMENTED (+hit limit) | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED (SIGXCPU) | PARTIAL (timeout = killed) | IMPLEMENTED | n/a (ingests TIMEOUT) |
| Incremental reuse | IMPLEMENTED | IMPLEMENTED (baseline providers) | PARTIAL (OSS plugin only) | via PIT | IMPLEMENTED (function hash + config fingerprint) | UNSUPPORTED (resume of session only) | PARTIAL (`--iterate` heuristic) | PLANNED |
| Marks reused vs executed in output | UNSUPPORTED | IMPLEMENTED (`statusReason`) | UNSUPPORTED | UNSUPPORTED | UNKNOWN (only internal `.meta`) | n/a | PARTIAL (`previously_caught.txt`) | UNSUPPORTED (gap C3) |
| Diff / changed-code targeting | PARTIAL (`mutate` line ranges) | IMPLEMENTED (`--since`) | PARTIAL (`targetClasses`; GIT = commercial) | via PIT | PARTIAL (mutant names / covered lines) | IMPLEMENTED (git filter) | IMPLEMENTED (`--in-diff` with tree check) | PLANNED |
| Equivalent-mutant handling | UNSUPPORTED (docs only) | UNSUPPORTED | PARTIAL (pre-execution filters, unreported) | PARTIAL (stop methods) | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | PARTIAL (keeps tool EQUIVALENT; agent hypothesis SPECIFIED) |
| Pseudo-tested methods | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | IMPLEMENTED | UNSUPPORTED | UNSUPPORTED | PARTIAL (FnValue, no method classification) | PLANNED (M2) |
| Interchange report with source text | IMPLEMENTED (MTE) | IMPLEMENTED (MTE) | UNSUPPORTED (XML, no source) | UNSUPPORTED | UNSUPPORTED | PARTIAL (dump JSONL) | PARTIAL (outcomes.json + diffs) | IMPLEMENTED (checks MTE source matches state) |
| Records the config used in the report | IMPLEMENTED | IMPLEMENTED (DECLARED, same reporter family) | UNSUPPORTED | UNSUPPORTED | PARTIAL (fingerprint in internal stats) | UNSUPPORTED (in DB) | PARTIAL (argv per phase) | UNSUPPORTED (drops `config`) |
| Ingests this tool's output | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | UNSUPPORTED | PARTIAL (aggregate) | UNSUPPORTED (by decision) | UNSUPPORTED | (row = Assertiva's status per tool) |
| Retirement safety from per-test detection | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | PARTIAL (implemented; unsound under bail/reuse, see §0.1-0.2) |

---

## 5. What each tool does better than Assertiva, how, and how we would prove we matched it

- **StrykerJS:** it executes, and records how it executed (`config`, `testsCompleted`, `static`). Assertiva throws this away.
  - *Match:* read `config.disableBail` / `incremental` and the per-mutant fields (C1/C3).
  - *Proof:* fixture tests in `tests/test_mutation.py`, plus an `improve` test where a bail report no longer produces a false retirement failure.
- **Stryker.NET:** it is honest about carry-over ("Result based on previous run") and about diff scoping ("Mutant not changed…").
  - *Match:* the `executed_in_this_run` normalisation.
  - *Proof:* a fixture with reuse reasons; the `_mutation_stage` wording and counts exclude carried-over results.
- **PIT:** the complete-killer mode is visible in the XML element, and it filters equivalent mutants before running them.
  - *Match:* the `killers_complete` sniff; keep error statuses not-detected even though PIT says `detected='true'`.
  - *Proof:* PIT `fullMutationMatrix` and default fixtures, plus a test asserting that `NON_VIABLE` never counts as detected.
- **Descartes:** method-level pseudo-tested classification from executed extreme mutants.
  - *Match:* ingest `methods.json` → CONFIRMED FALSE_GREEN/WEAK_ORACLE candidates.
  - *Proof:* a fixture with each classification, and an eval case where the agent separates a confirmed pseudo-tested method from a hypothesis.
- **mutmut:** forced-fail and clean-run controls on the harness itself, and the most precise cache invalidation (function hash, deps, config groups).
  - *Match:* add a harness forced-fail check to FAULT_SENSITIVITY in M4 orchestration, and label any reused verdict.
  - *Proof:* a benchmark project where the harness swallows failures. Assertiva must report BLOCKED, not "all mutants survived" or "all killed".
- **Cosmic Ray:** nothing to match in evidence quality. Its dump format is the safe input.
  - *Proof:* a JSONL fixture where pending lines yield UNKNOWN, while cr-xml stays rejected with the stated reason.
- **cargo-mutants:** baseline-gated, copy-isolated runs with per-phase argv, durations, logs and diffs, and a diff-versus-tree consistency check.
  - *Match:* the `outcomes.json` adapter (baseline must be Success), and for orchestration, a revision-bound diff check before targeting.
  - *Proof:* a fixture with a baseline Failure → BLOCKED, Unviable not evaluated, and missed mutants listed with their diff paths.

---

## 6. Effort, uncertainties, not done

- **Approximate spend:** about 120k tokens and about 1 hour of wall time, well under the 300k budget.
- **Not done:**
  - Did not read the Stryker mutator implementations, the PIT mutators or the Gradle plugin, or the Stryker.NET Roslyn orchestration.
  - Did not verify that Mull, Infection or mutant emit MTE (marked DECLARED/unverified).
  - Did not open a real cargo-mutants `outcomes.json` snapshot to confirm the serde nesting of `scenario`.
  - Did not fetch the PMT and pseudo-tested papers. Those citations are from memory and are marked as such.
  - Did not run anything, by rule, so no runtime claim here is observed behavior.
- **Uncertainties:**
  - Whether Stryker.NET's JSON reporter writes `config` the way StrykerJS does was not confirmed in Stryker.NET code.
  - PIT's baseline-must-pass behavior was not traced in code.
  - mutmut `.meta` is an internal format and may change without notice.
