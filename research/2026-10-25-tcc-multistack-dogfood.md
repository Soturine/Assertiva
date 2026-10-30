# Dogfooding Assertiva 0.9.0 on Soturine/tcc — 2026-10-25

> **Evidence record, not a claim of new Assertiva functionality.** The source project is [Soturine/tcc](https://github.com/Soturine/tcc), an ESP32/MPU6050 fall-event platform with C++, Node.js/Express/MySQL/MQTT, frontend, Python research/FallBench, and offline MotionLab. This record is based on the [TCC audit](https://github.com/Soturine/tcc/blob/513157c6a150b9761d8c4c968c6a66a88e458ee0/docs/quality/test-audit-assertiva-2026-10-25.md), [P2.1 evidence](https://github.com/Soturine/tcc/blob/main/docs/quality/p2-1-implementation-evidence-2026-10-25.md), [PR #11](https://github.com/Soturine/tcc/pull/11), and the two supplied Assertiva 0.9.0 reports from the same exercise (not copied or republished). It is **not** a rerun of the engine in this repository.

## 1. Provenance and immutable scope

| Record | Evidence | Meaning |
|---|---|---|
| Tool | Assertiva **0.9.0**, as reported by the original operator | existing release; no Assertiva code modified by the TCC run |
| Source project first audited | TCC `e49724b57c2e2705f88360e4a931c796c57b9c98`; report run `f1a077abc150409b` | earlier product revision; native/project runners used separately |
| Source project reassessed | TCC `91222ce343d5faa32c453f60f2fae6eb2735faae`; engine run `bf5f5edca6d743dd` | clean disposable clone, report HTML/JSON and agent assessment attached |
| Final deployed *repository* revision, not device deployment | TCC `513157c6a150b9761d8c4c968c6a66a88e458ee0` (PR #11 merged) | Backend/Firmware/Web/Security GitHub workflows passed on this SHA; no physical validation |
| Distinction | Product code same between `e49724b` and `91222ce` according to TCC operator; late CodeQL fix was in broker verification script | **No assertion that the engine reran on the final merge SHA.** In particular, CI on a later SHA is independent evidence |
| Artifact privacy | original `history.zip` includes SQLite history, HTML/JSON reports and JSONL traces; manual mutation scripts/reports live in private Assertiva workspaces | **Do not commit** raw workspaces, user data, zip, HTML/SQLite/JSONL traces, credentials, download-only datasets or personal filesystem paths here |

**Units matter:** in the final assessment, the engine inventoried **142 JavaScript** and **60 Python** static test definitions/candidates; these are *not* 202 invocations executed by the engine. `--run-check` executed **4 HIL-checker** and **12 MotionLab** invocations; it did not validate real ESP32 hardware. The operator's project suites and CI ran other tests with their own commands and identities; external run evidence must never be relabeled `ENGINE_EXECUTED`.

## 2. What was actually performed

| Instrument/method | Observed result | Evidence provenance | Claim boundary |
|---|---|---|---|
| `assertiva audit --output json` | Static inventory, heuristics and seven engine findings | `ENGINE_STATIC` (observed files + heuristic signals) | Not native test execution |
| `assertiva audit --execute` at repository root | Root `unittest` collected **0**, result **UNKNOWN** | `ENGINE_EXECUTED` | Multi-root project subtrees contain their own runners; this is not proof that project has zero tests |
| `--run-check` for two declared Python commands | HIL-checker **4/4** and MotionLab **12/12**, no collection errors | `ENGINE_EXECUTED` in disposable copy | HIL checker verifies logs/contracts, not a device; MotionLab is offline |
| `--ci-run`/provider queries | Four TCC CI workflows reported success with revision equivalence for `e49724b` | `EXTERNAL_VERIFIED / SAME_REVISION` | GitHub verified the CI jobs, not Assertiva reproducing all the commands |
| `--execute --mutate` | **BLOCKED**: Cosmic Ray unavailable to that environment/target | `BLOCKED`, no mutant evaluated by engine | Not an engine mutation score |
| Manual mutation exercise | **22 hand-selected mutants**: 21 detected initially, 1 survived (backend `reason_code` contract), new test killed the survivor | `OPERATOR_EXECUTED_MANUAL` outside engine | Not population mutation coverage, not automated Assertiva mutant execution, not full project coverage |
| TCC independent project runners | Backend **151 total: 146 pass, 5 skipped locally** then MySQL-specific **4/4 migrations + 1/1 retention**; C++ **65/65**; E2E **20/20**; broker negative checks **19/19**; research **44** (1 skipped locally, none in CI); MotionLab **12/12**; HIL log-verifier **4/4**, ESP32 build succeeded | `PROJECT_RUNNER` / GitHub CI; see linked TCC evidence | Do not sum these unlike units or say Assertiva ran them. Physical HIL, secure staging and Android alerts still absent |
| Agent assessment | Dispositions of engine findings and **4 agent-added findings** attached to the report | `AGENT_ASSESSMENT` | The engine did not independently discover these four product findings |

## 3. Engine findings and adjudication

Source: TCC [auditor disposition report](https://github.com/Soturine/tcc/blob/main/docs/quality/test-audit-assertiva-2026-10-25.md). **Severity below is the engine's initial level**, not necessarily the final effective priority.

| Code | Initial severity | Disposition / verification | Transferable gap |
|---|---|---|---|
| `CI_TEST_EXECUTION_GAP` | high | **FALSE_POSITIVE:** GitHub Action `research-replay` sets `working-directory: tools/research` then invokes `python -m unittest discover -s tests`; project CI actually ran 43 tests at that point | CI working-directory/path resolution must be scoped to each step, not repository root |
| `WEAK_ORACLE_SIGNAL` | medium | **FALSE_POSITIVE** on two MotionLab validation tests: valid-input tests assert only "does not raise" but their sibling negative tests assert exceptions | Oracle strength depends on the validated contract and neighboring negative-path tests; no blanket "no assert = weak" |
| `STATIC_INVENTORY_DIVERGES_FROM_NATIVE` | info | **CONFIRMED/CONTEXTUAL:** 60 Python static definitions vs 16 invocations in the two chosen checks | Show denominator/scope, partial selection and explicit origin rather than a misleading test-coverage ratio |
| `LOCAL_CHECK_NOT_OBSERVED_IN_CI` | high | **CONTEXTUAL:** `dev:setup/start/stop/init-db/check/smoke` are local developer orchestration; CI has its own disposable services | Do not automatically demand local lifecycle helpers in CI; compare *effect* and proof of boundary |
| `CI_ONLY_CHECK` | medium | **CONFIRMED**, low impact in this project: CI gates are not mirrored by local hooks | Workflow preference / fast-feedback tradeoff; not necessarily a defect |
| `CI_SINGLE_OS` | info | **CONFIRMED:** GitHub CI Linux only; Windows shell/CRLF/MSYS differences happened in the exercise | Offer targeted Windows check when real portability matters; do not promise portability from Linux success |
| `UNCLASSIFIED_VERIFICATION` | info | **CONFIRMED:** PlatformIO build, broker Docker, scripts absent from recognized verification categories | Distinguish *custom/unknown* checks from nonexistent checks; classify by observed CLI effect when safe |

**Finding counts:** **7 engine** findings plus **4 agent-added** findings in the reassessed JSON. The TCC narrative additionally lists its own manually found T1–T8; **do not call all T1–T8 engine-generated**.

## 4. Independent investigator observations (not engine discoveries)

| TCC finding | Assessment | Relevance to Assertiva |
|---|---|---|
| **T1** backend's persisted result could carry inappropriate `reason_code` without test failure | demonstrated by manual mutant B2; TCC added regression test | Strengthen contract/test quality reasoning for persisted result combinations and mutation attribution |
| **T2** E2E check initially always true | found by diff review, fixed in TCC | Static false-green candidate for tautological or unconditional assertions, with proof needed |
| **T3** broker/E2E checks could hang on failed publish/connection | reproduced and fixed | Detect unbounded waits, missing process-tree cleanup and no timeout observability across runners |
| **T4** `test:integration` uses `loadWithMocks` for DB/services/logger | confirmed from source, remains open as naming/fidelity issue | Classify mocked unit behavior vs actual integration; do not infer from script name |
| **T5** backend CI runs overlapping test files multiple times | confirmed, informational | Compare test *invocation identities* and CI command graphs before suggesting deduplication |
| **T6** web workflow only lint/build; no UI tests | confirmed; uncovered product risk | Reveal a UI test *absence* as relevant without reporting lint/build as behavioral UI evidence |
| **T7** `CriticalOutboxFsStore` is excluded from native build/tests; pure recovery decision tested instead | confirmed; hardware requirement blocked | Coverage of the real filesystem adapter must stay `HIL_REQUIRED/BLOCKED`, not `PASS` because 4 "HIL" checker tests passed |
| **T8** E2E 17 accepts silence during reset, complemented by before/after assertions | contextual, acceptable when considered as scenario suite | Analyze the full temporal oracle rather than one silence-based check in isolation |

**Separately**, the TCC PR CodeQL flagged `js/clear-text-logging` in a broker diagnostic. Its code was changed to log restricted error codes, then the CodeQL check became green. This was a **GitHub CodeQL finding**, not Assertiva's own detector.

## 5. Cross-cutting lessons and threats to validity

1. **The engine's inventory coverage is not the same as test-execution coverage.** A root command collected 0 while child projects' tests were runnable. Mark `partial` and enumerate uncovered roots/adapter capabilities.
2. **A workflow's working directory changes discovery scope**; shell quoting, CI container environment and step-specific defaults matter. Avoid severity high for a synthetic CI-gap absent after path resolution.
3. **A unit test with doubles should not be promoted to an integration claim** because of filename, `npm run test:integration`, or mock count. Conversely, the same repo did run a separate real MySQL/Mosquitto E2E.
4. **CI green is revision-bound and environment-bound.** A copied source, a real device, a broker in production and a server with TLS are different boundaries. The TCC CI has 4 workflows green on merge SHA, but no physical HIL or actual Android/FCM.
5. **Mutation must be linked to tool/source/tests and explicitly distinguished from manual probes.** The selected 22 mutants gave useful local evidence; they do not justify a whole-project score, and none was engine-generated.
6. **Unknown adapters must not become "not tested" across the full project**, nor be quietly called PASS. A useful report names the unsupported command/runner and the independent evidence that is available.
7. **This is one project, selected by the user.** Findings are transfer hypotheses for Assertiva; validate them against independent fixtures/confirmation cases before altering core heuristics, severities or published coverage claims.

## 6. Suggested implementation backlog

See [TCC dogfood improvement proposals](2026-10-25-tcc-improvement-backlog.md) for prioritized changes, concrete acceptance checks, non-goals and evals. No feature is marked implemented by publishing this record.

## Source links

- TCC [auditor report](https://github.com/Soturine/tcc/blob/main/docs/quality/test-audit-assertiva-2026-10-25.md)
- TCC [P2.1 implementation evidence](https://github.com/Soturine/tcc/blob/main/docs/quality/p2-1-implementation-evidence-2026-10-25.md)
- TCC [WEDA-FALL and Nyquist research](https://github.com/Soturine/tcc/blob/main/docs/research/wrist-baseline-weda-fall-2026-10-25.md)
- TCC [PR #11](https://github.com/Soturine/tcc/pull/11); [merge commit](https://github.com/Soturine/tcc/commit/513157c6a150b9761d8c4c968c6a66a88e458ee0)
