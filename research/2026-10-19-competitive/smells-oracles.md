# Competitive research: test smells, oracle/assertion quality, test fidelity, redundancy

Date: 2026-10-19. Researcher: agent (source-level, read-only).
Clones: `scratchpad/research-src/smells/<name>`. Each was a fresh `git clone --depth 1`. Nothing was installed, built or run. Cloned content was treated as data.
Labels used below:
- **CONFIRMED-IN-CODE**: I read the logic at the cited path:line. Behaviour claims come from reading only, not from running anything.
- **DECLARED-ONLY**: README, paper or docs claim it, and I did not verify it in code.
- **PAPER**: a number reported by a publication. I did not reproduce it.

On Windows several repos hit MAX_PATH during checkout (jnose-core, PyNose). Those files were read with `git cat-file` from HEAD into `jnc-blobs/` and `pynose-blobs/`. For blob files the line numbers come from the blob, and are approximate where marked "~".

---

## 0. Identifying "test-fidelity"

No package, PyPI/npm project, or skill named exactly `test-fidelity` exists as a tool. A GitHub repository search for `"test-fidelity"` returned:
- `tanveerxz/test-fidelity`: one COBOL file, no description. Unrelated.
- `dudasmarques/test_Fidelity`, `genaro-lopez/test_fidelity`: job-interview exercises. Unrelated.
- **`officefloor/test-fidelity-long-run`**: "Can an agent write the tests?" It is a harness that measures whether *agent-written* acceptance tests pin the requested behaviour. It uses per-requirement mutation catalogues, a "mutation zero", reviewer/oracle-proxy agents and post-hoc degradation analysis. It is the only match about *test* fidelity, and it has auxiliary tools (`tools/`) and agent conditions (`fidelity/conditions.py`), which matches the brief's "auxiliary tools/agents". **I treat this as the target.** Uncertainty: the brief may have meant something private or unpublished. Web searches ([1](https://codex.danielvaughan.com/2026/05/02/over-mocked-tests-agent-generated-test-quality-codex-cli-realistic-testing/), [2](https://tianpan.co/blog/tags/test-fidelity)) found only blog posts that use "test fidelity" as a concept. One related study is Hora & Robbes, [arXiv 2602.00409](https://arxiv.org/abs/2602.00409). It reports that agent test commits add mocks more often than human ones (36% vs 26%), and that 95% of those are the generic "mock" type.

---

## 1. Deep dives

### 1.1 officefloor/test-fidelity-long-run (the "test-fidelity" target)
- URL: https://github.com/officefloor/test-fidelity-long-run. SHA `fa1e6f33e80b4ffc022c046fd440b2cc311f97c2`, commit 2026-10-08. Repo created 2026-10-04, 0 stars.
- **License: none** (the GitHub API returns `license: null` and there is no LICENSE file). That means all rights reserved, so nothing can be copied. Only concepts can be adapted.
- Maintenance: very young (4 days of history in the shallow view). Single author org (OfficeFloor). It belongs to a series of "long degradation" experiments by the same org.
- **Scope.** An experimental harness, not a product. A fixed reference application evolves through 60 checkpoints, each a plain-English change request. An agent writes Playwright acceptance tests *before* seeing the implementation. The tests are then graded:
  1. The suite must be green on cpN and must never shrink.
  2. "Mutation zero": run the new suite against cp(N-1), the app *without* the feature. If nothing fails, "the new tests do not bind to this change".
  3. A hand-authored mutation catalogue is applied one mutation at a time. Kill rate is reported per request clause.
- **Non-goals.** It does not analyse any third-party suite statically, and it is not a general tool. It runs only on its own fixture, a Java/Spring + React app.
- **Architecture (examined paths).**
  - `fidelity/run.py` is the driver. Flow: materialise → Landlock-confined agent area → copy back → gate (two repeats, flake detection) → mutation zero (`run.py:516-550`) → authored mutations (`run.py:552-590`) → verdict `kill_rate`, `survived` (`run.py:581-609`).
  - `fidelity/mutations.py:53-72` is a substitution mutation that must match **exactly once**. It raises on 0 matches (stale) or more than 1 (ambiguous kill). `mark_calibrated` (`:100-121`) sets `calibrated: true` only from a *replay* run of the known-good suite, which gates grading.
  - `fidelity/spec.py:155-170` is the reviewer prompt. It looks for: "a clause of the request no test asserts", "a test that asserts something weaker than the clause … would still pass if implemented wrongly", "a test that asserts what the application ALREADY does rather than what the change adds", and "a test that cannot pass as written".
  - `spec.py:280-300` is the reconcile prompt: "the same behaviour asserted two ways — keep the assertion that would fail if the behaviour were implemented wrongly, and drop the weaker one".
  - `fidelity/conditions.py:65` is `proxy_leak_scan`, which flags an oracle proxy that leaks test code.
  - `fidelity/analyse.py:282-310` computes the degradation slope with a chain-level bootstrap. It deliberately reports no interval when there is only one chain (`:394`).
- **I/O example (real, `mutations/cp08.yaml`).**
  ```yaml
  - id: "002-client-count-off-by-one"
    clause: "how many clients"
    breaks: One fewer client than exists. Killed by an exact count; survived by a test that only asserts the tile is present or non-zero.
    find: "...new DashboardView(clients.count(), ..."
    replace: "...new DashboardView(clients.count() - 1, ..."
  ```
  The output is per-checkpoint `cpNN.json` (prompt, contract, gate, each mutation's verdict and killing test) plus a Markdown summary listing survivors and flaky tests.
- **Quality evidence (DECLARED-ONLY, README §status, DESIGN §11).** 133 mutations across 60 checkpoints. The first replay killed 120. The 13 survivors were diagnosed as "nine reference-suite holes, three equivalent mutants, one reference assertion that could not fail". A full replay of 60/60 green took 4h53m, with zero flakes. There are no unit tests for the harness in the repo.
- **Inconsistency.** README says only `blind` and `prototype-first` are implemented in agent mode. DESIGN §11 says all six conditions are built. Not resolved.
- **What it does better.** (a) It defines each oracle-strength probe *per requirement clause* and explains in the `breaks:` text which weak assertion would survive it. That is labelled ground truth for "weak oracle". (b) It calibrates probes against a known-good suite before trusting them, and classifies survivors as suite hole, equivalent or unkillable. (c) Mutation zero is a cheap, general negative control for "the test restates existing behaviour". (d) The reviewer agent is given an explicit checklist of weak-oracle patterns.

### 1.2 tsDetect / TestSmellDetector (TestSmells org)
- URL: https://github.com/TestSmells/TestSmellDetector. SHA `e89ce1a28d56db314d159e8957591aef6002173d`, last commit 2022-07-18, repo push 2022-10-01. 80 stars, 23 open issues. **GPL-3.0.**
- Maintenance: dormant since 2022. Open bug reports remain unanswered (#14, #19, #27).
- **Scope.** 21 JUnit smells, Java only, parsed with JavaParser, at file/method level. Non-goals: no execution, no runtime evidence, no other languages.
- **Flow.** `Main.java:19-106` reads a CSV of `app,testPath[,prodPath]` and builds a `TestFile` from each line. `TestSmellDetector.detectSmells` then runs every `AbstractSmell` visitor, and output is a CSV of *counts per smell per file* (`Main.java:98-104`), with no locations (issue #22 asks for them).
- **Thresholds.** `DetectionThresholds.java:9-17` and `kotlin/thresholds/Thresholds.kt:24-53` hold the defaults (0/1, after van Deursen). `SpadiniThresholds` overrides them with eagerTest 4, assertionRoulette 3 and verboseTest 13 (`Thresholds.kt:59-66`), from Spadini et al. "Investigating severity thresholds for test smells", MSR 2020.
- **Detector implementation (CONFIRMED-IN-CODE):**
  - **Test discovery.** `Util.java:8-22` requires `@Test` or a `test*` name, **plus the `public` modifier**. JUnit 5 tests are idiomatically package-private, so they are *silently not analysed*.
  - **Assertion Roulette.** `AssertionRoulette.java:68-78` and `:97-128` decide "message missing" by *argument count* (fewer than 3 for assertEquals/assertThat, fewer than 2 for assertTrue). A fluent AssertJ `assertThat(x).isEqualTo(y)` has 1 argument, so it always counts as unlabelled (issue #13). A single-assert test is exempt (`:73`).
  - **Redundant Assertion.** `RedundantAssertion.java:76-116` flags boolean literals in assertTrue/False, a `null` literal in assertNull/NotNull, and assert* with two *syntactically equal* arguments.
  - **Magic Number.** `MagicNumberTest.java:55` uses `magicCount >= threshold` with a default of 0, so *every* test is flagged (issue #27, open since 2024-08).
  - **Exception Catching/Throwing.** `ExceptionCatchingThrowing.java:58` counts a `throws` clause on the test method as the smell. That is idiomatic JUnit, so it produces a false positive.
  - **Sensitive Equality.** `SensitiveEquality.java:71-74` uses `argument.toString().contains("toString")`, a textual match on any assert argument.
  - **Mystery Guest.** `MysteryGuest.java:51-80` uses Android-specific type and method lists (`SQLiteDatabase`, `getFilesDir`…). Variables annotated `@Mock`/`@Spy` are exempt (`:148`).
  - **Unknown Test.** `UnknownTest.java:56-75` means no `assert*`/`fail` call and no `@Test(expected=…Exception)`. Custom assertion helpers produce false positives.
  - **Sleepy Test.** `SleepyTest.java:77-81` matches only `Thread.sleep`.
- **Known-wrong evidence.** Issue #19 ("Once found 'true', never goes 'false'": per-file state is not reset, so a smell leaks into following files) and issue #14 ("Detected smells are wrong") are open.
- **Quality evidence.**
  - Tests: `src/test/kotlin/testsmell/TestDetectionCorrectness.kt` (2151 lines) asserts detections on fixture files.
  - PAPER: the tsDetect demo (Peruma et al., ESEC/FSE 2020 tool demo, https://2020.esec-fse.org/details/esecfse-2020-tool-demos/4/tsDetect-An-Open-Source-Test-Smells-Detection-Tool) reports **precision 96% and recall 97% on average over 65 hand-made test files covering 19 smells**. That benchmark was built by the authors.
  - PAPER, independent: Panichella, Panichella, Fraser, Sawant & Hellendoorn, "Test smells 20 years later", EMSE 27:170 (2022), https://doi.org/10.1007/s10664-022-10207-5. I extracted the text from the TU Delft open-access PDF, which is CC BY. Replication package: https://figshare.com/s/7b8bf9a7580001929f63. Results for tsDetect with Spadini thresholds:
    - On **EvoSuite** tests: Assertion Roulette P 0.67 / R 0.50, Eager Test P 0.73 / R 0.55.
    - On **manually-written** tests: AR P 1.00 / R 0.80, Eager P 0.94 / R 0.39, Resource Optimism P 0.33 / R 0.20.
    - The older tool used by Grano et al. had AR precision of 0.22 on EvoSuite tests. It flagged single-assert tests.
    - The abstract says the older tool "misclassified over 70% of test smells". The authors also conclude that the smell vocabulary is "highly mismatched to real concerns": smells were ubiquitous yet "virtually never correlated with semantic or maintainability flaws".
  - **This is the strongest external evidence that smell counts are not quality verdicts. Assertiva's "leads, not verdicts, no score" stance matches it.**

### 1.3 JNose (arieslab/jnose and jnose-core)
- App: https://github.com/arieslab/jnose. SHA `315d79332c51f403368adb494dbf70cfe6f8bc5f` (2026-06-26), v2.5.0, Spring Boot 4 + Wicket web UI. **GPL-3.0.**
- Core: https://github.com/arieslab/jnose-core. SHA `d38efbe7c40a5e3bc30f9f49fbbdbe222f3f33d5` (2026-06-22), consumed as `jnose-core 0.9.4`. **GPL-3.0.**
- Maintenance: active in 2026 (dependency bumps, Java 21+ syntax such as `catch (NumberFormatException _)`).
- **Scope.** A fork and evolution of tsDetect with 21 smells. It adds:
  - per-instance **line ranges**;
  - per-smell enable/disable toggles (`TestSmellDetector.java:30-50`);
  - git-history **evolution** analysis (`base/GitCore.java`);
  - coverage via a Cobertura subprocess (`base/cobertura/*`);
  - a CSV export and web dashboards (`pages/EvolutionPage.java`, `ChartsPage.java`).
- **Detector differences from tsDetect (CONFIRMED-IN-CODE):**
  - `Util.java:7-17` (core) **drops the `public` requirement**, so JUnit 5 package-private tests are analysed.
  - Assertion Roulette (blob ~L80-118) emits **one smelly element per unlabelled assertion with its `begin-end` range**, once more than one is unlabelled. An empty-string message `""` counts as missing (`explanationIsEmpty`).
  - Exception Catching/Throwing (`ExceptionCatchingThrowing.java:62-65`, blob) now flags only `try` statements with their ranges. The `throws` clause is no longer a smell. A `try` that *asserts on the caught exception* is still flagged, which is a false positive.
  - Output DTO `dto/TestSmell.java:10-40` carries name, method, `range` "10-15", and an MD5 id of project, class and method.
- **Quality evidence.** Unit tests exist per smell (`src/test/java/io/github/arieslab/test/*Test.java`).
  - PAPER: Virgínio et al., "On the test smells detection: an empirical study on the JNose Test accuracy", JSERD (https://journals-sol.sbc.org.br/index.php/jserd/article/view/1893). JNose and tsDetect were run on the same 65-file benchmark, with precision 85–100%, recall 90–100% and mean F ≈ 95% (from search results; I did not read the full paper).
- **Not investigated:** the coverage pipeline's correctness, and whether the evolution view uses commit-level re-parsing or diffs.

### 1.4 PyNose (JetBrains-Research)
- URL: https://github.com/JetBrains-Research/PyNose. SHA `081e5f9dcc416da4a290bcc5102ce46f104afefa` (2022-02-24). 57 stars. **Apache-2.0.** Dormant since 2022. The README pins PyCharm 2021.3.
- **Scope.** A PyCharm plugin: 17 smells as IDE inspections over PSI, for unittest and pytest, several with quick-fixes. The original CLI version lives in the `ASE2021` branch, which I did not read. Non-goals: no CLI on `main` (`cli/build.gradle.kts` only), no execution.
- **Detectors (CONFIRMED-IN-CODE, plugin/src/main/kotlin/…/inspections):**
  - **Redundant Assertion.** `common/RedundantAssertionTestSmellVisitor.kt:18` lists the operators. `:29-63` flags a comparison that `PyEvaluator` can constant-fold, or one with literals on both sides.
  - **Likely false positive in Redundant Assertion (found by reading, not run).** When the assert argument is parenthesised (`:38-41`), it takes `findChildOfType(PyLiteralExpression)`, *any* literal descendant. Then `:58-61` flags the assertion if any literal was found. So `assert (result == 5)` would be reported as redundant. To confirm, add an `example/` fixture or a PyCharm test.
  - **Lack of Cohesion.** `common/disabled/LackCohesionTestSmellVisitor.kt:37` sets threshold 0.6 "from the paper". `:48-76` computes token-bag cosine similarity between test bodies, with camelCase/underscore splitting. This is redundancy and cohesion by *textual similarity*.
  - **Exception Handling.** `universal/ExceptionHandlingTestSmellInspection.kt:46-55` flags any `try/except` or `raise` in a test.
  - **Suboptimal Assert.** `unittest/SuboptimalAssertTestSmellUnittestInspection.kt:25-52` covers `assertTrue(a == b)` and `assertEqual(x, True/None)` → suggests the specific assert, with a quick-fix.
  - **Discovery.** `util/PytestInspectionsUtils.kt:16-30` treats files starting with `test` or ending in `test.py`, functions starting with `test`, and classes `Test*` as tests.
- **Quality evidence.** PAPER: Wang, Golubev, Smirnov, Li, Bryksin & Ahmed, "PyNose: A Test Smell Detector For Python", ASE 2021, https://arxiv.org/abs/2108.04639.
  - Weighted average precision 94.0%, recall 95.8%, F1 94.9%, on a manually labelled sample.
  - Per smell: Lack of Cohesion P 78.6% / R 84.6%. Some smells have only 1–3 labelled instances.
  - The authors state that Conditional Test Logic false positives come from flagging control flow regardless of its effect on assertions. Assertiva avoids this: CONDITIONAL_ASSERTION fires only when *every* assertion is behind a condition.
  - The suboptimal-assert list is on Zenodo (https://zenodo.org/record/5156098).

### 1.5 pytest-tidy (az-pz), a modern Python AST smell linter (discovered)
- URL: https://github.com/az-pz/pytest-tidy. SHA `5c25869fd3d95f9fe7f42ca574e44f3e37d6f5e3`. **The repo was created and last pushed on 2026-07-15 (one day)**, so maintenance is unknown and it looks like a code drop. **MIT.**
- **Scope.** 32 rules in 7 categories (`docs/rules.md`), using stdlib `ast` only. It ships as a CLI, a pre-commit hook and a pytest plugin, with `--fix` autofix and `--format github|json`.
- **Detectors that directly overlap Assertiva FALSE_GREEN (CONFIRMED-IN-CODE):**
  - **PTD002 assert-on-tuple.** `assert (x == 1, "msg")` is always true (`rules/assertions.py:110`).
  - **PTD003 test-without-assertion.** `assertions.py:146-221` counts `assert`, `raise`, `pytest.raises` context, any call whose name contains "assert", `fail`, unittest aliases, and **configurable `assert-calls` helpers** (`config.py:63`).
  - **PTD501 mock-uncalled-assert.** `mock.assert_called_once` without parentheses is a no-op (`rules/mocking.py:19-51`).
  - **PTD502 mock-nonexistent-attr.** `mock.called_once_with(...)` is a typo that auto-creates an attribute and is always truthy (`mocking.py:77-86`).
  - **PTD101 except-pass**, **PTD102 raises-broad-exception**, **PTD103 raises-without-match**, **PTD104 raises-multiple-statements.**
  - **PTD301 sleep, PTD302 datetime.now, PTD303 random-without-seed, PTD304 network-call.**
  - **PTD603 parametrize-values-mismatch.**
- **Quality evidence.** Per-category rule tests (`tests/test_rules_*.py`). "Near-zero false positives by design" is **DECLARED-ONLY**: no precision study.

### 1.6 Descartes / pitest-descartes (pseudo-tested methods)
- URL: https://github.com/STAMP-project/pitest-descartes. SHA `20cbecff6fab5a3bdfcdc048371981cbae973fd5` (2026-09-29). 127 stars. **LGPL-3.0.** Active.
- **Scope.** A PIT mutation *engine* plugin with "extreme mutation": it replaces a whole method body with `return` (void), `null`, empty values, constants, `Optional.empty`, an argument, `this`, or a new instance (`operators/*.java`). Non-goals: no fine-grained mutants.
- **Classification (CONFIRMED-IN-CODE).** `reporting/models/MethodClassification.java:33-68` classifies each method:
  - all extreme mutants detected → TESTED;
  - none detected → **PSEUDO_TESTED**;
  - mixed → **PARTIALLY_TESTED**;
  - not covered → NOT_COVERED;
  - not covered mixed with anything else → ERROR.
- **Noise control (CONFIRMED-IN-CODE).** `interceptors/stopmethods/StopMethodMatchers.java` uses bytecode matchers to skip methods where an extreme mutant is meaningless or equivalent: static initialisers, `hashCode`, `toString`, deprecated, synthetic, empty void, methods returning null/this/a parameter/a constant, simple getters and setters, Kotlin setters, delegates, and enum-generated methods. `SkipShortMethodsFilter.java:39` adds a line-count threshold, and `AvoidNullInNotNullFilter` covers `@NotNull` returns.
- **Output.** A JSON `methods` report (`src/main/resources/schemas/methods.report.schema.json`). Each method has `classification` in {error, tested, pseudo-tested, partially-tested, not-covered}, `details` {package, class, name, desc, file, line}, `mutations[]` {operator, result, `detected-by[]`}, and `tests[]`. There is also an "issues" HTML report, and standard PIT `mutations.xml` is still produced.
- **Quality evidence.** PAPER:
  - Niedermayr, Juergens & Wagner, "Will my tests tell me if I break this code?", CSD 2016.
  - Vera-Pérez, Danglot, Monperrus & Baudry, "A comprehensive study of pseudo-tested methods", EMSE 2019, https://arxiv.org/abs/1807.05030. It replicated the result on 28K+ methods and manually analysed 101 pseudo-tested methods. These are "significantly less tested", and developers would often not pay the cost to fix them. I did not extract per-project percentages.

### 1.7 TOGA (microsoft/toga), neural oracle generation
- URL: https://github.com/microsoft/toga. SHA `45be2fc78fbd6fdbbd43f73e5d42c4291e56d99a` (2022-07-25), last push 2023-06. **MIT.** A research artefact.
- **Architecture (CONFIRMED-IN-CODE).** Two fine-tuned classifiers:
  - exception-vs-normal (`model/exceptions/run_classifier.py`, with thresholds in `model/exceptions/threshold.py:14-41`);
  - an assertion ranker over **grammar-generated candidates** (`model/assertion_data.py:9-25`). The candidates are regexes over `assertEquals|assertTrue|assertFalse|assertNotNull|assertNull`, and `gen_variants` (`:229`) enumerates type-matched literals and variables from a vocabulary. Ranking is in `model/ranking.py:57`.
  - Inputs are the focal method and the test prefix. The output is one ranked assertion or an expected exception.
- **Quality evidence.**
  - PAPER: Dinella et al., https://arxiv.org/abs/2109.09262 (ICSE 2022), report 57 bugs found on Defects4J, 30 of them unique.
  - Independent critiques (PAPER): Liu et al., ISSTA 2023, https://arxiv.org/abs/2305.17047, report **TOGA precision of 0.38%**, and a trivial "NoException" baseline finds 61% of TOGA's bugs with twice the precision. Hossain et al., FSE 2023, https://arxiv.org/abs/2307.16023, report **over 47% of generated assertion oracles are false positives**, and the oracle type is misclassified 24% of the time.
- **Relevance.** A cautionary tale. Generated oracles mostly restate current behaviour, which is a self-referential oracle. Assertiva should not generate oracles. It should make the agent show which behaviour an oracle would fail on.

### 1.8 SNUTS.js core (JavaScript)
- URL: https://github.com/Jhonatanmizu/snuts.js-core. SHA `b389f5b3030d1f837b6ca3fe94266588e470321a` (2026-09-28). **GPL-3.0.** Active.
- Uses a Babel AST. There are 15 detectors (`lib/detectors/*.ts`), each with a co-located `.test.ts`: anonymous test, comments-only, complex snapshot, conditional logic, general fixture, identical description, non-functional statement, `.only`, overcommented, sensitive equality, sub-optimal assert, test-without-description, transcripting (console), verbose, and verify-in-setup.
- The output type is `lib/core/detector.interface.ts:5-20`: file, start/end line and column, message, codeBlock, description, explanation, and `severity` low/medium/high.
- Per-smell threshold overrides come from a config file (`lib/config/snuts-config.ts:8-70`).
- An **LLM refactor service** (`lib/ai/refactor-service.ts`) generates patches and writes files.
- **Likely false positive (by reading).** `sensitiveEqualityLogic.ts:43-50` flags *any* `BinaryExpression` with a `.toString()` call anywhere in the file, including helpers outside tests.
- PAPER: SNUTS.js, SBES 2024 (https://sol.sbc.org.br/index.php/sbes/article/view/30417), reports "100% accuracy" for three smells on a preliminary dataset. That is a small sample.

---

## 2. Peripheral projects (brief)

- **smelly-test (marabesi)**: https://github.com/marabesi/smelly-test. SHA `27a4413`, 2026-10-19, ISC.
  - A JS/TS detector, VS Code extension and CLI using the TypeScript compiler AST. It detects if/for, setTimeout, console and `jest.mock` counts.
  - `detector/src/smells/findDuplicatedTestCases.ts:36-63` keys "duplicates" by *line range*. Two different tests never share one, and the body comparison is commented out (`:18`). It is also not referenced anywhere else in `src`, so it is dead code. Lesson: textual-duplicate detection is easy to get vacuously wrong. Assertiva's DUPLICATE_CASES tests must include positive fixtures.
- **AromaDr / AromaLIA**: https://github.com/publiosilva/aromadr (MIT), SBES 2025 (https://sol.sbc.org.br/index.php/sbes/article/view/37078). A language-independent detector for C#, Java, JS, TS and Python with a REST API. Not cloned; its precision is unknown to me.
- **Pytest-Smell**: PyPI `pytest-smell` (https://pypi.org/project/pytest-smell/), ISSTA 2022 tool demo. It has a CSV export and a CI exit-code mode. The README calls it a "research tool, work in progress". I could not locate the repo.
- **TEMPY**: https://github.com/pageviewer/TEMPY, MIT, last push 2022-06. A Python test smell detector. Not cloned.
- **Checked coverage (Schuler & Zeller)**: ICST 2011 (https://www.st.cs.uni-saarland.de/publications/files/schuler-icst-2011.pdf) and STVR 2013. It measures the share of executed statements that are in the **dynamic backward slice of an oracle**.
  - In the STVR example, a test had 83% statement coverage and 0% checked coverage. Adding one non-null assert raised checked coverage to 65%. So checked coverage is *very* sensitive even to weak oracles.
  - The authors report it is cheaper than mutation and correlates with oracle quality on 7 projects. The tooling was a Java dynamic slicer and is unmaintained.
- **OASIs / GAssert (Jahangirova, Tonella et al.)**: ISSTA 2018 demo (https://research.facebook.com/file/389756425844240/OASIs-Oracle-Assessment-and-Improvement-Tool.pdf). It assesses *assertions* by generating inputs that expose false positives and mutants that expose false negatives. Fault detection of improved oracles rose by an average of 48.6%. GAssert (https://arxiv.org/abs/2103.02901) automates the improvement step, and notes that humans fixed all reported deficiencies for only 67% of assertions.
- **EvoSuite assertion minimisation / mutation-based assertion generation (Fraser & Zeller 2010–2011)**: EvoSuite keeps only the assertions that kill at least one mutant. That gives an *operational* definition of a non-contributing assertion. Not re-read here.
- **ATLAS (Watson et al., ICSE 2020)**: seq2seq assertion generation. It belongs to the same family as TOGA, with the same self-referential risk. Not cloned.
- **GeMTest (TUM)**: https://github.com/tum-i4/gemtest, ICSE 2025 demo. Metamorphic relations written as decorated Python functions that expand into pytest cases. Also Chrysalis (ASE 2025 demo). Relevant only as a *recommendation* when no exact oracle exists.
- **Test-suite reduction**: Shi, Gyori, Gligoric, Zaytsev & Marinov, "Balancing trade-offs in test-suite reduction", FSE 2014 (https://mir.cs.illinois.edu/gyori/pubs/fse14reduction.pdf), studied 18 projects. Reduction defined by *killed mutants*, not coverage. The quality of a reduced suite changes across later versions, as followed up in ISSTA 2018, "Evaluating test-suite reduction in real-world software evolution". This supports Assertiva's rule: consolidate only on per-test mutation evidence, and re-check over time.
- **Smell harmfulness**:
  - Spadini et al., ICSME 2018: smelly tests are more change-prone and defect-prone (cited from memory, not re-verified).
  - Spadini et al., MSR 2020, on severity thresholds: the thresholds used in tsDetect.
  - Panichella et al. 2022 (above): weak link to real concerns.
  - Bavota et al., EMSE 2015: smells hurt comprehension (cited from memory, not re-verified).

---

## 3. Comparison with Assertiva, per capability

Assertiva facts were read in this session:
- `assertiva/effectiveness.py:18-159`: the rules.
- `assertiva/adapters/test_facts.py:214-313`: Python facts.
- `assertiva/pytest_audit.py:78-97, 217-254`: assertion kinds.
- `assertiva/adapters/mutation.py:1-104`: Stryker/MTE, PIT `mutations.xml` and mutmut stats.

### 3.1 Python false-green patterns (assert-on-tuple, mock no-op assertions)
- **They do better.** pytest-tidy PTD002, PTD501 and PTD502 (MIT) detect three classic "cannot fail" Python patterns.
- **Assertiva today (CONFIRMED-IN-CODE).**
  - `pytest_audit._assertion_kind` (`:78-97`) returns `BEHAVIORAL_ASSERTION` for any non-status, non-`is not None` assert. So `assert (x == 1, "m")` and `assert mock.called_once_with(1)` are both classed as strong VALUE oracles.
  - `test_facts.py:226-229` flags TAUTOLOGY only for a truthy `Constant` or `left == right`.
  - `mock.assert_called_once` with no call is not an `ast.Call`, so `_call_oracle` never sees it. A test whose only check is that no-op is therefore "no oracle" (`summarize` `without_explicit_oracle`), not FALSE_GREEN.
- **Gap.** Real false greens get labelled strong.
- **Decision: BUILD** (small; ADAPT-CONCEPT from pytest-tidy, with no code copied).
- **Changes.**
  1. In `test_facts._python_test`, add TAUTOLOGY for:
     - an `ast.Assert` whose `test` is an `ast.Tuple` with at least one element;
     - an `ast.Expr` whose value is an `Attribute` with `attr` in the mock-assert set (`assert_called`, `assert_called_once`, `assert_not_called`, …), i.e. a no-op lookup;
     - an `ast.Assert` on `<x>.called_once_with(...)`, `.called_with(...)` or `.assert_called_once_with` typos (attr starts with `called_`, or matches `assret`/`asert`).
     Record `detail.pattern` subtypes `ASSERT_ON_TUPLE`, `MOCK_ASSERT_NOT_CALLED` and `MOCK_TYPO_ATTRIBUTE` in the candidate.
  2. In `pytest_audit._assertion_kind`, return `TRUTHY` (not BEHAVIORAL) for a bare `Name`, `Attribute` or `Call` test that has no `Compare`. That moves `assert result` from VALUE to TRUTHY, which affects the WEAK_ORACLE counts, so call it out in the CHANGELOG.
  3. Schema: no change (`detail` is free-form). Optionally document `detail.pattern` values in `schemas/assurance-report.schema.json`.
  4. SKILL/`references/TEST_QUALITY.md`: one bullet under "Oracles": "an assertion that cannot fail in Python (tuple, un-called mock assert, mock attribute typo) is a false green; Python itself warns about the tuple form."
- **Proof.** Add a labelled fixture set `tests/fixtures/python_false_green/`:
  - ≥5 positives per pattern;
  - ≥10 calibration negatives: `assert (a == b)` (parentheses without a tuple), `assert mock.called` (legitimate), `mock.assert_called_once()`, a tuple *inside* a comparison such as `assert t == (1, 2)`, and `assert_called_once` inside a helper.
  Report precision and recall per pattern in `tests/test_effectiveness.py` and gate at P = 1.0 on the fixtures. Then add an eval case `evals/cases/PY_ASSERTION_CANNOT_FAIL.md`: the agent must confirm via a negative control and must not call the suite strong.

### 3.2 Assertion Roulette and Mystery Guest (declared in Assertiva, never emitted)
- **Assertiva (CONFIRMED-IN-CODE).** `effectiveness.py:33-34` lists `ASSERTION_ROULETTE` and `MYSTERY_GUEST` in `SMELL_NOTES`, but **no extractor in `test_facts.py` ever emits them**. A repo-wide grep finds them only in `effectiveness.py` and `build/`. So they are SPECIFIED but not implemented, and the report can never show them.
- **They do better.** tsDetect and JNose implement both.
  - JNose gives per-instance line ranges, and exempts single-assert tests (tsDetect `AssertionRoulette.java:73`).
  - The evidence on precision is mixed. Panichella 2022 measured AR at P 0.22–1.00 depending on the tool and the suite. AR is a *diagnosability* smell, not a correctness one.
- **Decision.** Either **BUILD** AR minimally (Python `assert` without a message, unittest without `msg`, JS `expect` chains, JVM assert*): count unlabelled assertions, with the Spadini threshold of ≥3 and single-assert exempt, *and treat AssertJ/expect fluent chains as self-describing*, which avoids tsDetect issue #13. Or **remove** the two entries from `SMELL_NOTES`. Recommendation: build AR, because it is cheap, and **REJECT** Mystery Guest for now. The tsDetect version is Android-specific, and Assertiva's FILESYSTEM/DATABASE boundaries already carry that information.
- **Proof.** Fixtures with known AR counts per language. Negatives: a single assertion, fluent AssertJ, pytest asserts with messages. Report P/R. The eval should check that the agent calls AR a diagnosability issue, not a false green.

### 3.3 Weak oracle per requirement (mutation-zero, clause-tagged probes)
- **They do better.** test-fidelity-long-run attaches each behavioural probe to a *requirement clause*, documents which weak assertion survives it, calibrates probes against a known-good suite, and runs **mutation zero**: the suite against the code without the change.
- **Assertiva today.**
  - WEAK_ORACLE is static: `effectiveness.py:94-101`.
  - `resolve_with` already says "a mutant of the checked behavior".
  - `mutation_contribution` (`:162-188`) reads killing tests from reports.
  - There is no "previous revision as the negative control" step, and no clause tagging.
- **Decision: ADAPT-CONCEPT.** That repo has no license, so no code can be used.
- **Changes.**
  1. SKILL.md / TEST_QUALITY.md: name **"mutation zero" (previous-revision control)** as a cheap option for change-scoped audits. Run the new or changed tests against the merge base in a disposable worktree. A test that passes there does not bind to the change (unless the change is a refactor, which must be stated).
  2. Schema: allow a `negative_control` evidence record that names its source (`PREVIOUS_REVISION` | `HAND_MUTANT` | `TOOL_MUTANT`), its target clause/requirement id, and its expected verdict (kill/survive). Expected "survive" is used for refactors, as the harness does at no-code checkpoints (`run.py:530-547`).
  3. Evals: `evals/cases/CHANGE_TEST_DOES_NOT_BIND.md`. A PR adds a feature plus a test that passes on the base revision too. The agent must propose or run the base-revision control and must not accept "new test added" as proof.
  4. The HTML report shows per-requirement probes with killed/survived, and lists survivors classified as suite hole, equivalent, or assertion-cannot-fail. Those are the harness's three survivor classes, and Assertiva can use them as resolution labels for a surviving mutant.
- **Proof.** Fixture repo pairs (base, head). Measure that the engine-side helper which builds the control command is correct. Agent-side, the eval pass rate is scored by the rubric. Do not change rubrics after results.

### 3.4 Pseudo-tested methods (extreme mutation)
- **They do better.** Descartes classifies whole methods as pseudo-tested or partially-tested from extreme mutants. It filters methods where an extreme mutant is meaningless (getters, setters, delegates, constant returns, `hashCode`/`toString`). Its JSON output is machine-readable, and it names the tests per mutation (`detected-by`).
- **Assertiva.**
  - `adapters/mutation.py` reads PIT `mutations.xml`. A Descartes run *is* a PIT run, so its mutants are already readable as per-mutant records, though the operator names differ (`void`, `null`, `empty`…).
  - The Descartes `methods` JSON with classification is **not** read.
  - ROADMAP lists "targeted pseudo-mutation as an explicit hypothesis" as **PLANNED**.
- **Decision: INTEGRATE** (as an input format only; no code linked, so LGPL is not an issue for reading its JSON).
- **Changes.**
  1. `adapters/mutation.py`: add a `_descartes_methods(data)` reader keyed on the schema's `methods[].classification`. Map it to a new per-method record (`PSEUDO_TESTED`, `PARTIALLY_TESTED`), and map the tests from `methods[].tests` and `mutations[].detected-by`.
  2. `effectiveness.py`: add a candidate `PSEUDO_TESTED` with basis **CONFIRMED** (execution showed that no test detected removal of the body). Set `resolve_with` = "equivalence check: does the method have an observable effect in the tested scenarios?". Keep the recommendation "assert the method's effect *or* accept it as not worth testing", which reflects the Vera-Pérez finding that developers often decline to fix these.
  3. In `test_effectiveness.candidates[].kind` of the schema, add `PSEUDO_TESTED` to the description enum text.
  4. HTML: a section "Methods whose body can be removed without any test failing".
  5. Skill: explain that an *Assertiva-proposed* pseudo-mutation (the agent removes a body in a disposable copy) is a HYPOTHESIS until executed. That matches the ROADMAP's wording.
- **Proof.** A golden-file test with a real Descartes `methods.json` from a small sample project. Generate it outside the repo and commit only the JSON, after checking it against the confidentiality gate. Check the classification mapping 1:1. Add a negative: a `not-covered` method must *not* become PSEUDO_TESTED.

### 3.5 Redundancy and distinct contribution
- **They do.**
  - PyNose Lack of Cohesion uses token-cosine similarity with a 0.6 threshold (`LackCohesionTestSmellVisitor.kt:37,48-76`).
  - smelly-test's duplicate detector is vacuous.
  - The research consensus (Shi et al. 2014/2018) is to reduce by killed mutants, and to re-check quality over versions.
- **Assertiva.**
  - REDUNDANCY nominates only identical normalised bodies within a component with the same boundaries, fidelity, level and parameters (`effectiveness.py:112-128`).
  - DUPLICATE_CASES is CONFIRMED for literal rows (`:129-151`).
  - Distinct contribution comes from `killedBy` (`:162-188`).
  This is **stricter and better-founded** than textual similarity. Assertiva explicitly refuses similarity-based removal (eval `REDUNDANCY_NOT_BY_SIMILARITY.md`).
- **Gap.** "Distinct contribution beyond textual similarity" (PLANNED) could use *subsumption*: test A's killed set ⊂ test B's killed set. Today only exclusive kills are listed.
- **Decision: BUILD** (small).
- **Change.** In `mutation_contribution`, add `subsumed_by: {test: [tests whose kill set is a strict superset]}`, labelled INFERRED with the existing note that kills ≠ protection. Do **not** adopt cosine similarity (**REJECT**: Panichella 2022 and the PyNose authors note the gap between this metric and human judgement).
- **Proof.** Unit test with a synthetic `killedBy` matrix. Include a negative in which equal kill sets but different `parameters` must not be called redundant.

### 3.6 Fidelity (declared level vs simulated boundaries)
- **Others.** None of the deep-dived tools models boundaries crossed versus simulated, or the declared level. tsDetect's Mystery Guest exempts `@Mock`/`@Spy` (`MysteryGuest.java:148`), which is the closest it gets. test-fidelity-long-run measures fidelity *dynamically* through behaviour, not structure.
- **Assertiva.** FIDELITY_MISMATCH is IMPLEMENTED across Python, JS/TS and JVM (`effectiveness.py:102-111`). **Assertiva leads here.** Keep it.
- **Gap.** pytest-tidy PTD304 (network-call in a unit test) is the inverse mismatch: a unit-declared test crossing a real boundary. Assertiva has the facts for it (`boundaries − simulated` on `declared_level == UNIT`) but no rule. **BUILD**: an INFERRED "UNIT_CROSSES_BOUNDARY" note under determinism. Proof: fixtures with `requests.get` in a unit test, versus `responses.activate` (negative).

### 3.7 Exception oracles (broad error, raises without match, try/except)
- **They.**
  - pytest-tidy PTD102/103/104: broad, no `match`, multiple statements in a `raises` block.
  - PyNose and JNose flag any `try`. That is noisy, and JNose's ECT is now try-only (`ExceptionCatchingThrowing.java:62-65`).
- **Assertiva.**
  - BROAD_ERROR / SPECIFIC_ERROR oracles.
  - SWALLOWED_EXCEPTION only when the handler ignores the exception *and* it hides assertions, with `finally`-cleanup exempt (`test_facts.py:287-297`). That is more precise than PyNose/JNose by construction.
  - The negative-path dimensions in `pytest_audit.py:102-108`.
- **Gap.** "pytest.raises block with several statements" (PTD104): the expected error may come from setup, not from the action. **BUILD** it as a WEAK_ORACLE detail `RAISES_SPANS_SETUP`. Proof: fixtures with one statement (negative) and setup plus action (positive).

### 3.8 Output format, locations, severity
- **They.** JNose and SNUTS.js emit per-instance line ranges, and SNUTS.js adds severity. tsDetect only emits counts per file, which is worse.
- **Assertiva.** Candidates list test ids. There is no line range per pattern.
- **ADAPT.** Add an optional `detail.locations: [{path, line}]` for FALSE_GREEN patterns so the HTML report can link to them. Do **not** add severity: it would be a hidden score, against Assertiva's "no score" principle.

### 3.9 Generated oracles and LLM refactoring
- TOGA, ATLAS and the SNUTS.js AI refactor generate assertions or patches. The evidence (Liu 2023: 0.38% precision; Hossain 2023: more than 47% false-positive assertions) shows that generated oracles restate the implementation.
- **REJECT** generation in the engine. The skill already says "an oracle derived from the code under test … shares its bugs" (`references/TEST_QUALITY.md:24`). Strengthen that line with these citations, and add the self-referential-oracle check (PLANNED M2) as an agent instruction: "where would this expected value come from if the implementation were wrong?"

### 3.10 Checked coverage and the oracle-slice
- Nobody ships a maintained tool for it. **PLANNED/UNSUPPORTED** in Assertiva.
- **ADAPT-CONCEPT** only: in the skill, "coverage of lines that flow into an assertion" is the right question when line coverage is high. A cheap static proxy is to compare the variables asserted with the values produced by the call under test, which is the M2 "unobserved side effects" item. It stays INFERRED. Do not build a dynamic slicer.

---

## 4. Capability gap matrix (Assertiva)

| Capability | Assertiva status | Evidence | Best external reference |
|---|---|---|---|
| Swallowed exception (false green) | IMPLEMENTED (Py/JS/JVM) | `test_facts.py:287-297`, `:498`, `:671` | pytest-tidy PTD101 |
| Conditional-only assertion | IMPLEMENTED | `test_facts.py:298-299` | PyNose CTL (noisier) |
| Tautology: constant or self-compare | IMPLEMENTED | `test_facts.py:226-239` | tsDetect RedundantAssertion; PyNose |
| Assert-on-tuple, mock no-op assert, mock typo | **UNSUPPORTED** (misclassified as VALUE) | `pytest_audit.py:78-97`, `:226-240` | pytest-tidy PTD002/501/502 |
| `assert x` bare truthiness classed as weak | PARTIAL (counted as VALUE) | `pytest_audit.py:97` | n/a |
| Unawaited async, action without check, snapshot-only | IMPLEMENTED | `test_facts.py:300-308` | SNUTS.js complex snapshot (different) |
| Weak oracle (existence/truthy/status/broad error) | IMPLEMENTED | `effectiveness.py:94-101` | test-fidelity per-clause probes |
| Assertion Roulette | **SPECIFIED, not emitted** | `effectiveness.py:33` with no producer | JNose (per instance), tsDetect |
| Mystery Guest | **SPECIFIED, not emitted** | `effectiveness.py:34` | tsDetect (Android-only) |
| Sleep / fixed wait / retry | IMPLEMENTED | `test_facts.py:240-241, 500, 511, 673` | tsDetect SleepyTest; pytest-tidy PTD301 |
| Excessive mocking | IMPLEMENTED (≥4 doubles) | `test_facts.py:303-304` | smelly-test jest.mock count |
| Fidelity mismatch (declared integration/E2E, all simulated) | IMPLEMENTED | `effectiveness.py:102-111` | none comparable |
| Unit test crossing a real boundary | PLANNED-able (facts exist, no rule) | `TestFacts.boundaries` | pytest-tidy PTD304 |
| Redundancy (identical body) | IMPLEMENTED | `effectiveness.py:112-128` | PyNose cohesion (similarity, rejected) |
| Duplicate parameter rows | IMPLEMENTED (CONFIRMED for literal rows) | `effectiveness.py:129-151` | pytest-tidy PTD603 (mismatch, different) |
| Per-test exclusive mutation kills | IMPLEMENTED | `effectiveness.py:162-188` | EvoSuite assertion minimisation |
| Kill-set subsumption | PLANNED (M2 "distinct contribution") | ROADMAP:114 | Shi et al. 2014 |
| Pseudo-tested methods | PLANNED; PIT mutants readable; Descartes `methods.json` UNSUPPORTED | `adapters/mutation.py` | Descartes |
| Previous-revision negative control ("mutation zero") | UNSUPPORTED as a named protocol; generic negative control SPECIFIED in skill | `TEST_QUALITY.md:59` | test-fidelity-long-run |
| Self-referential oracle detection | SPECIFIED (skill text) / PLANNED (engine) | `TEST_QUALITY.md:24`, ROADMAP:114 | none reliable; TOGA critiques |
| Checked coverage / oracle slice | UNSUPPORTED | n/a | Schuler & Zeller (no maintained tool) |
| Per-instance line locations | PARTIAL (test ids only) | `effectiveness.py:64-74` | JNose, SNUTS.js |
| Autofix / quick-fix | UNSUPPORTED (by design: leads, not edits) | n/a | PyNose, pytest-tidy, SNUTS.js AI |
| Precision/recall measured on labelled fixtures | UNKNOWN (rule unit tests exist; no P/R table) | `tests/test_effectiveness.py` | PyNose (94/95.8), tsDetect (96/97 own benchmark) |

---

## 5. What each does better than Assertiva, how, and how we would prove parity

| Project | Better at | How | How we would prove we matched it |
|---|---|---|---|
| test-fidelity-long-run | Showing a test binds to *the requested change* | Mutation zero (base revision) plus clause-tagged mutation catalogue, calibrated on a known-good suite, with survivors classified | Eval `CHANGE_TEST_DOES_NOT_BIND`; schema `negative_control.source=PREVIOUS_REVISION`; fixture pair where a base-passing test is caught |
| pytest-tidy | Python cannot-fail assertions | AST rules PTD002/501/502; configurable helper list | Labelled Python fixtures, P = 1.0 and R ≥ 0.95 per pattern, ≥10 calibration negatives |
| Descartes | Method-level "tests run it but would not notice its removal" | Extreme mutants plus stop-method filters, then classification | Golden `methods.json` → `PSEUDO_TESTED` candidates, 1:1 mapping test; not-covered negative |
| JNose | Locations and history | Per-instance ranges; git evolution | `detail.locations` populated for FALSE_GREEN patterns; HTML links; snapshot test |
| tsDetect / JNose / PyNose | Breadth of the classic smell catalogue (21 / 17 smells) | Per-smell visitors with thresholds | Deliberately **not** matched: Panichella 2022 shows weak validity. Match only AR, with a P/R fixture table |
| PyNose | IDE inline feedback and quick-fixes | PyCharm inspections | Not a goal (Assertiva is agent-led, not an IDE linter). REJECT |
| TOGA | Proposing concrete oracles | Neural ranking over grammar candidates | Not a goal. Independent studies show 0.38% precision. REJECT |
| Schuler & Zeller | Measuring whether executed code is *checked* | Dynamic slicing from assertions | Not matched. Keep the skill guidance; at most a static INFERRED proxy |

**Calibration negatives Assertiva must keep, because these are where the external tools are known to be wrong:**
- a single assertion is not roulette (Panichella Fig. 1);
- a `throws` clause is not an exception smell (tsDetect `ExceptionCatchingThrowing.java:58`);
- a `try` that asserts on the caught exception is not swallowed (JNose ECT);
- a parenthesised compare with a literal is not redundant (PyNose `:38-61`);
- a magic-number threshold of 0 flags everything (tsDetect #27);
- package-private JUnit 5 tests must be analysed (tsDetect `Util.java:15`);
- per-file state must reset between files (tsDetect #19);
- duplicate detection must compare bodies, not positions (smelly-test).
Each of these should be a negative fixture in `tests/test_effectiveness.py` or `tests/test_probe_boundaries.py` (the latter is untracked in the working tree, so check its scope before adding to it).

---

## 6. Licenses and security notes
- **GPL-3.0:** tsDetect, JNose, jnose-core, SNUTS.js. **LGPL-3.0:** Descartes. **Apache-2.0:** PyNose. **MIT:** pytest-tidy, TOGA, AromaDr. **ISC:** smelly-test. **No license:** test-fidelity-long-run.
- Assertiva is Apache-2.0. **Do not copy GPL code or code with no license.** Reading Descartes' JSON *output* is fine. Concepts are not copyrightable. pytest-tidy (MIT) could be referenced, but writing our own AST checks is trivial and avoids a dependency on a repo with one day of history.
- SNUTS.js runs an LLM refactor that writes files (`lib/ai/refactor-service.ts`). Do not recommend it inside the audit flow: it would modify the system under test.
- Running any of these tools executes JVM, Node or IDE plugins. If Assertiva ever invokes them, it should do so under the existing declared-command safety (`evals/cases/DECLARED_COMMAND_SAFETY.md`). Reading their reports is the safer integration.

---

## 7. Budget, uncertainties, unfinished items
- **Approximate tokens spent:** ~190k, under the 300k target.
- **Unfinished or not investigated:**
  - The full text of the JNose accuracy paper (JSERD) and of the tsDetect FSE demo. Their numbers come from search snippets.
  - Per-project percentages in Vera-Pérez 2019 (not extracted).
  - PyNose `ASE2021` branch CLI, not read.
  - The Pytest-Smell repo, not located.
  - AromaDr, TEMPY, ATLAS, GeMTest and Chrysalis, not cloned.
  - The Spadini 2018 and Bavota 2015 harmfulness claims are cited from memory and should be verified before quoting.
  - test-fidelity-long-run `DESIGN.md` was read only in sections (§11 plus headings).
  - The two suspected bugs (PyNose parenthesised-literal false positive, SNUTS.js file-wide sensitive equality) are **from reading, not execution**. They need a fixture run in a disposable environment before being stated as facts.
  - Whether "test-fidelity" in the brief means `officefloor/test-fidelity-long-run` is my inference (§0).
