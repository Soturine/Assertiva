# External browser, market-model, agent-budget and Android skills intake — 2026-11-03

**Status:** code-and-document review; candidates NOT_RUN; no new analyzer, third-party runtime execution, model score, or security findings. Related Framework [PR #11](https://github.com/Soturine/Derivanta/pull/11), Engine [PR #2](https://github.com/Soturine/Derivanta-Engine/pull/2), both unmerged proposals.

## Audited references and test-strength implications

| Source | Selected code/docs inspected | Test false-green hazard | Existing-owner intersection |
|---|---|---|---|
| [Lightpanda](https://github.com/lightpanda-io/browser) | AGENTS.md leak-detecting Zig test runner; agent-regression.yml; README compatibility, benchmark, WSL2 and source tree | A headless/Playwright test reports PASS after an unsupported/skipped browser operation; required DOM or persisted effect not observed | Browser, platform matrix, E2E and UI oracles |
| [WebToApp](https://github.com/shiaho777/web-to-app) | AGENTS.md app/shell sync, ApkArtifactVerifier.kt, NativeBridge.kt, Android instrumented test tree | A preview or signed ZIP is correct for its scope, but generated APK/runtime has stale shell/config/capabilities | Mobile E2E, runtime boundary, test fidelity |
| [Paperclip](https://github.com/paperclipai/paperclip) | docs/agents-runtime.md, approval/cost API, heartbeat budget cancellation code search | Budget test has one simulated agent; concurrent wakeups/delayed provider bill escape hard cap | Retry/failure, side effects, concurrency |
| [Kronos](https://github.com/shiyu-coder/Kronos) | seeded pinned-revision model regression, stored-prediction backtest script | Prediction regression green does not prove fee-inclusive out-of-sample profitable execution | Weak-oracle/selection leakage; Framework Market/Quant owns edge |
| [correlation](https://github.com/bhoult/correlation) | README, ANALYSIS.md, test-results.md | Selecting only successful strategies hides the null trials and search cost | DrawLab selection leakage, baselines and evidence honesty |

Screenshot-only sources: KAKIGOLD signal chart; twenty-item agent/Claude Skills list; NotFair, ThreeUI, AutoHedge, trading-bot catalog and market commentary. They indicate relevant hypotheses, not proven implementation or performance. No financial strategy, trading order, production provider action or live Android device was run.

## New candidates and exclusion of duplicative automatic heuristics

- BROWSER_ALTERNATIVE_CAPABILITY_FALSE_GREEN: independent browser effect oracle and unsupported/skip accounting. Related existing E2E_BLIND_RERUN, PLATFORM_MATRIX_COLLAPSE, MOCKED_AWAY_INTEGRATION and ARIA_SCAN_FALSE_CONFIDENCE.
- ANDROID_PREVIEW_EXPORT_PARITY_FALSE_GREEN: preview/config/shell/APK/installed-device evidence, positive and denied-origin paths. Related TCC_ANDROID_GRADLE_COMPOSE_EVIDENCE_BOUNDARIES and MOCK_AWAY_INTEGRATION_BOUNDARY.
- Budget enforcement under concurrency, Kronos predictive regression vs net PnL, and token-compression evidence truncation are recorded as candidate questions only. Do not add cases duplicating TRANSACTION_HARNESS_MASKS_COMMIT_BEHAVIOR, HIGH_COVERAGE_WEAK_ORACLE, DRAWLAB_SELECTION_LEAKAGE, COST_AWARE_HEAD_EVIDENCE_ORDERING or EVIDENCE_NOT_WORTH_ITS_COST without a distinct calibrated failure mode.

A green archive test is valid evidence of archive integrity and a green preview is valid for preview. It is only false confidence when broadened to unsupported device/runtime effects. Device APK certification and Browser WPT qualifications are outside Assertiva's current engine. Run semantic skill evaluation with fixed synthetic fixtures, independent private rubric and failures retained; only promote a deterministic detector after precision/recall on labeled positive and negative projects. All these new cases remain NOT_RUN.
