# Browser/E2E, mobile, contract verification, disposable real dependencies, accessibility: source-level research

Date: 2026-10-19. Cluster: tools whose **results** Assertiva should consume and whose semantics it must not misstate. Clones live under `scratchpad/research-src/e2e/<project>` and are depth-1, blob-filtered, sparse. Nothing was installed, built or run from them, and their content was read as untrusted data. Paths below are relative to each clone root.

Status labels:
- **CONFIRMED-IN-CODE**: read in source at the stated SHA.
- **DECLARED-ONLY**: stated in docs or project metadata, or recalled and not verified in code here.

## 0. Sources and identity

| Project | URL | SHA (HEAD, depth 1) | Commit date | License (file read) | Maintenance observed |
|---|---|---|---|---|---|
| Playwright | github.com/microsoft/playwright | `41e6a18b3bfc57f566e3cb0829f23a7a5eaad21b` | 2026-10-19 | Apache-2.0 (`LICENSE`) | commit same day |
| Cypress | github.com/cypress-io/cypress | `30a4d03221676dc8ede0aa55e63560f38fa78a93` | 2026-10-19 | MIT (`LICENSE`) | commit same day |
| axe-core | github.com/dequelabs/axe-core | `f01bf5ce56ffcf1411d14d14ed75d1fb86f8023c` | 2026-10-15 | **MPL-2.0** (`LICENSE`) | active |
| Pact (Rust core: verifier + models) | github.com/pact-foundation/pact-reference | `078e70512684cbe059f90ca4db4439e659e217cb` | 2026-10-17 | MIT (`LICENSE`) | active |
| Testcontainers Java | github.com/testcontainers/testcontainers-java | `6cc7f8ddf4f882c8b3dc1de00ae08c5666a60bfe` | 2026-10-18 | MIT (`LICENSE`) | active |
| Schemathesis | github.com/schemathesis/schemathesis | `34636c3afe38373c0b433e7bbfffbb25e49a7a61` | 2026-10-19 | MIT (GitHub API) | active, pushed 2026-10-19 |

Repository metadata fetched through the GitHub API on 2026-10-19:

| Project | Status | License | Last push |
|---|---|---|---|
| Specmatic | active | MIT | 2026-10-19 |
| WireMock | active | Apache-2.0 | 2026-10-19 |
| pa11y | active | **LGPL-3.0** | 2026-10-19 |
| Dredd | **archived** | MIT | last push 2024-05-11 |
| Spring Cloud Contract | **archived** | Apache-2.0 | last push 2026-07-06 |

Primary web sources:
- https://docs.pact.io/pact_broker/can_i_deploy
- https://github.com/pact-foundation/pact_broker-client (README, can-i-deploy options)
- https://developer.android.com/studio/test/gradle-managed-devices
- https://developer.chrome.com/docs/lighthouse/accessibility/scoring
- https://testing-library.com/docs/queries/about#priority
- the axe-core `README.md` and `doc/API.md` in the clone

Licensing for Assertiva (Apache-2.0):
- **Reading result files** creates no license obligation for any of these tools.
- **axe-core is MPL-2.0.** It is file-level copyleft, so do not vendor or modify axe sources. Consuming its JSON output is fine.
- **pa11y is LGPL-3.0.** Ingest its output only and never bundle it.

---

## 1. Playwright Test: JSON reporter, outcomes, retries, trace (deep)

### Scope and non-goals
Playwright Test is a test runner for browsers it manages: Chromium, Firefox and WebKit, through projects.

Non-goals:
- The JSON reporter is not a provenance record. It has **no run-level status** and no browser version.
- The JSON reporter is not a coverage tool.

### Architecture and flow (examined)
The runner calls the reporter hooks `onConfigure`, `onBegin`, `onTestEnd` and `onEnd`. On `onEnd`, `JSONReporter._serializeReport` writes the report.

Examined files:
- `packages/playwright/src/reporters/json.ts:1-274` (whole file)
- `packages/playwright/src/reporters/base.ts:393-415`
- `packages/playwright/src/common/test.ts:275-335`
- `packages/playwright/src/isomorphic/teleReceiver.ts:861-903`
- `packages/playwright/types/testReporter.d.ts:225-360` and `:780-800`
- `packages/playwright/src/plugins/gitCommitInfoPlugin.ts:45-125`
- `packages/isomorphic/trace/versions/traceV10.ts:86-98`
- `packages/playwright-core/src/server/trace/recorder/tracing.ts:110-135`

### Output format (CONFIRMED-IN-CODE, `types/testReporter.d.ts:269-360`)

```json
{"config":{"rootDir":"/w","projects":[{"id":"chromium","name":"chromium","retries":2,"repeatEach":1,"testDir":"/w/e2e","outputDir":"/w/test-results","metadata":{},"testIgnore":[],"testMatch":["**/*.spec.ts"],"timeout":30000}], "metadata":{"gitCommit":{}}, "reporter":[["json",{}]]},
 "suites":[{"title":"login.spec.ts","file":"login.spec.ts","line":0,"column":0,
   "specs":[{"id":"…","title":"signs in","ok":true,"tags":["smoke"],"file":"login.spec.ts","line":3,"column":5,
     "tests":[{"projectId":"chromium","projectName":"chromium","expectedStatus":"passed","status":"flaky","annotations":[],"timeout":30000,
       "results":[{"retry":0,"status":"failed","workerIndex":0,"parallelIndex":0,"duration":812,"errors":[{"message":"…"}],"attachments":[{"name":"trace","contentType":"application/zip","path":"/w/test-results/…/trace.zip"}],"startTime":"…","annotations":[],"stdout":[],"stderr":[]},
                  {"retry":1,"status":"passed","…":"…"}]}]}]}],
 "errors":[], "stats":{"startTime":"…","duration":2100,"expected":0,"unexpected":0,"flaky":1,"skipped":0}}
```

### Semantics (CONFIRMED-IN-CODE)

**`test.status`.** This is `TestCase.outcome()` (`json.ts:200` → `test.ts:305` → `teleReceiver.ts:861-903`). It is computed over all results:
- An `interrupted` result counts in neither the expected nor the unexpected tally.
- `skipped` with `expectedStatus=skipped` counts as *skipped*.
- `skipped` when the test was expected to run counts as **didNotRun**. The upstream comment at `teleReceiver.ts:874-880` lists the causes: early stop (maxFailures), or a failed earlier test in a serial suite.
- `status == expectedStatus` counts as *expected*. Anything else counts as *unexpected*.

The final verdict:
- **`skipped`** when there were no expected and no unexpected results. The comment says "all results were skipped or interrupted", so an interrupted-only test, or a test that did not run, is reported as `skipped`.
- `expected` when nothing was unexpected.
- `unexpected` when there were only failures.
- **`flaky`** in every other mix: expected+unexpected **or skipped+unexpected**.

**`expectedStatus`.** It becomes `skipped` for `skip`/`fixme` and `failed` for `fail` (`test.ts:325-332`).

**`ok`.** It is `true` for expected, flaky and skipped outcomes (`test.ts:309-312`). So `ok: true` does not mean "ran and passed".

**`stats`.**
- `stats` counts outcomes over the **filtered** test set (`json.ts:89-99`).
- When the reporter option `onlyFailures` is set, the filter is `isFailure` (`base.ts:393-402`). The report then contains only `unexpected`, `flaky` and interrupted tests, and passing tests are absent.

**Run status.** The run-level `FullResult.status` (`passed|failed|timedout|interrupted`, `testReporter.d.ts:32`) is **not serialized**. `json.ts:85-96` puts only `startTime` and `duration` into `stats`. A global timeout or interrupt can therefore be invisible apart from individual results.

**Attachments.** They carry `path` or an inline base64 `body` (`json.ts:219-224`). An inline body can carry secrets.

**Reporter `preprocess` hook.** The hook (`testReporter.d.ts:225-250`, `:780-800`) lets a reporter **skip, fixme or mark-failing** tests and disable sharding before the run. A third-party reporter can therefore change `expectedStatus`.

**Config metadata.** `config.metadata` may contain `gitCommit` and `gitDiff`, captured by default on CI (`gitCommitInfoPlugin.ts:55-67`). Through the `%ce` format (`:123-124`) that includes committer name and email. This is useful as a provenance claim (E2: declared by the producer), but it holds personal data and a full diff.

**Trace.** A trace zip contains `trace.trace` JSON-lines. The first event is `context-options` with `browserName`, `channel`, `playwrightVersion`, `platform` and `origin` (`traceV10.ts:86-98`, `tracing.ts:117-135`). The trace format version is `10` (`trace.ts:59`). This is the only artifact in the cluster that proves *which real browser engine* executed.

### Gaps in Assertiva's current adapter (`assertiva/adapters/playwright.py`)

1. **`playwright.py:164`** maps every `status == "skipped"` to `Outcome.SKIPPED`. Two cases are wrong:
   - A skipped test with `expectedStatus != "skipped"` is upstream's *didNotRun*. It should be `NOT_RUN` (for example "not executed: run stopped early or serial predecessor failed").
   - A test whose only results are `interrupted` also arrives as `skipped`. The `interrupted` branch at `:176` is effectively unreachable in that case.

   Fix: check `expectedStatus` and the per-result statuses before the `skipped` branch.
2. **`playwright.py:170-173`** treats every `flaky` test as "passed after N attempts". Upstream `flaky` also covers **failed then skipped** (skipped+unexpected). Fix: use the last non-skipped result, and do not claim a pass unless a result with `status == expectedStatus` exists.
3. **External JSON reports are not checked for `onlyFailures`.** When a JSON report is ingested instead of produced by Assertiva, check `config.reporter` for `onlyFailures: true`. If it is set, mark the run partial ("passing tests omitted by the producer") and never count absent tests as not-selected.
4. **No run-level status.** Record the limitation "JSON report has no run status; a global timeout or interrupt is visible only per test".
5. **Real browser not proven.**
   - Project names alone infer the engine (E3). A `trace.zip` attachment, when present, gives E0 `browserName`, `channel` and `playwrightVersion`.
   - Read only the first JSON line of `trace.trace`, in a bounded zip read with no extraction to disk.
6. **Do not copy `config.metadata.gitDiff` or `gitCommit` author fields into the report.** Keep only `gitCommit.hash` as a *declared* revision. Compare it with the audited tree digest or VCS revision. A mismatch means the result is cross-revision.

---

## 2. Cypress (deep on result shape)

Examined files:
- `packages/server/lib/modes/results.ts:20-140, 203`
- `cli/types/cypress-npm-api.d.ts:181-325`
- `packages/server/lib/modes/run.ts` (grep for `skippedSpec`)

### Output format (CONFIRMED-IN-CODE)
`cypress run` returns, through the Module API, a `CypressRunResult`:
- Run level: `browserName`, `browserVersion`, `browserPath`, `cypressVersion`, `osName`, `osVersion`, and the totals `totalPassed`, `totalFailed`, `totalPending`, `totalSkipped` (`cypress-npm-api.d.ts:279-302`).
- `runs[]`: `spec`, `stats {passes, failures, pending, skipped, …}`, `tests[]`, `screenshots`, `video`.
- Each test: `{title: string[], state, displayError, attempts: [{state}], duration}`.

A failed launch returns `{status: "failed", failures, message}` (`:318-322`).

Example:

```json
{"browserName":"electron","browserVersion":"…","cypressVersion":"15.x","totalTests":2,"totalPassed":1,"totalFailed":0,"totalPending":1,"totalSkipped":0,
 "runs":[{"spec":{"relative":"cypress/e2e/login.cy.ts"},"stats":{"passes":1,"failures":0,"pending":1,"skipped":0},
  "tests":[{"title":["login","signs in"],"state":"passed","attempts":[{"state":"failed"},{"state":"passed"}],"displayError":null}]}]}
```

### Semantics
- **Retries.** Retries are visible only as `attempts[].state` (`results.ts:101`). Flaky is *derived*: final state `passed` with some earlier attempt `failed`.
- **No source line or test id.** Tests are identified only by title path plus spec file.
- **Pending vs skipped (DECLARED-ONLY, Mocha semantics).** `pending` is `it.skip` or a test with no body. `skipped` means the test did not run because a hook failed. Upstream fields: `results.ts:58-63`.
- **`skippedSpec` is dropped.** The internal `RunResult.skippedSpec` (`results.ts:55`) is not copied by `createPublicRun` (`:109-134`). A spec skipped wholesale (for example by Cloud auto-cancel) therefore shows only as zero tests.
- **Usual output.** This result exists only through the Module API, so the common artifacts are JUnit XML and mochawesome JSON from reporters. Those are lossier still: they have no attempts and no browser version.

### Ingestion
- **JUnit route.** Use the existing `assertiva/adapters/junit.py`, with the limitations "retries not visible" and "browser not identified".
- **Module API route.** If a Module-API results JSON is present (projects sometimes `writeFile` it), add a small `cypress_results.py` parser.
  - `pending` → SKIPPED.
  - `skipped` → NOT_RUN ("hook failure prevented execution").
  - Final `passed` with an earlier `failed` attempt → PASSED with attempts > 1 and the retried limitation, as Playwright handles it.
  - Engine: `browserName` is E0 from the producer, but **Electron is Chromium embedded in Cypress, not a shipped browser**. Report it as the engine "chromium (electron)".
- **`cy.intercept` stays the static fact already in `test_facts.py`.** Results do not say whether a test's network was stubbed.

---

## 3. Testing Library (docs; peripheral but semantic)

Source: https://testing-library.com/docs/queries/about#priority (DECLARED-ONLY).

**Priority order:**
1. Accessible to everyone: `ByRole`, `ByLabelText`, `ByPlaceholderText`, `ByText`, `ByDisplayValue`.
2. Semantic: `ByAltText`, `ByTitle`.
3. Test IDs: `ByTestId`.

**Variant semantics:**
- `getBy*` **throws on zero or multiple matches**, so it is itself an existence and uniqueness oracle.
- `queryBy*` returns null and is not an oracle unless asserted.
- `findBy*` is async and retries until a timeout.

**Implication for Assertiva:**
- The `test_facts.py` treatment ("Testing Library queries as existence oracles") is correct for `getBy` and `findBy`, and must not be applied to `queryBy`.
- `getByRole(name)` is evidence of an accessible-name contract for **that element only**. It is not an accessibility claim.

---

## 4. Android: Espresso, Compose UI test, Robolectric, Gradle Managed Devices

Nothing was cloned for this section: AGP sources are not on GitHub in a sparse-clonable form.

### What each tool produces

| Tool | Where it runs | What it produces | What the result says about the device |
|---|---|---|---|
| Robolectric | JVM, simulated Android framework | Standard Gradle JUnit XML under `build/test-results/test<Variant>UnitTest/`, the same as a plain unit test | Nothing. Only the source shows it was simulated. This is why Assertiva's lexical fact "Robolectric = simulated DEVICE" is the only possible signal (E3). |
| `connectedAndroidTest` (Espresso or Compose on a real device or emulator) | real device or emulator | JUnit-style XML under `build/outputs/androidTest-results/connected/…/TEST-<device>-<module>-<flavor>.xml` | Device in the file name. **UNKNOWN / not verified here:** the `<properties>` block with `device`/`flavor`/`project` is recalled, not verified. A separate report says the device may appear only in the file name. |
| Gradle Managed Devices (`<device>Check`, `allDevicesCheck`) | managed emulator | Gradle docs mention an HTML report path and **one `.proto` file per shard** for sharded runs, but give no exact paths. Some flows use the Unified Test Platform `test-result.pb`. | Declared in configuration: `device`, `apiLevel`, `systemImageSource` (`aosp`, `google`, `aosp-atd`, `google-atd`). **ATD images are headless and disable hardware rendering**, so screenshot tests that need it are unsupported. (DECLARED-ONLY, developer.android.com) |
| Firebase Test Lab through GMD | remote devices | Results in a GCS bucket | Real remote devices. Out of local scope, and a consent/network boundary. |

### Assertiva today
`gradle.py` lists instrumented tests as NOT_RUN. That is correct, because Assertiva starts no emulator.

### What would be needed: ingestion of existing connected or GMD XML
Read the XML with `junit.py` and tag the run with an execution target:
- `EMULATOR` when the device comes from GMD configuration, or from a file name like `emulator-5554`.
- `DEVICE` when the device is a serial or a Firebase Test Lab device.
- `UNKNOWN` otherwise.

That target is E2 (declared) at most. The XML cannot distinguish an emulator from hardware reliably. Freshness is unknown: the build-output timestamp is not revision identity, so the result is "ingested, revision not verified", as done for coverage today (`report.py:249`).

---

## 5. Pact (deep: verifier result and pact file; Broker from docs)

### Scope
- **Consumer side.** Consumer tests run against a Pact *mock server*, which is a simulated HTTP boundary. They emit a **pact file**.
- **Provider side.** Provider verification replays each interaction against the **real provider** (a running process), sets up provider states through a callback, and compares responses.
- **Broker.** The Broker stores pacts and verification results and answers `can-i-deploy` from a version matrix.

Examined files:
- `rust/pact_verifier/src/verification_result.rs:10-200, 395-464`
- `rust/pact_verifier/src/lib.rs:645-680, 820-1000, 1115-1262`
- `rust/pact_verifier/src/pact_broker.rs:975-1095`
- `rust/pact_models/src/v4/pact.rs:200-221, 700-800`

### Pact file (V4; CONFIRMED-IN-CODE, `v4/pact.rs:202-209`)

```json
{"consumer":{"name":"web"},"provider":{"name":"orders-api"},
 "interactions":[{"type":"Synchronous/HTTP","description":"get order 1","key":"…","pending":false,
   "providerStates":[{"name":"order 1 exists"}],"request":{"method":"GET","path":"/orders/1"},"response":{"status":200,"body":{"id":1}}}],
 "metadata":{"pactSpecification":{"version":"4.0"}}}
```

- Interaction types are `Synchronous/HTTP`, `Asynchronous/Messages` and `Synchronous/Messages`.
- Each interaction has a `pending` flag.

### Verification execution result (CONFIRMED-IN-CODE, `verification_result.rs:46-130`, test fixture `:395-464`)

```json
{"result":false,"notices":[],"output":[],"errors":[{"interaction":"…","mismatch":{"type":"mismatches","mismatches":[{"type":"StatusMismatch","expected":200,"actual":500,"mismatch":"expected 200 but was 500"}]}}],
 "pendingErrors":[],
 "interactionResults":[{"consumer":"Consumer A","provider":"Provider","description":"result-1","providerStates":[],"pending":false,"result":"OK","duration":"0ns"},
                       {"consumer":"Consumer B","provider":"Provider","description":"result-3","interactionId":"test-id","pending":true,"result":"OK","duration":"0ns"}]}
```

### Semantics (CONFIRMED-IN-CODE)

**`result`.**
- `result` is `false` iff the non-pending `errors` list is non-empty (`lib.rs:1240-1248`).
- **Failures of pending pacts or interactions go to `pendingErrors` and do not fail the run** (`lib.rs:1148-1154`; summary line "non-fatal pact failures on pending pacts", `:1234-1238`).
- If the verifier cannot load a pact at all while it is pending, that also becomes a *pending* error (`:1161-1168`).

**Vacuous passes.**
- **A pact with no interactions** only pushes `WARNING: Pact file has no interactions` into output (`lib.rs:1121-1128`). The run can still be `result: true` with zero interactions verified.
- **A Broker "no pacts found" (NotFound) is ignored** unless `no_pacts_is_error` is set (`lib.rs:1198-1205`; option at `:998-999`). Again the outcome is `result: true` with nothing verified.

**Partial runs.**
- Filters (`FilterInfo`: description, provider state, interaction ids; `lib.rs:821-952`) narrow which interactions run.
- So do `run_last_failed_only` and `exit_on_first_failure` (`lib.rs:1000-1003`, `:1176-1179`).
- In every case the JSON shows only what ran. Nothing records what was filtered out.

**Missing identity.** `interactionResults` carry no provider version, commit or base URL. The JSON is **not self-identifying** for revision. Provider version, branch, tags and build URL exist only in the publish options (`lib.rs:963-980`) and in the payload published to the Broker (`pact_broker.rs:980-998`): `success`, `providerApplicationVersion`, `verifiedBy`, `testResults[{interactionId, success}]`.

**Telemetry.** `send_metrics_async(MetricEvent::ProviderVerificationRan…)` runs on every verification (`lib.rs:1220-1225`). Opting out with `PACT_DO_NOT_TRACK` is DECLARED-ONLY in Pact docs. This matters if Assertiva ever *runs* a verifier: set the opt-out and treat it as a network egress.

**Observed oddity.** On the no-publish path, `lib.rs:1190` selects the error-notice stage with `!errors.is_empty() || pending_errors.is_empty()`, which looks inverted compared with `:1184`. It affects only Broker notices, not `result`. Not verified with upstream.

### Broker `can-i-deploy` (DECLARED-ONLY, docs and pact_broker-client README)
- **Inputs:** `--pacticipant` with `--version`, `--latest`, `--branch` or `--main-branch`, plus `--to-environment`.
- **Exit codes:** 0 yes, 1 no. **`--dry-run` always exits 0.**
- **Other options:** `--retry-while-unknown`; `--output json|table`.
- **Matrix rule:** deployable when every integrated version in the target environment has a successful verification with it.
- **Not confirmed:** the JSON fields (`summary.deployable`, `reason`, `matrix`) appear in neither page. Do not hard-code them without a fixture from a real Broker.

### Ingestion design: new `assertiva/adapters/pact.py` (report ingestion; no execution)

**Pact files** (`pacts/*.json`, discovered statically) → contract **declarations**:
- one declared check per interaction: consumer→provider, `description`, `type`, `pending`, provider states;
- tier E1 from the file, revision identity = the file's sha256 plus the audited tree.
- Consumer tests that produced the pact cross a **simulated HTTP** boundary. `test_facts.py` should add Pact mock-server usage to the simulated-HTTP facts, so FIDELITY_MISMATCH applies when an "integration" test is only a consumer pact test.

**Verifier JSON** → `RunEvidence(adapter_id="pact", mode="report")`, one `TestInvocation` per `interactionResults[i]`:
- `OK` → PASSED.
- `Error` → FAILED, keeping the mismatch types.
- `pending: true` with `Error` → **XFAILED-like "pending failure (non-blocking by policy)"**. It is *not* passed.
- `pending: true` with `OK` → PASSED, plus the note "pending: not yet a contract obligation".
- `materialization_id = consumer → provider : description`.
- Tier: E0 artifact, E1 normalization.

**Limitations to emit:**
- "verifier result carries no provider revision; not tied to the audited tree" unless Broker publish data is provided;
- "pending failures do not fail verification";
- "an empty or absent pact passes vacuously" when `interactionResults` is empty while `result` is true;
- "filtered or last-failed runs omit interactions".

**Cross-check.** Compare declared interactions from pact files with interactions in the verifier result:
- verified → EXECUTED;
- declared and absent → SELECTED-not-run or NOT_RUN, the same DECLARED/SELECTED/EXECUTED matrix as Playwright projects.

**Broker matrix and can-i-deploy JSON** → E2 (declared by the Broker), stamped with the Broker URL and query time. It is never an E0 run and never fetched without consent (network).

**Must NOT support:**
- "contract verified" from pact files alone;
- "provider compatible" from a consumer test run;
- "deployable" from a `--dry-run` exit code, or from a pending pass;
- "API correct" from a pact pass. Pact verifies only the consumer's recorded expectations (examples plus matchers), not the provider's full behaviour or schema.

---

## 6. Testcontainers (deep on lifecycle and isolation)

Examined files:
- `core/src/main/java/org/testcontainers/utility/ResourceReaper.java:40-130, 330-404`
- `RyukResourceReaper.java:28-135`
- `RyukContainer.java:10-32`
- `JVMHookResourceReaper.java:20-62`
- `DockerClientFactory.java:57-70`
- `TestcontainersConfiguration.java:62-184`

### Semantics (CONFIRMED-IN-CODE)

**Session labelling.** Every resource is labelled `org.testcontainers.sessionId=<random UUID per JVM>` (`DockerClientFactory.java:57-65`, `ResourceReaper.java:44-52`). Language and version labels are added too.

**Ryuk reaper.**
- **Ryuk** (`testcontainers/ryuk:0.14.0`, `RyukContainer.java:11`) is started with `AutoRemove`.
- It runs **`Privileged` by default**: `ryuk.container.privileged` defaults to `"true"` (`TestcontainersConfiguration.java:140-141`).
- It has the **host Docker socket bind-mounted** at `/var/run/docker.sock` (`RyukContainer.java:15-27`).
- The client sends label filters over TCP and waits for `ACK` (`ResourceReaper.java:356-401`; rate-limited retry in `RyukResourceReaper.java:88-115`).
- When the client connection drops, Ryuk prunes containers, networks, volumes and images matching the filters after `ryuk.container.timeout`, default 30 s (`TestcontainersConfiguration.java:154-155`).

**Ryuk disabled.**
- `TESTCONTAINERS_RYUK_DISABLED=true` falls back to `JVMHookResourceReaper` with a warning (`ResourceReaper.java:77-91`).
- That reaper prunes only from a JVM shutdown hook (`JVMHookResourceReaper.java:20-30`).
- **A killed JVM leaks containers.**

**Reuse.** `testcontainers.reuse.enable` (`TestcontainersConfiguration.java:183-184`) allows `withReuse(true)` containers to survive across runs. Not reaping them is DECLARED-ONLY. Either way, state crosses test runs, which breaks the "disposable" claim.

**Images** are pulled from a registry (Docker Hub by default; configurable image substitution). That is network egress and supply-chain input.

### Meaning for Assertiva
- **Testcontainers is a *disposable real service*.** It runs a real engine binary, which is higher fidelity than an in-memory fake.
- **But running it requires a Docker daemon.** The default reaper is privileged and holds the Docker socket, which is **root-equivalent on the host**. Pulls are network egress.
- Assertiva's current position fits this: `services.py` uses a local PostgreSQL with no Docker, and the README says "no Docker required".

**Decision:**
- **Do not BUILD** a Testcontainers runner. **REJECT executing it by default.**
- **ADAPT-CONCEPT:**
  - session-scoped labels and an orphan sweep for Assertiva's own disposable services: a temp dir plus a PID file plus a sweep of stale `assertiva-*` clusters;
  - "reaper acknowledges before tests start".
- **Static facts (INTEGRATE).** `test_facts.py` should recognise Testcontainers usage, which proves the test *declares* a real disposable dependency:
  - Java `@Testcontainers` / `@Container` / `new PostgreSQLContainer`;
  - Python `testcontainers.*`;
  - Node `@testcontainers/*`.

  Classify the boundary as `REAL_DISPOSABLE` (DATABASE, BROKER, HTTP), so FIDELITY_MISMATCH does not fire.
- **Execution.** Execution of such tests needs explicit consent, naming Docker daemon, privileged reaper, socket mount, image pulls and network. Without consent, list them NOT_RUN with the reason "requires Docker (not authorized)", mirroring Android instrumented tests. Reused containers (`withReuse(true)`) are flagged "not disposable: state may persist between runs".

---

## 7. axe-core (deep)

Examined files:
- `lib/core/constants.js:1-83`
- `lib/core/utils/aggregate-result.js:1-39`
- `lib/core/utils/aggregate-node-results.js:1-65`
- `lib/core/utils/finalize-result.js`
- `lib/core/utils/get-environment-data.js`
- `lib/core/reporters/{v1,v2,raw,no-passes,na}.js`
- `lib/core/reporters/helpers/process-aggregate.js:1-107`
- `README.md:19, 69-102`
- `doc/API.md:141, 425-600, 671-698, 974-981`

### Output format (v1/v2 reporter; CONFIRMED-IN-CODE)

```json
{"testEngine":{"name":"axe-core","version":"4.x"},"testRunner":{"name":"axe"},
 "testEnvironment":{"userAgent":"…","windowWidth":1280,"windowHeight":720},"timestamp":"…","url":"http://localhost:3000/login",
 "toolOptions":{"runOnly":{"type":"tag","values":["wcag2a","wcag2aa"]}},
 "violations":[{"id":"button-name","impact":"critical","tags":["cat.name-role-value","wcag2a","wcag412"],"help":"Buttons must have discernible text","helpUrl":"https://dequeuniversity.com/rules/axe/4.x/button-name",
   "nodes":[{"target":["#submit"],"html":"<button id=\"submit\"></button>","impact":"critical","any":[…],"all":[],"none":[],"failureSummary":"…"}]}],
 "passes":[…],"incomplete":[…],"inapplicable":[{"id":"video-caption","nodes":[]}]}
```

### Semantics (CONFIRMED-IN-CODE)

**Four groups.** `inapplicable` (NA), `passes`, `incomplete` (CANTTELL) and `violations` (FAIL), with priorities 0..3 (`constants.js:1-26`). Impact levels are `minor`, `moderate`, `serious` and `critical` (`:38`).

**Errors become `incomplete`.** **A rule that threw an error is put in `incomplete`, not reported as an error** (`aggregate-result.js:24-25`). `doc/API.md:698` says the same: incomplete happens "because a JavaScript error occurred".

**A rule can appear in several groups.** It is placed in every group where it has nodes (`aggregate-result.js:28-33`), so the same rule can be in `violations` and `passes` for different nodes. Count rules per group, never `violations + passes = rules`.

**Rules with no matching nodes** are `inapplicable` (`aggregate-node-results.js:34-36`).

**Impact.** The rule-level impact is the highest node impact among failures. If there are no failures, it is the highest among *incomplete* nodes (`aggregate-node-results.js:46-58`).

**Truncation and omission.**
- **`resultTypes` truncates nodes to one** for non-listed groups (`process-aggregate.js:33-39`).
- **The `no-passes` reporter drops `passes`, `incomplete` and `inapplicable` entirely** (`no-passes.js:11-20`).
- So an absent `incomplete` key does **not** mean zero review items.

**HTML may be null.** `html` can be nulled when `noHtml` is set (`process-aggregate.js:89-91`).

**Default rule set.** By default every rule runs **except `experimental`** (`doc/API.md:547`). `runOnly` restricts by tags or ids, and the effective scope is echoed in `toolOptions`.

**Coverage claims.**
- axe finds "on average 57% of WCAG issues automatically" (`README.md:19`).
- It aims for zero false positives (`README.md:69`).
- **Absence of violations is therefore no evidence of the other ~43%.** Examples: focus order, meaningful alt text quality, captions accuracy, keyboard traps in flows not rendered, cognitive criteria.

**Scope.** Results cover **one DOM state at one URL** (`get-environment-data.js`: `url`, `userAgent`, viewport), plus the `context` include/exclude passed to `axe.run`.

### Ingestion design: new `assertiva/adapters/axe.py` (report ingestion)
Locate axe JSON written by:
- `@axe-core/playwright` saved as a test attachment (already referenced by name or path in Playwright metadata);
- `jest-axe` snapshots;
- `@axe-core/cli`, or the axe-core JSON from pa11y or Lighthouse.

Normalize to a new record kind, `AccessibilityScan`:
- `{url, engine, engine_version, user_agent, viewport, rule_scope (runOnly tags/ids or "default minus experimental"), reporter_completeness (full | no-passes | truncated)}`;
- per rule: `{rule_id, group, impact, wcag_tags, node_count, targets[:N]}`.

Mapping and tiers:
- violations → findings (E0 artifact, E1 normalized);
- incomplete → "needs manual review", never pass and never fail;
- passes → only "rule R found no failing node among N nodes on this URL/state";
- inapplicable → "rule not exercised".

Provenance:
- the axe JSON sha256;
- the producing test invocation, when it came from a Playwright attachment, which ties it to an executed test in this run;
- otherwise "ingested, revision not verified".

Redact `html` snippets in the HTML report by default, because they may contain user data. Keep `target` selectors.

**Must NOT support:**
- "accessible", "WCAG 2.x AA conformant" or "no accessibility issues" from 0 violations;
- any claim beyond the scanned URLs and states and the rule scope actually run;
- "0 incomplete" when the reporter was `no-passes` or `resultTypes` truncated;
- treating a rule error (which lands in incomplete) as a pass.

The report must always say: "automated rules only; manual and assistive-technology review not evidenced". This implements the ROADMAP M7 sentence.

---

## 8. Peripheral projects (brief)

- **Lighthouse accessibility.** The score is a **weighted average of pass/fail audits** mapped to axe rules (weights 3/7/10, from axe impact). There is no partial credit: one failing node fails the audit. **Manual audits and best-practice audits do not count.** Source: developer.chrome.com/docs/lighthouse/accessibility/scoring (DECLARED-ONLY). Ingest `lhr.audits[*]` where the audit is in the accessibility category, along with its `scoreDisplayMode` (`notApplicable` and `manual` are excluded; recalled, not verified in code). **A score of 100 must never be rendered as "accessible".** Lighthouse is Apache-2.0.
- **pa11y** (LGPL-3.0, active). It is a CLI and CI runner over axe or HTML_CodeSniffer, emitting issues `{code, type: error|warning|notice, message, selector, context, runner}`. Ingest its JSON and keep `runner`, because HTMLCS codes differ from axe ids. Do not bundle it (LGPL). Format fields are DECLARED-ONLY (not cloned).
- **Schemathesis** (MIT, active, SHA `34636c3a`). It does property-based testing from OpenAPI or GraphQL. Report handlers exist for **JUnit XML, VCR YAML cassettes, HAR, NDJSON event stream, Allure and HTML** (`src/schemathesis/cli/commands/run/handlers/{junitxml,vcr,har,ndjson,allure,html}.py`). JUnit records failures per operation and check, plus errors and skipped (`junitxml.py:28-78`). NDJSON and VCR record the **seed** (`ndjson.py:47`, `vcr.py`), so a failure is reproducible. Ingest the JUnit through `junit.py`, and read the seed and Schemathesis version from NDJSON as provenance. A run against a non-local base URL is network egress. It must be blocked like a Playwright non-local `baseURL`.
- **Specmatic** (MIT, active). It turns OpenAPI and AsyncAPI specs into executable contract tests and stubs. Its stub mode is a **simulated** boundary. Contract-test mode exercises a real provider. Classify by mode. Output format not investigated.
- **WireMock** (Apache-2.0, active). Its HTTP stub, record/playback and `verify()` are **simulated HTTP**; Assertiva already classifies them so. Recordings (`mappings/*.json`) can be stale versus the real service. Report a recording's age and source only if available.
- **Spring Cloud Contract** (Apache-2.0, **archived per GitHub API at 2026-10-19**). It generates provider tests and stubs from Groovy/YAML contracts. Generated tests run as ordinary JUnit, already ingestible. Do not invest in a dedicated adapter, given the archived status.
- **Dredd** (MIT, **archived 2024**). It validated API Blueprint/OpenAPI against a running server. REJECT: unmaintained.

---

## 9. Per-format ingestion summary

| Format | Adapter | Normalized records | Tier | Lost / inferred | Revision identity | Must NOT support |
|---|---|---|---|---|---|---|
| Playwright JSON | `playwright.py` (existing; fix §1) | `TestInvocation` per test×project; matrix DECLARED/SELECTED/EXECUTED; attachments | E0 file → E1 | Run status; browser version (only via trace); filtered tests when `onlyFailures` | Assertiva-executed: the audited tree. Ingested: `config.metadata.gitCommit.hash` (E2) or unknown | "Passed" for an `ok:true` skipped or flaky test; "ran on WebKit" from project name alone (E3) |
| Playwright trace.zip (first event) | `playwright.py` (bounded zip read) | `browserName/channel/playwrightVersion/platform` per invocation | E0 | — | Same as the run | Proof of real-backend calls: routes may be fulfilled by `page.route` |
| Cypress Module-API JSON | new `cypress_results.py` | invocations with attempts; engine | E0→E1 | Line numbers, intercepts, skipped specs | Unknown unless supplied | Flaky = passed; Electron = real Chrome |
| Cypress / Android / Schemathesis JUnit | `junit.py` | invocations | E0→E1 | Retries, device kind, seeds | Unknown (build output) | Device or emulator kind from XML alone |
| Pact file | new `pact.py` | declared contract interactions | E1 | — | sha256 + tree | Verified |
| Pact verifier JSON | new `pact.py` | interaction invocations; pending failures | E0→E1 | Provider revision; filtered interactions | None in file; Broker publish data E2 | Pass on empty or no pacts; pending = pass; API correctness |
| can-i-deploy / matrix JSON | new `pact.py` (opt-in, network consent) | deployability claim | E2 | — | Broker URL + query time | Dry-run exit 0 = deployable |
| axe JSON | new `axe.py` | `AccessibilityScan` + rule results | E0→E1 | Pages and states not scanned | Producing test invocation or sha256 | Accessible or WCAG-conformant; 0 incomplete under no-passes |
| Lighthouse LHR (a11y) | `axe.py` (LHR reader) | audits → rule results | E0→E1 | Node detail | `lhr.fetchTime`, `finalUrl` | A score of 100 = accessible |
| pa11y JSON | `axe.py` (pa11y reader) | issues by runner | E0→E1 | — | — | Same as axe |

---

## 10. Comparison: what they do better, and how

**Playwright.**
- It separates `expectedStatus` from actual status per attempt. Its `outcome()` handles five per-result categories.
- The trace records the exact engine and version.
- Assertiva copies most of this but **conflates didNotRun and interrupted with skip**, and over-claims flaky as a pass (§1 gaps 1-2).

**Pact.**
- It ties verification to versions and environments in the Broker matrix: revision-aware, cross-service evidence that Assertiva lacks.
- It has an explicit **pending** concept, which lets a new obligation fail without blocking. That is analogous to XFAIL with a policy.

**axe-core.**
- It has an explicit, honest **`incomplete`** category, distinct from pass and fail.
- It echoes its rule scope (`toolOptions`).
- Assertiva's NOT_RUN/UNKNOWN discipline matches this philosophy. Assertiva has no a11y record yet.

**Testcontainers.**
- Session-labelled resources and an out-of-process reaper with an ACK handshake give crash-safe cleanup.
- Assertiva's `services.py` cleanup is in-process. Adapt the concept: a session label or temp-dir marker plus a startup sweep of stale clusters.

**Schemathesis.** It records a seed, so a property failure is reproducible. Assertiva should keep the seed in provenance when ingesting it.

### Decisions

| Item | Decision | Reason |
|---|---|---|
| Playwright JSON and trace | **INTEGRATE** (fix existing) | Apache-2.0, format stable, already partially done |
| Cypress results | **INTEGRATE** via JUnit now; Module-API parser later | MIT; low cost |
| Pact files and verifier JSON | **INTEGRATE** (new `pact.py`) | MIT; report-only, no execution |
| Pact Broker queries | **INTEGRATE, opt-in** | Network and credentials need consent |
| axe / Lighthouse / pa11y output | **INTEGRATE** (new `axe.py`) | Read outputs only (axe MPL-2.0, pa11y LGPL: no bundling) |
| Testcontainers execution | **REJECT by default** | Docker daemon, privileged reaper and socket (root-equivalent), image pulls |
| Testcontainers detection | **INTEGRATE** (static facts) | Boundary classification |
| Ryuk-style session reaper | **ADAPT-CONCEPT** for `services.py` | |
| Android connected/GMD results | **INTEGRATE** (ingest XML; never start emulators) | Device kind E2 at most |
| Schemathesis | **INTEGRATE** JUnit + NDJSON seed | MIT, active |
| Specmatic | **ADAPT-CONCEPT** (mode classification) | |
| Spring Cloud Contract, Dredd | **REJECT dedicated adapters** | Archived; their tests surface as JUnit anyway |

### Concrete changes (proposed; nothing implemented in this research)

1. **`assertiva/adapters/playwright.py`**
   - didNotRun → NOT_RUN; interrupted-only → NOT_RUN "interrupted".
   - flaky computed from the results: last result `== expectedStatus` → PASSED with retries; otherwise FAILED or NOT_RUN.
   - `onlyFailures` detection, which marks the run partial.
   - Limitation "no run-level status in JSON report".
   - Optional bounded read of `trace.zip` → `run.metadata["engines_observed"]`.
   - `gitCommit.hash` captured as declared revision, with author, email and diff dropped.
2. **`assertiva/adapters/test_facts.py`**
   - Facts for Pact consumer mock servers (simulated HTTP).
   - Pact provider verification (`@Provider`/`Verifier`/`pact_verifier`): a real HTTP boundary to a local process.
   - Testcontainers (`REAL_DISPOSABLE`) and `withReuse(true)`.
   - Specmatic stub vs test mode.
   - `getBy`/`findBy` vs `queryBy` distinction.
3. **`assertiva/effectiveness.py`**
   - The fidelity ladder becomes MOCK < SIMULATOR (Robolectric, MockWebServer, Pact mock, WireMock) < REAL_DISPOSABLE (Testcontainers, `services.py`) < REAL_EMULATOR < REAL_DEVICE / REAL_BROWSER.
   - FIDELITY_MISMATCH fires only below the level the test declares.
4. **New adapters**
   - `assertiva/adapters/pact.py`: pact files plus verifier JSON; Broker matrix opt-in.
   - `assertiva/adapters/axe.py`: axe, Lighthouse a11y and pa11y.
   - Optionally `cypress_results.py`.
5. **`schemas/assurance-report.schema.json`**
   - Add `execution_target` on runs: `enum [MOCK, SIMULATOR, REAL_DISPOSABLE, EMULATOR, DEVICE, BROWSER, REMOTE, UNKNOWN]` plus `target_detail`.
   - Add `contract_verifications[]`: consumer, provider, interaction, pending, result, revision_identity.
   - Add `accessibility_scans[]`: url, engine/version, rule_scope, reporter_completeness, counts per group, `manual_review_required: true` (const).
   - Each new record gets `evidence_tier` and `provenance`.
6. **`references/TEST_QUALITY.md`**
   - Pending pacts; vacuous verification.
   - axe incomplete vs pass; "0 violations ≠ accessible".
   - Electron ≠ shipped Chrome; ATD headless limits.
   - Testcontainers reuse is not disposable.
7. **HTML (`report_html.py` / `report_i18n.py`)**
   - An accessibility panel with the fixed caveat line.
   - A contract matrix: declared → verified → pending.
   - An execution-target badge per run.
8. **Evals** (with budget approval, per memory rule)
   - An agent asked "is the app accessible?" given a 0-violation axe report must answer "not established".
   - An agent asked "is the provider compatible?" with an empty verifier result must answer "not verified".

### Tests and fixtures that would prove it (synthetic, generic names)

- **Playwright JSON** (`tests/test_playwright.py`): one fixture per case.
  - `expectedStatus=passed` with a single `skipped` result → NOT_RUN.
  - Only `interrupted` results → NOT_RUN.
  - `[failed, skipped]` → not PASSED.
  - `reporter: [["json", {"onlyFailures": true}]]` → partial-run limitation.
  - `metadata.gitCommit` with an email → the email is absent from the report.
- **Playwright trace.** A minimal `trace.zip` with one `context-options` line → engine observed. A zip bomb or oversized entry → bounded refusal.
- **Pact.**
  - Verifier JSON built from the upstream test fixture shape: a mix of OK, Error, pending OK and pending Error → 1 FAILED, 1 pending-failure, 2 PASSED, `result` false.
  - `{"result":true,"interactionResults":[]}` → "vacuous verification" limitation, status UNKNOWN, not PASS.
  - A pact file with 3 interactions and a verifier JSON with 2 → one NOT_RUN.
- **axe.**
  - Full v2 JSON with violations, incomplete and inapplicable → mapping as above.
  - `no-passes` output → completeness `no-passes`, with no "0 incomplete" claim.
  - The same rule in violations and passes → counted per group.
  - `runOnly` tags → the scope is shown.
  - The report text never contains "accessible" as a verdict (a negative assertion test).
- **Testcontainers static facts.** A Java/Python/Node test file using a container → `REAL_DISPOSABLE`, no FIDELITY_MISMATCH. With `withReuse(true)` → flag. Execution listed NOT_RUN "requires Docker (not authorized)".
- **Benchmark (M9 lab).** Count false "pass" claims across these fixtures. The target is zero.

---

## 11. Capability gap matrix

| Capability | Status in Assertiva |
|---|---|
| Run Playwright, parse JSON, retries/flaky, project matrix, missing browser → NOT_RUN | **IMPLEMENTED** |
| Playwright didNotRun and interrupted-only distinguished from skip | **PARTIAL** (mapped to SKIPPED, `playwright.py:164`) |
| Playwright flaky edge case (failed → skipped) | **PARTIAL** (over-claims pass) |
| Playwright `onlyFailures` partial-report detection | **UNSUPPORTED** |
| Real browser engine proven from trace | **UNSUPPORTED** (project-name inference only) |
| Playwright `gitCommit` as declared revision | **UNSUPPORTED** |
| Cypress results (Module API) | **UNSUPPORTED**; JUnit route **PARTIAL** (generic junit) |
| Testing Library query semantics as oracles | **IMPLEMENTED** (lexical); `queryBy` distinction **UNKNOWN** (not checked in `test_facts.py`) |
| Robolectric as simulated device | **IMPLEMENTED** |
| Android instrumented tests NOT_RUN | **IMPLEMENTED** |
| Ingest connected/GMD XML with an emulator/device target | **UNSUPPORTED** |
| UTP `.pb` results | **UNSUPPORTED** (format UNKNOWN here) |
| Mocks/simulators detection (MockWebServer, WireMock, msw, `cy.intercept`) | **IMPLEMENTED** |
| Fidelity ladder incl. REAL_DISPOSABLE / EMULATOR / DEVICE | **PLANNED** (M7) |
| Disposable real PostgreSQL without Docker | **IMPLEMENTED** (`services.py`) |
| Testcontainers static detection | **UNSUPPORTED** |
| Testcontainers execution | **UNSUPPORTED by design** (consent needed) |
| Crash-safe orphan sweep for disposable services | **UNKNOWN** (not inspected here) |
| Pact files as declared contracts | **PLANNED** (M7) |
| Pact verifier results incl. pending/vacuous | **PLANNED** (M7) |
| Pact Broker matrix / can-i-deploy | **UNSUPPORTED** |
| axe results with incomplete / no-passes semantics | **PLANNED** (M7) |
| "No full-accessibility claim" rule | **SPECIFIED** (ROADMAP M7; not enforced in code) |
| Lighthouse a11y / pa11y ingestion | **UNSUPPORTED** |
| Schemathesis / Specmatic ingestion (seed, mode) | **UNSUPPORTED** (JUnit generic only) |

---

## 12. Limitations, uncertainties, not investigated

**Android.**
- Exact XML `<properties>` (device/flavor), exact GMD and UTP result paths, and the `.pb` schema were **not verified in code**. AGP was not cloned.
- To verify: clone `android.googlesource.com/platform/tools/base` sparsely (`build-system/gradle-core/.../testing/`, `utp/`).

**Cypress.**
- Mocha `pending` vs `skipped` meaning is from knowledge; only the field names were confirmed.
- The mochawesome and JUnit reporter formats were not read.

**Pact.**
- Only the Rust core was read. pact-js and pact-jvm wrap it, or have their own JVM implementation, and may serialize differently.
- The can-i-deploy JSON structure is unconfirmed.
- The `PACT_DO_NOT_TRACK` opt-out is from docs memory.
- The `lib.rs:1190` notice-logic oddity is unverified upstream.

**Testcontainers.**
- Only Java was read. The Python and Node reaper defaults (privileged and socket mount) were not verified.
- Reuse-skips-reaping is DECLARED-ONLY.

**Lighthouse.** The scoring of `notApplicable` and `manual` audits was not verified in code.

**pa11y.** The JSON fields are not verified.

**Not fetched.** Specmatic, WireMock and Spring Cloud Contract result formats.

**Trace.** Not verified whether `trace.trace` is always the first zip entry or whether `context-options` is always the first line. The parser must scan a bounded prefix.

**Approximate tokens spent:** about 105k of the 300k budget.
