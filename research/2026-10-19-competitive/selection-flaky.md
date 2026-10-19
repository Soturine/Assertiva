# Competitive research: regression test selection, prioritization, change impact, flaky tests, failure intelligence

Date of research: 2026-10-19. Researcher: agent, read-only on clones (nothing installed, built or run).
Clone root: `<scratchpad>\research-src\selection\`

Legend: **CONFIRMED-IN-CODE** = read in the cloned source at the cited path:line. **DECLARED-ONLY** = README/docs/paper says so, not verified in code. **OBSERVABLE** (closed tools) = documented user-visible behaviour; **HYPOTHESIS** = our inference about how it is implemented.

## 0. Sources examined

| Project | URL | SHA (HEAD) | Commit date | License | How fetched |
|---|---|---|---|---|---|
| pytest-testmon | github.com/tarpas/pytest-testmon | dccc58d2ed8edec98096ff1974acb7c07d3e3482 | 2025-12-01 | MIT | git clone --depth 1 |
| Ekstazi | github.com/gliga/ekstazi | b6ee1f2bed42c6bb343e74759078dbd6458f4f5a | 2026-01-30 | Apache-2.0 | clone (checkout partial on Windows; read via `git cat-file`) |
| STARTS | github.com/TestingResearchIllinois/starts | a01412c4aae5dd472101fd00cf7aad2fc584f4ed | not recorded (tarball) | "STARTS Release License" (University of Illinois/NCSA-style permissive, MIT-like text) | codeload tarball at SHA (clone failed: index-pack) |
| gradle/test-retry-gradle-plugin | github.com/gradle/test-retry-gradle-plugin | 103e513ff84de7ba12aa47f76b4b76ab66626da6 | not recorded (tarball) | Apache-2.0 | tarball |
| CloudBees Smart Tests CLI (ex-Launchable) | github.com/launchableinc/cli | b5ace7f37c59a33e3a09e187a6a9d96523d9e091 | 2026-10-19 | Apache-2.0 | clone. NOTE: repo contains a `CLAUDE.md`; treated as untrusted data and not followed |
| iDFlakies | github.com/idflakies/iDFlakies | d9474c664fb3f1215763dc9ac7336c81520f20dd | 2026-10-04 | no LICENSE file found in tree (license UNKNOWN) | clone, read via `git cat-file` (long paths) |
| DeFlaker | github.com/gmu-swe/deflaker | cbe96bf0c4702de134015f8080fe025a55cd998f | 2019-12-31 | no LICENSE file in tree (UNKNOWN) | clone, `git cat-file` |
| FlakeFlagger | github.com/AlshammariA/FlakeFlagger | 2fcbafc4713abbcc452bee07aa9681c7c8ccb707 | 2022-04-08 | BSD-3-Clause | clone |
| NonDex | github.com/TestingResearchIllinois/NonDex | f1f407ce3e026f597567e7d96ee08cb08875690f | not recorded (tarball) | MIT | tarball |
| pytest-rerunfailures | github.com/pytest-dev/pytest-rerunfailures | 01fd226bd533ecd7f6aabe7c155c4ca7bcd8598c | not recorded (tarball) | MPL-2.0 | tarball |
| pytest-randomly | github.com/pytest-dev/pytest-randomly | 99dc4cf0026b3cb65a240fb98680f01d920a99b8 | 2026-10-16 | MIT | clone |
| pytest-flakefinder | github.com/dropbox/pytest-flakefinder | f6fb30fac91d6e85b6a712cf2a1266654a6c14e7 | 2022-10-26 | Apache-2.0 | clone |
| target-determinator | github.com/bazel-contrib/target-determinator | d4b6125546979713431e63b5c3e65810fa989446 | not recorded (tarball) | Apache-2.0 | tarball |

Documentary sources (fetched this session): testmon.org/blog/determining-affected-tests; docs.develocity.ai/predictive-test-selection; docs.develocity.ai/flaky-test-detection; docs.gradle.com/develocity/2026.2/guides/flaky-test-detection-guide (via search); learn.microsoft.com/en-us/azure/devops/pipelines/test/test-impact-analysis; nx.dev/docs/features/ci-features/affected; engineering.fb.com/2020/12/10/developer-tools/probabilistic-flakiness; mir.cs.illinois.edu/~marinov/publications/LegunsenETAL16StaticRTS.pdf (via search summary); jonbell.net/preprint/icse21-flakeflagger.pdf (referenced from README, not fetched); mir.cs.illinois.edu/winglam/publications/2019/LamETAL19iDFlakies.pdf (referenced, not fetched).

---

## 1. Deep dives

### 1.1 pytest-testmon (most relevant: Python, dynamic, per-test)

- **Maintenance (observed):** last commit 2025-12-01; single-maintainer project with a commercial cloud (`--tmnet`, testmon.net). Only one test file in tree (`tests/test_process_code.py`, 58 tests, 499 lines) — the plugin/DB/selection layers have no in-repo tests at this SHA.
- **Scope:** select and re-run only pytest tests affected by changes since the last recorded run in a local `.testmondata` SQLite file. Non-goals: cross-revision base comparison (it compares against *last recorded state*, not a git base), non-Python dependencies, safety claims.

**Architecture / flow (CONFIRMED-IN-CODE):**
1. *Collection:* a coverage.py `Coverage` object is started with `include=[rootdir/*]` and stdlib paths omitted (`testmon/testmon_core.py:487-525`). Each test switches the coverage *context* to its node id (`:527-537`). Coverage is flushed every 250 tests (`TEST_BATCH_SIZE`, `:43`, `:542-581`). Per context, `nodes_files_lines[test][file] = {lines}` (`:583-605`); a test with no recorded line in its own file gets a synthetic dependency on line 1 of its home file (`:602-604`).
2. *Fingerprint:* each Python file is parsed with `ast`; `Module.dump_and_block` (`testmon/process_code.py:134-188`) renders the AST like `ast.dump`, replacing every function body (and the module body) by a placeholder and emitting a `Block(start,end,code)` per body. A test's fingerprint for a file = CRC32 (signed 32-bit, `:17-19, :34-39`) of every block whose line range contains a covered line (`create_fingerprint`, `:291-306`). Non-`.py` files become one whole-file block (`:207-208`). Syntax errors yield no blocks (`:203-206`).
3. *Change detection:* file SHA = git blob SHA, taken from `git ls-files --stage -m` when unmodified, else computed from bytes (`process_code.py:87-99, :235-272`). Files whose fsha is unknown to the DB are re-blocked (`testmon_core.py:346-358`).
4. *Selection:* `db.determine_tests` (`testmon/db.py:496-559`) joins stored fingerprints against current method checksums; a test is affected iff some stored checksum set is **not a subset** of the file's current checksums (`process_code.py:280-283`). Previously failing tests are always re-selected (`pytest_testmon.py:518-528`). Selected tests are sorted by historical average duration of module/class/test (`pytest_testmon.py:497-505, :558`).
5. *Environment:* environment row = (name, installed packages minus patch versions, Python version) (`db.py:343-351`, `common.py:76-99`). If packages or Python changed, the old environment row is deleted and replaced (`db.py:647-711`), which cascades away all test executions → everything re-runs. `--testmon-env` is an expression **`eval`-ed** with `os`, `sys`, `hashlib` in scope (`testmon_core.py:626-639`).
6. *Auto-disable:* selection is turned off when `-k`, `-m`, `--lf` or explicit node ids are used (`configure.py:65-79`); collection is off under a debugger or foreign coverage (`configure.py:43-62`); branch coverage with pytest-cov raises (`testmon_core.py:514-518`).

**I/O.** Input: working tree + `.testmondata`. Storage tables: `environment`, `test_execution(test_name, duration, failed, forced)`, `file_fp(filename, method_checksums BLOB, mtime, fsha)`, `test_execution_file_fp`, `suite_execution_file_fsha` (`db.py:343-409`). Output: pytest deselection plus header line "changed files: …, unchanged files: N" and "testmon savings" summary (`pytest_testmon.py:321-340, :567-600`).

**Safety assumptions / what it misses (CONFIRMED by construction + DECLARED in blog):**
- Only what coverage.py traces in `rootdir`: data files, JSON/YAML config, templates without a coverage plugin, env vars, subprocess code (unless coverage subprocess is configured), and dependencies outside rootdir are invisible. Blog: reliability "pretty much the same as limits of coverage.py"; assumption that unexecuted code cannot influence the outcome (testmon.org blog).
- A change to a block *not executed* by a test does not select it, e.g. adding a new branch target or monkeypatch-reachable function, class attribute defaults inside class body are part of module block (so caught), but decorators applied at import are in module block (caught).
- New tests are always run (no fingerprint) via `sync_db_fs_tests` (`testmon_core.py:321-344`).
- Package/Python changes → full re-run (safe).
- No notion of revision: DB reflects "last run", so two branches sharing one `.testmondata` can mislead; Assertiva's revision-scoped graph is stricter here.

**Quality evidence:** unit tests cover only AST blocking/fingerprinting. No published miss-rate benchmark found. The blog provides reasoning, not measurements.

**Uncertainties / not investigated:** tmnet remote protocol (`--tmnet`, xmlrpc), xdist worker handling details.

### 1.2 Ekstazi (Java, dynamic, file/class-level)

- **Maintenance:** last commit 2026-01-30 (Java 21 support branch exists). Apache-2.0. Research tool from Gligoric/Eloussi/Marinov, ISSTA 2015 ("Practical Regression Test Selection with Dynamic File Dependencies").
- **Architecture (CONFIRMED-IN-CODE, via `git cat-file`, paths under `org.ekstazi.core/src/main/java/org/ekstazi/`):** Java agent instruments classes (`agent/EkstaziAgent.java`, `instrument/*`) and calls `monitor/CoverageMonitor.t(...)` to record every class/URL a *test class* touches, including classes touched via reflection (`monitor/ReflectionMonitor.java:49-51`). Dependencies are stored per test class as text lines `url _ hash` (`data/TxtStorer.java:46`). Hash = CRC32 by default (`Config.java:156`) of bytecode with debug info stripped (`hash/BytecodeCleaner.java:37-41`, "No need to visit sources as they do not change semantic" `:223-224`; `Config.java:160` `HASH_WITHOUT_DEBUGINFO=true`). Optional NIO file tracking (`dependencies.nio`, **off by default**, `Config.java:142`).
- **Selection rule:** a test is affected if it has no data, empty data, or any recorded URL's current hash differs (`check/AbstractCheck.java:49-50, :68-72`) — safe default for missing data.
- **Misses (DECLARED/inferred):** non-class resources unless NIO tracking is on; environment/JVM flags; anything outside the JVM.
- **Published numbers:** ISSTA 2015 reports large time savings vs RetestAll at class granularity (figures commonly quoted as ~32% mean end-to-end time saved; *recalled, NOT re-verified this session*). Legunsen et al. FSE 2016 used Ekstazi as the dynamic baseline (985 revisions, 22 projects).

### 1.3 STARTS (Java, static, class-level)

- **License:** STARTS Release License (permissive, MIT-like). Maintenance: tarball HEAD; commit date not recorded.
- **Architecture (CONFIRMED-IN-CODE):** builds a class dependency graph with `jdeps` (`helpers/RTSUtil.java:79-89`), computes reflexive-transitive closure per test (`helpers/Loadables.java:93`), stores `deps.zlc`: per dependency URL its cleaned-bytecode checksum and the tests that reach it (`helpers/ZLCHelper.java:96-152`).
- **Selection:** `getChangedData` (`ZLCHelper.java:155-232`) recomputes each stored checksum; a mismatch marks its tests affected; affected = all tests − non-affected (`RTSUtil.java:69-77`) so new tests run. A `file:*` "star" line lists tests that must run whenever **anything** changed (`ZLCHelper.java:171-176, :215-218`) — an explicit "unknown dependency" escape hatch, conceptually close to Assertiva's UNKNOWN_RELATION.
- **Safety gaps (CONFIRMED):** dependencies whose class resource is not found are silently skipped (`ZLCHelper.java:116-118`); jar/third-party deps skipped unless `useThirdParty=true` (default false, `jdeps/BaseMojo.java:53`; `ZLCHelper.java:120-123`); checksum `-1` (deleted) ignored (`:208-212`). Reflection not modelled.
- **Published numbers:** Legunsen et al. FSE 2016: class-level static RTS comparable to Ekstazi but "sometimes unsafe"; method-level static performs poorly. Follow-up (Shi/Hadzi-Tanovic et al., reflection-aware static RTS in STARTS, 1173 versions/24 projects): reflection was the only observed cause of unsafety; purely static safe variants cost precision (end-to-end at best 85.8% of RetestAll vs 69.1% for a dynamic-hybrid). Source: mir.cs.illinois.edu static RTS paper + cps-vo/par.nsf.gov abstracts.

### 1.4 Gradle Develocity: Predictive Test Selection, flaky detection, Test Retry plugin

**Test Retry plugin (open, Apache-2.0, CONFIRMED-IN-CODE):**
- Loop in `internal/executer/RetryTestExecuter.java:114-140`: run; if no failures → stop; if `retryCount>0` and nothing was filtered and `failOnPassedAfterRetry=false`, the task ignores failures (passes); otherwise re-run **only failed tests** (`createRetrying(... result.failedTests ...)`) until `maxRetries`.
- `RetryTestResultProcessor.java:266-295`: failures in classes not matching the retry filter set `hasRetryFilteredFailures` (build still fails); retry stops when failed count ≥ `maxFailures` (mass failure is treated as "not flakiness"), on last retry, or when some failed test could not be re-selected (`nonRetriedTests` → `IllegalStateException` asking for a bug report, `RetryTestExecuter.java:147`).
- All attempt results are forwarded to Gradle's result processor, so the first failure stays in the report (the build scan shows FAILED then PASSED = FLAKY).
- Class-level lifecycle failures handled specially (`RetryTestResultProcessor.java:127-134`).

**Flaky detection (closed, OBSERVABLE from docs):** a test is FLAKY if it fails and passes within one task execution (retry), and **cross-build flaky** (since 2023.4) when different outcomes are observed *for the same task/goal inputs* across builds, independent of build status. Each Build Scan keeps output of all failed executions plus the first successful one. No clustering documented.
- HYPOTHESIS: "same inputs" = the Gradle task input fingerprint (build-cache key), which is much stronger than a git SHA + OS label: it covers classpath, JVM args, system properties, test files.

**Predictive Test Selection (closed, OBSERVABLE):** ML model trained on "millions of test executions" from partners + continuous learning from your build scans; features named in docs: which code changes affect tests in the module, test sensitivity to changes, nature of recent changes, flakiness. Profiles Conservative/Standard/Fast. Always selected: recently new/changed/failed/flaky tests, tests skipped for the same inputs, tests explicitly filtered on CLI. Requires 14 days history and ≥50 executions; otherwise all tests run. **Simulator** replays real build scans and reports "% test failures predicted", savings, avoidable/unavoidable tests, and asks to filter flaky/infra failures out of the accuracy estimate. Only number: "calibrated to catch over 99% of non-flaky test task/goal failures" (no methodology). Docs explicitly recommend running the rest nightly/pre-release.

### 1.5 CloudBees Smart Tests / Launchable CLI (open CLI, closed service)

- **CONFIRMED-IN-CODE (client only):** `smart_tests/commands/subset.py` sends the candidate test list to the SaaS and receives `subset`/`rest` (`:107-151`). Options `--target` (%), `--time`, `--confidence` (%), `--ignore-flaky-tests-above`, `--prioritize-tests-failed-within-hours`, `--ignore-new-tests`, observation mode (`:185-258, :364-392`). `FallbackMode` RUN_ALL (default) / STOP / RANDOM_SAMPLE when the service fails or the model is untrained (`:101-104, :295-310, :747-801`). `detect_flakes.py` simply asks the server `GET detect-flake` with LOW/MEDIUM/HIGH threshold. `record commit` runs a bundled Java jar to collect git commits (`record/commit.py:24, :93-113`).
- **DECLARED/HYPOTHESIS:** model is server-side ML over commit diffs, test history and failures; no local safety reasoning; all intelligence requires sending commit metadata and test results to a third party.
- Note the honest local default: unavailable service → run everything; random-sample is an explicit opt-in (a sampling fallback is a non-safety choice clearly labeled).

### 1.6 iDFlakies (Java, order-dependent vs non-order-dependent flakiness)

- **License:** no LICENSE file found (UNKNOWN). Active (2026-10-04).
- **CONFIRMED-IN-CODE** (`idflakies-core/src/main/java/edu/illinois/cs/dt/tools/detection/`):
  - Detectors re-run the whole suite in orders: original, reverse, random class/method, "smart shuffle", Tuscan (`detectors/*.java`); default 20 rounds, original order must pass first (README:64-66).
  - **NOD classifier** (`classifiers/NonorderClassifier.java:26-35`): for each test, MD5 of the *ordered prefix of tests that ran before it*; if the same prefix yields a different result → non-order-dependent flaky.
  - **OD classifier** (`classifiers/DependentClassifier.java:41-58`): tests with >1 distinct result across orders and not NOD → order-dependent; can ignore everything after the first failure in a run as unreliable.
  - **ConfirmationFilter** (`filters/ConfirmationFilter.java:67-107`): re-runs the passing and failing orders to confirm; if confirmation fails the test is downgraded to NOD.
- **Published (DECLARED, paper ICST 2019, not re-verified):** 422 flaky tests in 82 of 683 projects, roughly half OD and half NOD.

### 1.7 DeFlaker (Java, flaky verdict without reruns via diff coverage)

- **CONFIRMED-IN-CODE** (`maven-plugin/.../DeflakerReportingMojo.java`): computes changed lines per class from the VCS diff, collects coverage *only of changed code* (diff coverage agent `org/deflaker/runtime/DiffCovAgent.java`). Verdict: a failing test whose coverage set **does not include any changed code** is reported "FLAKY" (`:477-487`). Also reports flaky if it failed then passed when rerun in the same JVM or a fresh JVM (`:446-475`). Non-Java changed files are "poison": warned that "non-java files are not tracked … they may have been impacted by this change!" (`:372-374`).
- **Security/quality red flags:** hard-coded remote MySQL credentials for the research DB in source (`:239`, not reproduced here); deserializes the diff file with Java object serialization (`:253-255`). Last commit 2019. **REJECT** for any integration.
- **Published (DECLARED, ICSE 2018):** high recall with low false-positive rate on 26 projects (commonly cited ~95.5% recall, ~1.5% FPR; *not re-verified*).
- **Key concept for Assertiva:** "the failure cannot be caused by this change because the test never executed changed code" is evidence of *not-a-regression*, never of flakiness alone (it may be an environment or pre-existing failure). Assertiva's impact graph already holds the "proven path" data to compute the static analogue.

### 1.8 FlakeFlagger (prediction without reruns)

- BSD-3-Clause; last commit 2022. Ground truth from rerunning suites **10,000 times** (README). Features (CONFIRMED in `flakiness-predicter/input_data/FlakeFlaggerFeaturesTypes.csv`): static smells (assertion-roulette, conditional-test-logic, eager-test, fire-and-forget, indirect-testing, mystery-guest, resource-optimism, test-run-war, numAsserts) and dynamic (covered lines, execution time, project lines/classes covered, h-index of modifications per covered line over windows 5…10000, third-party libs). Random Forest etc. with SMOTE and information-gain filtering (`flakeflagger_predicter.py:115-122`).
- Ships pickled `.sav` models — code-execution on load; **REJECT** integration. The feature list is the reusable idea; Assertiva's `effectiveness.py` already detects some smells (sleep-based synchronization).

### 1.9 NonDex (Java, seeded nondeterminism injection)

- MIT. CONFIRMED-IN-CODE: replaces JDK classes with versions whose underspecified behaviour (HashMap/HashSet iteration, `getDeclaredMethods` order, etc.) is shuffled with a seeded RNG (`nondex-common/.../NonDex.java:62, :78-110`). Config: mode FULL/ONE, seed default 933178, 3 runs, 1 run without shuffling, filter regex, and **`nondexStart`/`nondexEnd`** invocation-index window (`ConfigurationDefaults.java:41-75`) used to bisect to the exact nondeterministic call site.
- Concept for Assertiva M6: seed + bisection window = targeted reproduction with a minimal deterministic witness.

### 1.10 pytest-rerunfailures / pytest-randomly / pytest-flakefinder

- **pytest-rerunfailures** (MPL-2.0; file-level copyleft — fine to *invoke*, do not copy code into Apache sources). CONFIRMED: `--reruns`, `--reruns-delay` with backoff, `--only-rerun`/`--rerun-except` regexes over exception chain (`src/pytest_rerunfailures.py:654-710`), `--fail-on-flaky` (exit 7), `--max-suite-reruns` (suite-wide budget coordinated across xdist via a socket-based StatusDB, `:852-1046, :1193-1196`), attempts reported with outcome `"rerun"` and tracebacks optionally shown (`:1306-1339, :1370-1421`).
- **pytest-randomly** (MIT). CONFIRMED: seed from `-p randomly -p seed`/`last` cached in pytest cache (`__init__.py:119-140`); per-test reseed of `random`, faker, model_bakery, numpy and entry-point seeders with `seed + crc32(nodeid)` (±1 for setup/teardown) (`:156-205`) → a test's randomness is reproducible independent of order; shuffles modules, classes, functions by `crc32(seed::name)` (`:222-256`). Does **not** set `PYTHONHASHSEED` (no occurrence).
- **pytest-flakefinder** (Apache-2.0). CONFIRMED: duplicates each collected item N times (default 50, optional minutes cap) (`pytest_flakefinder.py:8-9, :75-90`). Simple, deterministic repeat-in-same-process.

### 1.11 target-determinator (Bazel)

- Apache-2.0. CONFIRMED: hashes every configured target at "before" and "after" revisions in separate worktrees: source files by content, rules by attributes + configured inputs, generated files by generating rule (`pkg/hash_cache.go:493-552`); differences reported per label with an explanation (`WalkDiffs`, `:227`). Non-existent files hash to empty (Bazel semantics, `:510-516`). `--enforce-clean` refuses unclean trees; `before-query-error-behavior` default "ignore-and-build-all" (README). README explicitly warns that cached "before" results computed under different env vars may produce spurious differences; recommends `--nocache_results` for same-environment comparison.
- Concept: **compare both revisions under the same environment, in clean worktrees**, and make "cannot compute before" fall back to "build all".

---

## 2. Peripheral (brief)

- **Jest `--findRelatedTests` / `--onlyChanged` / `--changedSince`** (jestjs.io/docs/cli): static module graph from jest-haste-map (require/import extraction), changed files from git/hg. Misses dynamic requires, data files and config not in the module graph. MIT. Not cloned (DECLARED-ONLY).
- **Vitest `related` / `--changed`** (vitest.dev/guide/cli): Vite module graph; `forceRerunTriggers` (default includes package.json and vite/vitest config) reruns everything — same idea as Assertiva's CONFIGURATION widening. MIT. DECLARED-ONLY.
- **Nx affected** (nx.dev/docs/features/ci-features/affected): git changed files → project graph → dependents. Lockfile change affects **all** projects by default; `projectsAffectedByDependencyUpdates: "auto"` diffs base vs head lockfile and marks only projects whose resolved deps changed. Task-based mode selects a task when a change reaches one of its declared inputs; custom hashers always selected. DECLARED-ONLY.
- **Microsoft Test Impact Analysis** (learn.microsoft.com/…/test-impact-analysis): managed code only; dynamic per-test file dependency maps; always includes impacted, previously failing and new tests; **unknown file type → run all tests**; periodic full runs; `TIA_IncludePathFilters` to ignore file types; **user-supplied dependency map XML** (`TIA.UserMapFile`) to extend to other languages/multi-machine; recommended validation = run impacted (T1) then all (T2) and compare failures. Unsupported: data-driven tests, multi-machine, .NET Core. DECLARED-ONLY (closed).
- **SeaLights** (sealights.io, closed): language agents record per-test code footprints in a SaaS; "Test Impact Analytics" selects tests by footprint, "Test Gap Analysis" reports modified code untested by any test stage. OBSERVABLE from marketing docs only; no code, no published miss rates found. HYPOTHESIS: coverage-based like TIA/testmon, with cross-stage aggregation.
- **Fault localization: GZoltar / Ochiai SBFL / FLACOCO**: rank code elements by `Ochiai = ef / sqrt((ef+nf)(ef+ep))` from per-test coverage of passing/failing tests. FLACOCO (ASSERT-KTH) wraps JaCoCo + Ochiai for Java. Requires E0 per-test coverage that Assertiva deliberately does not trust across revisions; usable only *within one run at one revision*. Not cloned.
- **Failure clustering / flakiness scoring:** Meta Probabilistic Flakiness Score (engineering.fb.com 2020): Stan statistical model producing a per-test flakiness degree monitored over time. Crash/stack bucketing research (e.g. ReBucket, ICSE 2012) uses position-weighted stack-frame similarity; Assertiva currently groups only identical normalized fingerprints (conservative, no similarity). Not code-verified.

---

## 3. Comparison with Assertiva per capability

Assertiva facts used (read this session): `assertiva/selection.py:1-120` (widening triggers, Confidence never "complete", CLAIM text), `assertiva/impact.py:1-45` (tiers E0–E4, relations), `assertiva/history.py:52-165` (Stability, MIN_FLAKY_FAILURES=2, MIN_STABLE_SAMPLES=3, fingerprint normalization, `environment_identity` = OS+machine+executable), `assertiva/improve.py:448-451` (bounded reruns, first outcome kept), `tests/test_selection_experiment.py:52-63` (10 single-project + monorepo defects incl. data file, dynamic import, rename, config).

### 3.1 Dependency collection precision (block-level dynamic fingerprints)
- **They do better:** testmon selects at function-block granularity from real execution (`process_code.py:291-306`), so editing an unrelated function in an imported module does not re-run a test; Ekstazi does the same at class level with debug-info-stripped bytecode hashing (comment/format changes do not select).
- **Assertiva:** E3 import/fixture/config edges at file level (IMPLEMENTED); E0 runtime coverage **not wired** by design (coverage cannot prove its revision).
- **Gap:** precision (over-selection), not safety. Also whitespace/comment-only edits currently select (file digest).
- **Decision: ADAPT-CONCEPT.** (a) AST-normalized digests: compute per-file `ast.dump`-style digest (comments/whitespace/docstrings optionally excluded) alongside the content digest; a change whose AST digest is unchanged becomes `Trigger`-free "NO_SEMANTIC_CHANGE" with explicit reason but still listed. (b) E0 as *revision-bound* evidence: record per-test coverage only when the run itself happened at the graph revision in a clean tree (Assertiva owns the run), store `(revision, tree digest)` with the coverage, and use it **only to add tests**, never to remove an E3-selected test, until a retrospective simulation proves equivalence. Changes: `assertiva/adapters/python_impact.py` (AST digest per unit), `assertiva/impact.py` (E0 edges carry `observed_revision` + `tree_digest`; `graph.require` rejects mismatch), schema `selection.changes[].semantic_digest_changed`. No code reuse from testmon (MIT, but approach is simple to re-derive).
- **Proof:** extend `tests/test_selection_experiment.py` with comment-only, docstring-only and unrelated-function edits: assert misses stay 0 and record `selected_count` reduction; never assert fewer tests on a defect row.

### 3.2 Unknown / non-code dependencies
- **They do better:** STARTS `file:*` star tests (always re-run on any change); TIA unknown file type → run all, plus **user dependency map**; Nx lockfile "auto" diff; Vitest `forceRerunTriggers`; DeFlaker "poison" warning for non-Java files.
- **Assertiva:** UNKNOWN_RELATION always added, UNMAPPED_CHANGE/CONFIGURATION widen to full (IMPLEMENTED — stronger than testmon/STARTS, which silently drop unresolved deps: `ZLCHelper.java:116-123`). Data-file defect is in the experiment.
- **Gap:** no declared user mapping file; lockfile change handling is coarse (UNKNOWN).
- **Decision: BUILD** a declared mapping (`.assertiva/impact-map.toml`: glob → tests/markers, tier E2, provenance "declared by project") — declared edges may *add* tests and may convert an UNMAPPED_CHANGE into a mapped one only if the mapping names the file explicitly; never narrows below configuration widening. **ADAPT-CONCEPT** lockfile diff: parse `uv.lock`/`poetry.lock`/`package-lock.json` base vs head, map changed packages to importing modules via existing import edges (E3), else widen. Changes: `assertiva/selection.py` (new `Trigger.DECLARED_MAPPING`, `Trigger.DEPENDENCY_LOCK`), `components.py` for per-workspace lockfiles, `references/DELIVERY.md` documents the map, schema `selection.widening[].trigger` enum.
- **Proof:** add defects "lockfile bump that breaks a used package" (stub local package) and "template/data consumed via declared mapping" to `DEFECTS`; assert 0 misses and that without the map the change still widens to full.

### 3.3 Environment identity for history/flakiness
- **They do better:** Develocity cross-build flaky = different outcomes for the **same task inputs**; testmon keys environment by package set + Python version and wipes data when it changes (`db.py:647-711`); target-determinator compares both revisions under one environment.
- **Assertiva:** `environment_identity` = OS, machine, executable name (`history.py:161-165`) — weaker; two runs with different installed packages at the same revision count as "same environment", so HISTORICALLY_FLAKY can be a dependency-drift artifact.
- **Decision: ADAPT-CONCEPT.** Environment digest = OS/arch + interpreter version + sorted installed distributions (name==version, from `importlib.metadata` of the target interpreter via the adapter, not of Assertiva) + relevant env-var *names* allow-list values (e.g. `TZ`, `LANG`, `PYTHONHASHSEED`) + lockfile digest. Keep the readable label. Changes: `assertiva/history.py` (`environment_identity` v2; `SCHEMA_VERSION=2` migration keeps old rows labelled `env_v1`), `assertiva/adapters/test_facts.py` to capture interpreter facts, schema `history.environment{digest,label,components[]}`.
- **Proof:** unit test: same revision, package version differs between runs, fail/pass → ENVIRONMENT_SPECIFIC not HISTORICALLY_FLAKY; identical inputs → HISTORICALLY_FLAKY.

### 3.4 Retries that keep the first failure
- **They do better:** Gradle test-retry: retry only failed tests, cap by `maxFailures` (mass failure ≠ flake), `failOnPassedAfterRetry`, class-level lifecycle handling, all attempts forwarded; rerunfailures: exception regex allow/deny lists, suite-wide rerun budget, `--fail-on-flaky`.
- **Assertiva:** bounded reruns ≤2 in `improve` keep first outcome (IMPLEMENTED for improve); generic run retries: PARTIAL; mass-failure guard: UNSUPPORTED.
- **Decision: ADAPT-CONCEPT** (do not depend on MPL plugin by default; may *detect* and parse its `rerun` reports). Add: rerun only when failing count ≤ `max_failures` (default e.g. 10 or 5% of selected), exception-type allow/deny from fingerprint `kind`, never convert a run to PASS (verdict stays "failed, then passed: OBSERVED_UNSTABLE_CURRENT_RUN"). Changes: `assertiva/process.py`/`improve.py` rerun policy object; schema `history.attempts[]` with `attempt_index`, `fingerprint`; HTML shows first failure prominently.
- **Proof:** seeded fixture project with (a) one test that fails on first attempt via a file sentinel, (b) 50 tests failing from a broken import: assert (a) yields OBSERVED_UNSTABLE_CURRENT_RUN with first fingerprint kept, (b) no reruns happen and classification is CONSISTENT_FAILURE candidate.

### 3.5 Order-dependence and seeded nondeterminism
- **They do better:** iDFlakies prefix-hash NOD vs OD classification with confirmation reruns; pytest-randomly per-test reseed `seed+crc32(nodeid)` and recorded seed; NonDex seeded shuffling with bisection window; flakefinder N-copies.
- **Assertiva:** M6 planned (PLANNED); seed/order not recorded (UNSUPPORTED).
- **Decision: ADAPT-CONCEPT + optional INTEGRATE of pytest-randomly as an *observed* plugin** (MIT): if present, capture its seed from the report header into evidence; Assertiva itself records executed order (pytest `-p` collection order from JUnit/`--report-log` event stream). Build an `order` probe for pytest: run (1) original order, (2) reversed, (3) k seeded shuffles; per test hash the ordered prefix (iDFlakies idea) to separate NOD (same prefix, different result) from OD (result changes only with prefix) and confirm with a 2-test isolation run (polluter + victim) before labeling ORDER_DEPENDENT. New Stability values: `ORDER_DEPENDENT` (confirmed), `NONDETERMINISTIC_SAME_ORDER`. Changes: `assertiva/history.py` enums + observation fields `order_prefix_digest`, `seed`; new module for the probe under existing `process.py` run infrastructure; budget-gated; CLI `assertiva audit --probe order --budget N`.
- **Proof:** benchmark fixture with seeded nondeterminism: 5 OD pairs (shared module state), 5 NOD tests (`random` with fixed failure probability, seeded per attempt), 20 stable tests. Measure precision/recall of labels over 20 seeds; acceptance: precision 1.0 for ORDER_DEPENDENT (confirmation required), recall reported, never a stable test labeled flaky.

### 3.6 "Not caused by this change" evidence (DeFlaker idea)
- **They do better:** DeFlaker labels a failing test that never covered changed code.
- **Assertiva:** selection reasons record proven paths; not used to qualify failures (UNSUPPORTED).
- **Decision: ADAPT-CONCEPT, wording-strict.** When a failing test has *no proven path* (E0–E3) to any changed unit **and** no UNKNOWN_RELATION reachable, annotate the failure `causal_link: NONE_PROVEN` ("no proven path from this change; failure may be pre-existing, environmental or flaky") — never "flaky", never suppress. If it reaches an unknown relation: `UNKNOWN`. Changes: `selection.py` exposes reverse lookup; `evidence.py` attaches to failed invocations; schema field `failures[].change_link`.
- **Proof:** experiment where the base already contains a failing unrelated test: assert it is annotated NONE_PROVEN and still reported as failed; and a defect through an E3 path is annotated PROVEN.

### 3.7 Prioritization and cost
- **They do better:** testmon orders selected tests by average duration (fast first) (`pytest_testmon.py:497-505`); Launchable/PTS rank by predicted failure probability, time budgets (`--time`, `--target`).
- **Assertiva:** p50/p95 with sample minimums (IMPLEMENTED); ordering: UNSUPPORTED; time budgets: PLANNED (M5) and must not imply safety.
- **Decision: BUILD** ordering only (never truncation by default): order = previously failing at this revision → tests with PROVEN E1–E3 paths to changes (shorter path first) → others by p50 ascending. Optional `--time-budget` produces an explicit **"partial"** run with remainder listed and Confidence forced to a new `BUDGET_TRUNCATED` (not claimable in gates). Schema `selection.order[]`, `selection.remainder[]`.
- **Proof:** APFD-style metric on the defect corpus (time-to-first-failure), compared to collection order.

### 3.8 Retrospective simulation / shadow mode
- **They do better:** Develocity simulator on real history (avoidable/unavoidable, % failures predicted), TIA "T1 then T2" recipe, Launchable observation mode.
- **Assertiva:** controlled 12-defect experiment (IMPLEMENTED as test); retrospective simulation on project history: PLANNED (M5).
- **Decision: BUILD** `assertiva audit --simulate-selection --since REV --runs N`: for each recorded full-suite state in `history.py` with a failing invocation at revision R and a parent P, compute `select_changes(P→R)` and report whether each first-failing test was selected, separated by stability class (exclude HISTORICALLY_FLAKY/ENVIRONMENT_SPECIFIC from the miss denominator but list them). Output only counts and named misses; never "safe". Add to HTML a "selection would have missed" table. Changes: `selection.py`, `history.py` query, schema `selection.simulation{states, failures, selected, missed[], excluded_flaky}`, DELIVERY.md shadow-mode guidance (run selected + full in CI for N weeks).
- **Proof:** mutation-style retrospective benchmark: take ≥3 real open-source Python repos' git history, replay K commits with injected single-function mutants (deterministic, seeded), record full-suite failures, then measure selection miss rate; report per trigger.

### 3.9 Failure intelligence (clustering, new vs recurring)
- **They do better:** Develocity Test Failure Analytics trends; Meta PFS quantifies degree of flakiness; bucketing research uses similarity.
- **Assertiva:** deterministic fingerprints, identical-only grouping (IMPLEMENTED); new vs recurring, trends: PLANNED.
- **Decision: BUILD (deterministic first).** New vs recurring = fingerprint seen at an ancestor revision in same environment digest. Optional second-level grouping by `(stage, kind, location)` without message, labelled `SIMILAR_SIGNATURE` (review candidate, never merged). Flakiness degree: report counts and a Wilson interval of failure rate per (test, revision, env) instead of a model score. REJECT ML scoring without labelled local data.
- **Proof:** fixture history with 3 distinct root causes × varied timestamps/paths: assert exact grouping, no cross-cause merge; Wilson intervals match reference values.

### 3.10 Coverage-based fault localization
- **Decision: REJECT for now / PLANNED-later.** Needs E0 per-test coverage within one run; usable as review candidates only. Revisit after 3.1(b).

---

## 4. Capability gap matrix

| Capability | testmon | Ekstazi | STARTS | Develocity | Launchable | iDFlakies | DeFlaker | MS TIA | Nx/Vitest | **Assertiva** |
|---|---|---|---|---|---|---|---|---|---|---|
| Revision-scoped dependency evidence | no (last run) | no | no | inputs hash | server | n/a | per diff | no | git base | **IMPLEMENTED** |
| Static import graph | no | no | yes (class) | unknown | unknown | n/a | n/a | no | yes | **IMPLEMENTED (Python)** |
| Dynamic per-test coverage deps | yes (block) | yes (class) | no | unknown | unknown | n/a | diff-only | yes | no | **SPECIFIED, not wired (E0)** |
| Semantic (AST/bytecode) change digest | yes | yes | yes | unknown | unknown | n/a | n/a | unknown | no | **UNSUPPORTED** |
| Unknown-dependency widening | partial (env) | safe default for missing data | star tests; silently drops unresolved | profiles | fallback run-all | n/a | warns | run-all | config triggers | **IMPLEMENTED** |
| Declared dependency map | no | no | no | additional inputs | no | n/a | no | yes | inputs | **UNSUPPORTED** |
| Lockfile-aware impact | env wipe | n/a | jars off | yes (inputs) | unknown | n/a | n/a | n/a | yes (auto) | **UNKNOWN/PARTIAL (config widening)** |
| Always run previously failing/new | yes | new via missing data | new | yes | flags | n/a | n/a | yes | n/a | **PARTIAL** (new via graph; previously failing not forced) |
| Prioritization by cost/risk | duration | no | no | ML | ML/time | n/a | n/a | no | no | **UNSUPPORTED (durations IMPLEMENTED)** |
| Retrospective simulation | no | no | no | yes | compare cmd | n/a | n/a | T1/T2 recipe | no | **PLANNED (controlled experiment IMPLEMENTED)** |
| Retry keeping first failure | no | no | no | yes | n/a | n/a | yes | n/a | n/a | **PARTIAL (improve only)** |
| Mass-failure retry guard | n/a | n/a | n/a | yes (maxFailures) | n/a | n/a | n/a | n/a | n/a | **UNSUPPORTED** |
| Cross-run flaky by identical inputs | no | no | no | yes | server | n/a | n/a | no | no | **PARTIAL (revision+weak env)** |
| Order-dependence detection | no | no | no | no | no | yes | no | no | no | **PLANNED** |
| Seed recording/reproduction | no | no | no | no | no | partial | no | no | no | **PLANNED** |
| "Not caused by change" annotation | no | no | no | no | no | no | yes | no | no | **UNSUPPORTED** |
| Failure fingerprint grouping | no | no | no | analytics | server | no | no | no | no | **IMPLEMENTED (identical only)** |
| New vs recurring failures | no | no | no | yes | server | no | no | no | no | **PLANNED** |
| Fault localization | no | no | no | no | no | no | no | no | no | **UNSUPPORTED (REJECT now)** |

---

## 5. What each does better than Assertiva, how, and how we would prove we matched it

1. **testmon** — function-block precision from coverage + AST-blocked CRC32 fingerprints; duration ordering. *Match proof:* AST-digest + revision-bound E0 add-only edges; on the controlled corpus plus comment/unrelated-function edits, 0 misses and a reported reduction in selected tests vs today; never fewer tests on defect rows.
2. **Ekstazi** — debug-info-stripped hashing means cosmetic changes do not select; safe default when data missing. *Proof:* cosmetic-edit cases select 0 additional tests with an explicit NO_SEMANTIC_CHANGE reason; missing graph → full (already STALE_GRAPH).
3. **STARTS** — explicit "star" tests for always-run-on-any-change. *Proof:* Assertiva already widens more; add a test that an UNKNOWN_RELATION test runs for *any* change (exists conceptually; assert in experiment).
4. **Develocity** — same-inputs cross-build flakiness, simulator, mass-failure retry cap, retry-only-failed. *Proof:* environment digest v2 tests (3.3); simulation command over recorded history (3.8); mass-failure fixture (3.4).
5. **Launchable** — explicit fallback modes and observation (shadow) mode. *Proof:* DELIVERY.md shadow-mode recipe + `simulate-selection` report; fallback on any selection error = full suite (verify existing behaviour with a fault-injection test in `select_changes`).
6. **iDFlakies** — OD vs NOD by order-prefix hashing with confirmation. *Proof:* seeded OD/NOD benchmark (3.5), precision 1.0 for confirmed ORDER_DEPENDENT.
7. **DeFlaker** — rerun-free signal that a failure is unrelated to the change. *Proof:* NONE_PROVEN annotation experiment (3.6) with a pre-existing unrelated failure.
8. **NonDex / pytest-randomly** — seeded, replayable nondeterminism; per-test reseed independent of order; bisection window. *Proof:* recorded seed reproduces the same failing order/value in a re-run (`--replay STATE_ID`) in the benchmark.
9. **MS TIA** — user dependency map; unknown file → all. *Proof:* declared-map defects (3.2).
10. **Nx** — lockfile diff to precise affected projects. *Proof:* lockfile defect row in monorepo experiment, 0 misses, and fewer components than full when the bumped package is used by one workspace only.

---

## 6. Concrete change list (consolidated)

- `assertiva/adapters/python_impact.py`: per-unit AST digest (ignore comments/whitespace; docstrings configurable), emitted with the content digest.
- `assertiva/impact.py`: E0 edges with `observed_revision`, `tree_digest`; add-only semantics in selection until simulation evidence exists.
- `assertiva/selection.py`: triggers `DECLARED_MAPPING`, `DEPENDENCY_LOCK`, `NO_SEMANTIC_CHANGE` (reason only, still listed); force previously failing tests at base; ordering; `BUDGET_TRUNCATED` confidence; `simulate_selection()`.
- `assertiva/components.py`: per-workspace lockfile diff → affected components.
- `assertiva/history.py`: environment digest v2 (SCHEMA_VERSION 2 migration), new stability values `ORDER_DEPENDENT`, `NONDETERMINISTIC_SAME_ORDER`, fields `seed`, `order_prefix_digest`, `attempt_index`; new-vs-recurring query; Wilson interval helper.
- `assertiva/process.py` / `improve.py`: retry policy (only failed, max-failures guard, exception allow/deny, budget), first failure always primary.
- `assertiva/evidence.py`: `change_link` on failures (PROVEN / NONE_PROVEN / UNKNOWN).
- `schemas/assurance-report.schema.json`: replace free-form `selection`/`history` objects (`:523-530` region) with typed sub-schemas for the fields above.
- `references/DELIVERY.md`: shadow-mode recipe, declared impact map, never-claim rules for budgets.
- CLI: `audit --simulate-selection`, `audit --probe order --budget N`, `--time-budget` (partial, labelled).
- HTML: first-failure-first attempt view; "would have missed" table; order-probe results; NONE_PROVEN badges with neutral wording.
- Evals/tests: extend `tests/test_selection_experiment.py` (cosmetic edits, lockfile, declared map, pre-existing failure); new seeded flakiness benchmark (OD/NOD/stable, 20 seeds); mass-failure retry fixture; env-digest unit tests; retrospective mutation replay on ≥3 public Python repos (budget-gated, results recorded, rubric frozen before running per project memory rules).

## 7. Security / license notes
- testmon `eval()`s the `--testmon-env` / ini expression (`testmon_core.py:626-639`): never invoke testmon on untrusted repos' config from Assertiva without isolation.
- DeFlaker: hard-coded remote DB credentials and Java deserialization — REJECT.
- FlakeFlagger: pickled models — REJECT loading; reuse feature ideas only.
- Launchable/Smart Tests, Develocity, SeaLights: send commit/test data to a vendor service — conflicts with Assertiva's local-evidence posture; REJECT as dependency.
- pytest-rerunfailures is MPL-2.0: may be *detected/parsed* when the user installed it; do not vendor code. iDFlakies and DeFlaker have no license file: ideas only.

## 8. Effort and unfinished items
- Approximate tokens spent: ~125k (well under the 300k target).
- Not done / uncertain: Ekstazi and DeFlaker headline numbers not re-verified from the papers (marked); iDFlakies paper numbers recalled; Jest/Vitest/SeaLights/GZoltar/FLACOCO not cloned; Develocity PTS internals unknowable (closed); testmon `--tmnet` path and xdist handling not read; commit dates for tarball-fetched repos not recorded; no measurements were run (by instruction).
