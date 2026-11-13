# Cross-project dogfood intake — BeamNG Randomizer v0.7.12

**Status:** evidence intake / remediation candidates, **not fixes**.  
**Date:** 2026-11-02. **Instrument:** Assertiva v0.10.1, commit `2618d95`.  
**Consumer:** [Soturine's Chaos Randomizer v0.7.12](https://github.com/Soturine/beamng-soturine-chaos-randomizer/releases/tag/v0.7.12), source audit at `e1610ed` during the release cycle; published final commit `fccc561`.  
**Source evidence:** [dogfood narrative](https://github.com/Soturine/beamng-soturine-chaos-randomizer/blob/v0.7.12/docs/assurance/ASSERTIVA_DOGFOOD_v0.7.12.md), [machine-readable feedback](https://github.com/Soturine/beamng-soturine-chaos-randomizer/blob/v0.7.12/docs/assurance/ASSERTIVA_FEEDBACK_v0.7.12.json), [functional audit](https://github.com/Soturine/beamng-soturine-chaos-randomizer/blob/v0.7.12/docs/testing/v0.7.12/AUDIT_REPORT.md), [Lua module inventory](https://github.com/Soturine/beamng-soturine-chaos-randomizer/blob/v0.7.12/docs/testing/v0.7.12/LUA_MODULE_INVENTORY.md).

This document preserves the **original Opus investigation** and adds an **independent source/contract review** of the published Randomizer reports and Assertiva's current README, STATUS and ROADMAP. The independent review **did not rerun Assertiva, reconstruct the ephemeral report files, or independently reproduce the Windows failures**. Results below remain attributed to the recorded run; new reviewer conclusions are labelled as such.

## Run receipts and evidence boundaries

| Run | Recorded outcome | Boundary |
| --- | --- | --- |
| `assertiva audit <repo>` | exit 0, 49 s, findings, run `979406beddba4089` | static; not a pass on project tests |
| `audit --execute --python <python.exe> --timeout-s 600 --ctrf` | exit 0, 49 s, pytest-native 51 PASS and Vitest 38 PASS; run `d45ddf58bf63486c` | native adapters selected some suites, not the full `npm run verify` |
| `audit --junit-xml lua-junit.xml` | 458 Lua cases ingested PASS, run `4c7ce0f7efb74c9c`, report digest `492f6380977063c2b890087411dbdc47d782c13651f0e787269c649be4394b81` | externally executed evidence **ingested**, not executed by Assertiva |
| Separate Randomizer verification | 458 Lua cases, 1,190 Node contract checks, Python unittest, mounted Vue, package/module/style gates | declared and/or independently run by the original investigator; **not all discovered or executed by Assertiva** |

Source notes preserve a static report and an execute report in a temporary scratchpad, but those full files were **not committed or uploaded** to the Randomizer repository. Do not claim their raw JSON/HTML is attached here. The published JSON feedback and prose are the durable portable receipts.

## Finding disposition — original auditor versus independent review

| ID | Assertiva signal / opportunity | Opus disposition and evidence | Independent review / next action |
| --- | --- | --- | --- |
| AXR-01 | Lua not classified as a primary language | Project reported JavaScript 40/56 despite 106 extension Lua modules | **Confirmed as reported from recorded output**; add Lua discovery with confidence and not claim runner support based on file count |
| AXR-02 | Nested custom runner collapsed | 458 Lua cases reside under one Python `test_lua` wrapper; native execute reports 51 Python test invocations and 38 Vitest | **Strong evidence gap**; either report nested runner opacity or support imported per-case JUnit/CTRF provenance without double counting |
| AXR-03 | `LOCAL_CHECK_NOT_OBSERVED_IN_CI` [HIGH] | Report says missing `verify` while `.github/workflows/ci.yml` invokes `npm run verify` | **False positive for this consumer**, subject to existing script-chain parser; resolve `package.json -> tools/verify.py -> unittest` with bounded recursion |
| AXR-04 | `CI_PYTEST_NOT_OBSERVED` | Project runs Python `unittest`, not pytest, through the wrapper | **Misclassified runner evidence**; do not imply pytest required to obtain test coverage |
| AXR-05 | `NESTED_SCRIPT_REPETITION` | `verify` appears in push/tag/manual workflows for different triggers | **False duplication conclusion** in this case; account for trigger, job and artifact surfaces before suppressing "redundancy" |
| AXR-06 | Contradictory severity | HIGH "not observed in CI" alongside INFO listing same CI invocation | **Consistency issue**, strong candidate for shared canonical script identity |
| AXR-07 | `FALSE_GREEN_CANDIDATE` conditional assertion in `test_beamng_api_boundary` | Manual negative control: baseline exit 0, defect injected in disposable `raceManager.lua` copy exit 1 (KILLED) | **Rejected for this test**; keep heuristic as a *candidate*, improve loops/subTest and guarded-condition reasoning |
| AXR-08 | `CI_ONLY_CHECK` | Byte-identical Windows/Linux package and tag-to-VERSION are genuinely CI-specific; core `verify` is not | **Partly valid**; report per-check provenance rather than global CI-vs-local green status |
| AXR-09 | `UNCLASSIFIED_VERIFICATION` | `npm run verify` remains UNKNOWN | **Correct UNKNOWN**, but improve bounded command tracing; no blind execution of arbitrary scripts |
| AXR-10 | `ARTIFACT_LINEAGE_UNKNOWN` | Release workflow publishes build job's validated artifact; manifest binds commit/hash | **Partly valid**: recognize declarative chain, keep download/installation verification UNKNOWN unless observed |
| AXR-11 | Node contract script outside Vitest | `node tests/js/vue_runtime.test.mjs` with 1,190 checks not recognized as verification | **Coverage gap**; characterize direct Node runners without pretending per-check granularity is native |
| AXR-12 | Windows `core.longpaths` | Deep temporary checkout failed; re-clone with `git -c core.longpaths=true` worked | **Environment friction**; shorten fixture layout/preflight paths; do not alter global Git config |
| AXR-13 | `PIP_NO_BUILD_ISOLATION=0` + setuptools | Fresh venv build failed; install recovered after build-requirement adjustment | **Environment-dependent**, not blanket product defect; document and detect before suggesting install |
| AXR-14 | `--python` missing `.exe` on Windows | CLI rejected path with no `.exe`; explicit executable worked | **Repro candidate**; improve path resolution or error text without ambiguity |

## What the agent found that the engine did not

1. GE mocked AI getter methods not provided by BeamNG 0.40.4; AI sent commands but false "running" status was possible. The v0.7.12 investigator replaced that with a Vehicle Lua `ai.mode` probe. This is **external API fidelity drift**, not an obligation for Assertiva to know BeamNG internals.
2. Wrong expectation in an existing test: Destination/Route were expected to confirm `traffic`, whereas `ai.driveUsingPath` produces `manual`. An AI agent reviewing actual engine code caught this; same-wrong-assumption mocks remain a meaningful assurance pattern.
3. Vue module graph checker validated host module *specifier*, not exported *symbol*. A `vBngPanel` negative fixture now proves that removed 0.40 exports fail validation. This illustrates a strong consumer-contract negative control.
4. Release gate made truthful live failures unpublishable for experimental releases; validator policy corrected without marking live tests passed.
5. Release title in workflow was hard-coded, causing v0.7.11 to retain the v0.7.10 title. CI drift detection opportunity.

These five findings are **agent/manual findings from the source investigation**, not Assertiva detections. An independent review confirms the v0.7.12 [audit report](https://github.com/Soturine/beamng-soturine-chaos-randomizer/blob/v0.7.12/docs/testing/v0.7.12/AUDIT_REPORT.md) records the code changes; it does **not** claim to have re-run the BeamNG process.

## Limits and unexecuted work

- No BeamNG 0.40.4 live gameplay execution. **0/18** owner test cases executed; no claims about FPS, physical AI motion, split-screen runtime or Preview pixels.
- No `assertiva --mutate` run: the project's Lua suite has no supported mutation adapter and required tools were not installed. Instead, the original audit reports **seven targeted Lua mutants killed** and one Python boundary negative control killed; the ephemeral mutation script is not published.
- No Assertiva source code modified, no fixes tested in Assertiva itself, no Assertiva release implied.
- This PR contains **intake documentation only**, preserving defects, false positives, limits and follow-up designs.

## Proposed remediation / qualification plan (separate implementation PR)

1. **P0 evidence fidelity:** bounded script resolution for npm/Node/Python wrappers; normalize identity across CI/local analyzers; add opposing-case regression fixtures for `verify`.
2. **P1 coverage:** recognize Lua from files while preserving `RUNNER_UNSUPPORTED/UNKNOWN`; support a deliberate JUnit bridge with provenance and per-case IDs; detect direct Node contract runners.
3. **P1 correctness:** control negatives for conditional-assertion false positives, CI trigger-aware duplication, artifact provenance tiers (declared vs executed vs downloaded).
4. **P2 Windows UX:** safe short scratch paths, documented `core.longpaths` and `PIP_NO_BUILD_ISOLATION` behavior, Python executable lookup.
5. Dogfood the **new Assertiva changes on Randomizer v0.7.12 and on Assertiva itself**, record before/after findings and killed negatives, then re-check Derivanta-Engine; preserve every UNKNOWN that cannot be settled.

Avoid blanket new gates, arbitrary test counts and unmeasured speed claims.
