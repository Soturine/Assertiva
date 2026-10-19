# Competitive research — test result analysis, reporting, observability, portable formats

> Recovered by the orchestrator from the research agent's final message (the agent could not write files). Text kept as the agent returned it; not re-verified except where the consolidated research document says so.

Date: 2026-10-19. Read-only shallow clones under `scratchpad/research-src/reporting\` with short directory names: `rpa`, `rpdao`, `al2`, `al3`, `alpy`, `ctrf-io_ctrf`, `otel`. Long names broke the first clones on Windows path length. Nothing from the clones was installed, built or run. About 100k tokens spent of 250k.

Legend: **CONFIRMED-IN-CODE** = read in the cloned source at path:line. **DECLARED-ONLY** = docs or marketing. **INFERRED** = the agent's own reading.

| Project | Repo | SHA | Last commit | License |
|---|---|---|---|---|
| ReportPortal auto-analyzer | github.com/reportportal/service-auto-analyzer | 2afcf26a09ea3a6b3659eed5274cd10492d92678 (VERSION 6.0.0) | 2026-10-19 | Apache-2.0 |
| ReportPortal data model | github.com/reportportal/commons-dao (sparse `entity/`) | 7d8f0b28326be362fcccd79e63ca0c9d98740bf1 | 2025-11-04 (default branch may be stale) | Apache-2.0 |
| Allure 2 | github.com/allure-framework/allure2 (sparse) | b2c4f3635fde6b4f142492f5400539850ac502db | 2026-09-03 | Apache-2.0 |
| Allure 3 | github.com/allure-framework/allure3 (sparse core-api/core/reader/ci) | f2be44e48ef9a61a88edc951b0061ecde2705c00 | 2026-10-19 | Apache-2.0 |
| allure-python | github.com/allure-framework/allure-python | 4a1f03a47b45bde572672df85cac35e671f58b98 | 2026-10-11 | Apache-2.0 |
| CTRF | github.com/ctrf-io/ctrf | e325eb33c7662a208bfa4d093a41cc55439d6e6a (spec 0.2.0 Working Draft) | 2026-10-10 | MIT |
| OTel semconv | github.com/open-telemetry/semantic-conventions (sparse) | 331541c4057c53d133c32efadaa7b656636eda77 | 2026-10-15 | Apache-2.0 |

## Summary
1. Surefire retries are misread: `assertiva/adapters/junit.py` only reads `failure`, `error` and `skipped`; a Surefire flaky case (`flakyFailure`/`flakyError`) comes in as a clean PASSED. (Orchestrator check: true for `--junit-xml` imports and the Gradle path; the Maven adapter already handled it. Fixed in 0.7.3.)
2. Assertiva's flakiness rules are already stronger: `history.classify` compares only runs of the same revision and environment; Allure 2 (last 5 runs), Allure 3 (tri-state) and ReportPortal history ignore the commit.
3. ReportPortal auto-analysis: OpenSearch candidates, 42 features in [0,1], XGBoost picks the best positive match and copies its defect type — label transfer, not cause.
4. ReportPortal loads models with `pickle`: reject the ML; keep label reuse by failure fingerprint as INFERRED (E3) suggestions in M6.
5. CTRF 0.2.0 (MIT, working draft): report/run/test/execution/attempt/shard ids and `retryAttempts`; its flaky rule equals OBSERVED_UNSTABLE_CURRENT_RUN; it carries no provenance or trust data.
6. CTRF: build ingest and export; export puts tier, revision identity and report digest in `extra.assertiva`, never findings in `ai`/`insights`.
7. allure-results: ingest; real identity (testCaseId + parameter hash), fixture containers, grouped retries; flaky/known flags are only the producer's declaration.
8. Allure 3 quality-gate rules (`minTestsCount`) and known-issue files (issue/muted/accepted, comment mandatory) are worth borrowing in M6; a known issue never moves a failure to Confirmed.
9. OpenTelemetry: test attributes at "development" stability, no test spans/retries/identity — align provenance field names only, no OTLP.
10. Closed tools (Datadog, Trunk, Codecov, BuildPulse, Tesults): documentation only. Datadog/Trunk define flaky per commit; hosted dashboards and quarantine are non-goals.

## 1. ReportPortal (deep)
Scope: server platform (Java API, PostgreSQL, OpenSearch, RabbitMQ, Python analyzer): launch/item/log storage, defect-type triage, ML auto-analysis, pattern analysis, unique-error clustering, dashboards. Non-goals observed: no portable export, no commit field in the core model, no judgment of test quality. Maintenance observed: commit on 2026-10-19; models retrained and dated (`res/model/auto_analysis_model_2026-10-01`, `defect_type_model_2026-09-29`, `suggestion_model_2026-10-01`); 51 Python test files.

### 1.1 Data model (CONFIRMED-IN-CODE, commons-dao `src/main/java/com/epam/ta/reportportal/entity/`)
- `launch/Launch.java:71-138`: `uuid`, `name`, `number` (`:97`), `hasRetries` (`:100`), `rerun` (`:103`), `mode` (`:113`), `status`, `retentionPolicy`. No commit/branch/revision field: those are free key/value attributes.
- `item/TestItem.java:68-149`: `uniqueId` (`:105`), `testCaseId` (`:108`), `testCaseHash` (`:111`), `codeRef` (`:77`), `parameters` (`:102`); `path` as PostgreSQL ltree (`:122`); `retryOf` (`:125`), `hasRetries` (`:143`).
- `item/TestItemResults.java:57-74`: `status`, `endTime`, `duration`, `issue`.
- `item/issue/IssueEntity.java:51-64`: `issueType`, `issueDescription`, `autoAnalyzed` (`:61`), `ignoreAnalyzer` (`:64`).
- `enums/TestItemIssueGroup.java:34-40`: PRODUCT_BUG `pb001`, AUTOMATION_BUG `ab001`, SYSTEM_ISSUE `si001`, TO_INVESTIGATE `ti001`, NO_DEFECT `nd001`, NOT_ISSUE flag.
- `enums/StatusEnum.java:25-34`: IN_PROGRESS, PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED, INFO, WARN (INFO and WARN count as positive).
- `enums/TestItemTypeEnum.java:25-39`: suite/test/step plus BEFORE_*/AFTER_* fixtures as items.
- `pattern/PatternTemplateType.java:27-28`: STRING or REGEX patterns.

### 1.2 Auto-analysis (CONFIRMED-IN-CODE unless marked)
Flow: API sends To-Investigate items over AMQP → `app/service/auto_analyzer_service.py` builds one OpenSearch query per item (`_build_item_query` `:138`; `opensearch-py==3.2.0`) → `_filter_by_similarity` (`:165`) → featurizer → XGBoost → `choose_best_prediction` (`:81-90`, highest positive probability, first wins a tie) → `relevantItem` (`:73-77`) supplies defect type, comment and issue link → no positive hit leaves To Investigate (`:385-389`).
Config: `AnalyzerConf` (`app/commons/model/launch_objects.py:32-45`) `minShouldMatch=80`, `numberOfLogLines=-1`, `searchLogsMinShouldMatch=95`, `similarityThresholdToDrop=0.95`; environment (`app/main.py:232-244`) `ES_BOOST_MA=10.0`, `ES_BOOST_AA=0.0`, `ES_TIME_WEIGHT_DECAY=0.999`, `PATTERN_LABEL_MIN_PERCENT=0.9`, `PROB_CUSTOM_MODEL_AUTO_ANALYSIS=0.5`, `PROB_CUSTOM_MODEL_SUGGESTIONS=0.7` (capped 0.8).
Features: 42 (`app/ml/boosting_featurizer.py:161-202`); rules (`app/ml/features.py:1-5`): item data only, values in [0,1], empty equals empty is 0.0. Families: log-field similarity (message, exception, stacktrace, URLs, status codes); `test_case_hash` and launch equality; defect-type model output (`:175`); manually-analyzed flag; time decay (`:362`), launch-number distance (`:394`); label-history stability 1 − (distinct − 1)/(n − 1) (`:423-434`), history unchanged (`:437`); issue-type consensus 1 − normalized entropy (`:459-474`); identifier Jaccard (`:477-496`); forward/reverse log coverage (`:523-552`).
Model: `XGBClassifier` (`app/ml/models/boosting_decision_maker.py:18,61`); fallback similarity predictor threshold 0.5 (`app/ml/predictor.py:333-389`).
Clustering: `app/commons/clustering.py:31-111` MD5 of word 2-grams, 64 largest, grouped at 0.95; `app/service/cluster_service.py:81-111` regroups by error and status codes.
Docs (DECLARED-ONLY, https://reportportal.io/docs/analysis/AutoAnalysisOfLaunches/): five analysis bases; only items with ERROR logs analyzed; "Ignore in AA"; docs say ~30 features and ≥50% (stale vs code). Pattern analysis (https://reportportal.io/docs/analysis/PatternAnalysis/) adds a "PA" label without changing defect type.

### 1.3 Inputs and outputs
Input: live agent API, or JUnit/Robot XML zip import (≤32 MB; skipped become To Investigate unless `skippedIsNotIssue=true`) — DECLARED (https://reportportal.io/docs/log-data-in-reportportal/ImportDataToReportPortal/). Output: UI and REST JSON; no portable export; analyzer publishes `AnalysisResult` JSON on AMQP.

### 1.4 Quality and security
`pickle.load`/`pickle.loads` for models (`app/commons/object_saving/filesystem_saver.py:63`, `blob_storage.py:99`): loading a model can run code. No published precision/recall per release (not verified).

### 1.5 Not investigated
service-api history, retry merge, launch merge; query_builder analysis bases.

Takeaway: reuse of human triage; AA is a transferred label, recorded as `autoAnalyzed`. Adaptable ideas: "empty never matches"; weigh a suggestion by the stability of the matched item's label history.

## 2. Allure (deep)
### 2.1 allure-results (CONFIRMED, `allure-python-commons/src/allure_commons/model2.py`)
Files (`:5-8`): `{uuid}-result.json`, `-container.json`, `-attachment.{ext}`, `-globals.json`. `TestResult` (`:44-54`): `uuid`, `historyId`, `testCaseId`, `fullName`, `labels`, `links`, `titlePath`. `ExecutableItem` (`:29-40`): `status`, `statusDetails`, `stage`, `steps`, `attachments`, `parameters` (`excluded`, `mode`), `start`, `stop`. `StatusDetails` (`:93-97`): `known`, `flaky`, `message`, `trace` (declared by the producer; allure-pytest never sets them). Status (`:125-130`): failed, broken, passed, skipped, unknown. Containers (`:13-25`): befores/afters. Identity in allure-pytest: `testCaseId = md5(fullName)` (`allure-pytest/src/listener.py:112-114`); `historyId = md5(fullName + sorted non-excluded params)` (`allure-pytest/src/utils.py:213-223`).

### 2.2 Allure 2 generator (CONFIRMED)
`retryHash = md5(testCaseId or fullName) + "." + md5(params)` (`allure-plugin-api/.../entity/TestResult.java:89-93`, `allure-generator/.../allure2/Allure2Plugin.java:215-247`; old `historyId` kept as `legacyHistoryId` `:258`). Retries (`retry/RetryPlugin.java:51-103`): latest visible, earlier `retry=true`, `retriesStatusChange`. History (`history/HistoryPlugin.java:52-190`): previous `history.json` by retryHash, 20 items (`:178-180`); `newFailed/newBroken/newPassed` vs last significant status (`:97-107`); flaky = current FAILED/BROKEN and a PASSED before the last FAILED in the last 5 (`:109-125`), OR producer flag (`:173`); no commit or environment key. Categories (`category/CategoriesPlugin.java:71-180`): "Product defects" (failed), "Test defects" (broken); custom by status + full-match regex + flaky.

### 2.3 Allure 3 (CONFIRMED)
Model (`core-api/src/model.ts:5-111`): `flaky`, `muted`, `known` (`:87-89`), `transition` (`:93`), `retryHash` (`:95`), `retries[]` (`:111`), `environment`/`environmentHash` (`:69-74`); producer flaky kept apart (`:37-38`); MD5 identity (`core-api/src/utils/identity.ts:32-85`). Flakiness tri-state (`core-api/src/utils/flaky.ts:20-65`): `historyDepth=10`, `stabilizationPeriod=5`, undefined = not enough evidence, stops at a missing run, ≤1 change after the latest stable streak = stable, P→F→P tolerated as recovery; detector flags only failed/broken (`core/src/utils/flaky.ts`). New/transitions (`core/src/utils/new.ts`). History store JSONL (`core/src/history.ts:165-370`); `HistoryDataPoint` (`core-api/src/history.ts:33-41`). Not keyed by commit: `GitFacts` (`core-api/src/gitFlow.ts`) only for TestOps upload. Known issues (`core-api/src/resolutions.ts`): match by message regex, `testCaseId[]`, `retryHash[]`, `environment[]`; resolution issue/muted/accepted, muted/accepted need a comment. Quality gate (`core/src/qualityGate/rules.ts:127-367`): maxFailures, minTestsCount, newTests, successRate, maxDuration, allTestsContainEnv, environmentsTested, metric rules (whether maxFailures excludes muted/known: not traced). Readers: allure1/2, cucumber JSON/messages, JUnit XML, xcresult. 294 `*.test.ts` files including flaky and history tests.

## 3. CTRF (deep)
Schema (CONFIRMED, `schema/ctrf.schema.json`, draft-07): root requires `reportFormat` ("CTRF") and semver `specVersion`; optional `results`, `reportId`, `runId`, `timestamp`, `generatedBy`, `insights`, `baseline{reportId, commit, …}`, `extra`. `results` requires `tool`, `summary` (tests, passed, failed, skipped, pending, other, start, stop; optional flaky), `tests[]`; `results.environment` optional commit, branchName, buildUrl, repositoryUrl, shardId, `healthy`. Test requires `name`, `status` (passed/failed/skipped/pending/other, `:166-168`), `duration`; identity `testId`, `executionId`, `attemptId`; `retries`, `retryAttempts[{attempt, status}]` (`:268-289`), `flaky`; also `rawStatus`, `filePath`, `line`, `parameters`, `steps`, `attachments`, `insights`, `ai` (§9.13).
Spec (`spec/ctrf.md`): identity model §4.9 (`:434-486`) document/run/test/execution/attempt/shard, no derivation or trust metadata; flaky (`:313`, `:1123`) = passed after ≥1 failed attempt in the run; `testId` derived from file, suite, name (Appendix B); `examples/with-retries.json` says 0.1.0 vs spec 0.2.0; normative JSON suites in `tests/normative/`.

## 4. OpenTelemetry CI/CD and tests (CONFIRMED)
`model/test/registry.yaml:2-76` (development): `test.suite.name`, `test.case.name`, `test.suite.run.status`, `test.case.result.status`; no test spans/events. CI/CD spans (`model/cicd/spans.yaml:2-43`, release_candidate): `span.cicd.pipeline.run.server`, `span.cicd.pipeline.task.internal`; `cicd.pipeline.*`, `cicd.worker.*`, `cicd.system.component`. VCS (`model/vcs/registry.yaml:9,97,126,209`): `vcs.ref.head.revision`, `vcs.ref.head.name`, `vcs.repository.url.full`, `vcs.change.id`. Missing: retries, case-level skip, identity, flaky.

## 5. Peripheral (docs only; algorithms are hypotheses)
- Datadog Test Optimization: flaky = passes and fails on the same commit; `is_flaky`, `is_new_flaky`, `is_known_flaky`; default branch over 5,000 commits; Active/Quarantined/Disabled/Fixed (30 days); "Attempt to Fix" 20 reruns; identity hash of repo id + FQ name. https://docs.datadoghq.com/tests/flaky_test_management/ , https://docs.datadoghq.com/tests/flaky_management/
- Trunk Flaky Tests: Pass-on-Retry (same commit), Failure Rate, Failure Count; Broken > Flaky > Healthy; environment variants as separate cases; muting 1 h–30 days. https://docs.trunk.io/flaky-tests/detection
- Codecov Test Analytics: JUnit only; failure rate, commits failed, "known flaky on main"; rule undocumented; 60-day retention. https://docs.codecov.com/docs/test-analytics
- BuildPulse: JUnit upload, method undocumented. https://docs.buildpulse.io/
- Tesults: hosted upload API, no flaky semantics found. https://npmjs.com/package/tesults
- Sonar generic test execution: no identity or retries. https://docs.sonarsource.com/sonarqube-server/latest/analyzing-source-code/test-coverage/generic-test-data/
- TAP 14: missing plan = failure; `1..0` all skipped; TODO/SKIP; YAML; subtests; Bail out. https://testanything.org/tap-version-14-specification.html
- JUnit XML variants: no official spec (https://github.com/testmoapp/junitxml); Surefire rerun elements (https://maven.apache.org/surefire/maven-surefire-plugin/examples/rerun-failing-tests.html): `flakyFailure`/`flakyError` failed then passed (time = last successful run); `rerunFailure`/`rerunError` failed every time, first failure stays in `failure`.
- Found, not investigated: Develocity flaky detection, CloudBees Smart Tests, dorny/test-reporter, Currents, Testmo, Allure TestOps.

## 6. Ingest and export for Assertiva
Every imported format: file E0 by bytes (path, sha256, `provenance: EXTERNAL_UNVERIFIED`); invocations E1 relative to the file, never to the revision; producer flags (flaky, known, muted, AA, CTRF `ai`/`insights`) E2 at best, shown as "the report says", never feeding `Stability`; a commit inside a results file is declared ("declared same revision"), weaker than an executed run.
- 6.1 allure-results — ingest (ADAPT; new `assertiva/adapters/allure_results.py`): result + container JSON; attachments by name/size, never resolve `source` outside the dir; failed fixture containers → setup ERROR; failed→FAILED, broken→ERROR, skipped→SKIPPED, unknown raw; invocation = fullName+params, declaration = testCaseId or fullName; retries by retryHash through `classify_attempts` keeping the first failure; labels/links E2. Lost: revision, coverage, xfail, wall clock. Must not claim Allure-history flaky/newFailed for this revision or `known` as accepted risk.
- 6.2 CTRF — ingest (`assertiva/adapters/ctrf.py`) and export (`--ctrf-out`, `assertiva/export_ctrf.py`): validate const/semver; pending→SKIPPED raw kept; `retryAttempts`→attempts; `testId` declaration only when present; `environment.commit` declared; merge shards by `runId`/`shardId`, refuse different `runId`s; `insights`/`ai` unverified. Export: `generatedBy` Assertiva, `environment.commit` audited revision, `extra.assertiva` {evidence_tier, revision_identity, provenance, report_sha256}, first failure kept, `flaky` only for fail→pass observed in this run, no findings in `ai`/`insights`; lost: claim boundary, unknowns, findings, decision layer (labelled as results interchange).
- 6.3 ReportPortal: ingest REJECT (API + credentials contradict "read, never fetch"); a user-exported item JSON could map later (PLANNED at most after M6); no RP writer (RP imports JUnit).
- 6.4 OTel CI/CD: ADAPT-CONCEPT (document provenance ↔ OTel names); OTLP UNSUPPORTED/REJECT for now.

## 7. Comparison and decisions
1. Retry semantics in imports — BUILD (small): parse `flakyFailure`/`flakyError` and `rerunFailure`/`rerunError`; proof: fixture XML in `tests/test_junit.py`. (Done in 0.7.3 for attempts and messages; the history classification of imported runs is not wired.)
2. Declaration identity in imports — BUILD: `allure_results.py`, `ctrf.py`, `--allure-results DIR`, `--ctrf FILE` (`cli.py:254`); golden fixtures incl. retries, failed container, malformed JSON, attachment traversal.
3. Portable export — INTEGRATE format, BUILD writer (`export_ctrf.py`); schema may be vendored only with its MIT notice; proofs: round trip, schema validation, no finding text leaked.
4. Tri-state flakiness — ADAPT-CONCEPT: "recovered after a fix" across revisions as a separate signal in M6.
5. Reusing past triage — ADAPT-CONCEPT, REJECT ML/OpenSearch/pickle: label per fingerprint in `history.py` SQLite, suggested as E3 with citation, flagged when labels flip, never auto-applied.
6. Clustering — BUILD in M6, deterministic "related" level (stage, exception type, location) as E3, measured on a labeled corpus first.
7. Categories/known issues — ADAPT-CONCEPT: optional known-issues file (match by invocation/fingerprint/environment, issue|accepted, mandatory reason, optional expiry), never Confirmed, expired rules reported.
8. Vacuous green — IMPLEMENTED (no executed cases → UNKNOWN); optional `--min-executed`.
9. New/recurring/fixed — BUILD in M6 (`history.summarize` transitions with cited state and revision).
10. Provenance names — IMPLEMENTED; OTel aliases in schema `provenance`.
11. Hosted dashboards, ML triage, quarantine — REJECT (non-goal).
Claims Assertiva must never import: "flaky" from another tool's history; AA labels, CTRF `ai` or categories as causes; CTRF `insights`/pass rates; a commit inside a results file as observed; summed durations as run duration.

## 8. Capability gap matrix (RP / Allure 2 / Allure 3 / CTRF / OTel / Assertiva)
- Ingest JUnit: IMPL(docs) / IMPL / IMPL / n/a / n/a / IMPLEMENTED
- Surefire rerun elements: UNKNOWN / UNKNOWN / UNKNOWN / n/a / n/a / UNSUPPORTED → PARTIAL in 0.7.3 (attempts and messages)
- Ingest allure-results: UNSUPP / IMPL / IMPL / n/a / n/a / UNSUPPORTED
- CTRF ingest/export: UNKNOWN / UNSUPP / UNKNOWN / SPECIFIED / n/a / UNSUPPORTED
- Stable identity with params: IMPL / IMPL / IMPL / SPECIFIED / UNSUPP / PARTIAL
- Within-run retries keeping the first failure: IMPL / IMPL / IMPL / SPECIFIED / UNSUPP / IMPLEMENTED native, PARTIAL imports
- Cross-run flakiness: UNKNOWN / IMPL (not revision-scoped) / IMPL tri-state / SPECIFIED / UNSUPP / IMPLEMENTED (revision + environment)
- New/recurring/fixed: PARTIAL / IMPL / IMPL / UNSUPP / UNSUPP / PLANNED (M6)
- Fingerprint or clustering: IMPL / UNSUPP / UNSUPP / UNSUPP / UNSUPP / PARTIAL
- ML auto-triage: IMPL / – / – / – / – / UNSUPPORTED by design
- Categories/known issues: IMPL / IMPL / IMPL / UNSUPP / UNSUPP / PARTIAL (dispositions)
- Product vs test vs infra: IMPL / PARTIAL / PARTIAL / UNSUPP / UNSUPP / PLANNED
- Revision identity of evidence: UNSUPP / UNSUPP / PARTIAL / SPECIFIED / SPECIFIED / IMPLEMENTED
- Evidence tier / claim boundary: PARTIAL / UNSUPP / UNSUPP / UNSUPP / UNSUPP / IMPLEMENTED
- Vacuity guard: UNKNOWN / UNSUPP / IMPL / UNSUPP / UNSUPP / IMPLEMENTED
- Offline single report: UNSUPP / IMPL / IMPL / n/a / n/a / IMPLEMENTED
- Dashboards/trends: IMPL / IMPL / IMPL / SPECIFIED / n/a / UNSUPPORTED (non-goal)
- OTel export: UNKNOWN / UNSUPP / UNKNOWN / UNSUPP / SPECIFIED / UNSUPPORTED

## 9. Suggested order
1. Surefire rerun elements in `junit.py` (done in 0.7.3). 2. CTRF ingest/export. 3. allure-results ingest. 4. M6 transitions, fingerprint label memory, known-issue file. 5. Eval cases (budget approval first): imported flaky JUnit; CTRF commit ≠ HEAD; Allure history flaky vs same-revision pass; accepted known issue never Confirmed.

## 10. Uncertainties and unfinished
RP service-api not read; commons-dao default branch may be stale; Allure 3 maxFailures vs muted/known, single-file mode and JUnit reader for Surefire rerun elements not read; closed tools from docs only; no tool executed (RP accuracy not measured).
