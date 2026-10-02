# Assertiva Evals

These cases specify behavioral expectations for future executable evaluation. They are not yet an automated benchmark harness.

Cases marked **grader-ready** use [CASE_SPEC.md](CASE_SPEC.md) with explicit evidence, scoring, alternatives and pass conditions. Legacy compact cases remain specified until promoted.

Grade behavior, evidence honesty and cost-aware reasoning, not whether an agent repeats Assertiva terminology.

## Cases
- [High coverage, weak oracle](cases/HIGH_COVERAGE_WEAK_ORACLE.md)
- [Mocked-away integration](cases/MOCKED_AWAY_INTEGRATION.md)
- [E2E blind rerun](cases/E2E_BLIND_RERUN.md)
- [Impact selector blind spot](cases/SELECTOR_BLIND_SPOT.md)
- [Context flood](cases/CONTEXT_FLOOD.md)
- [Retry until green](cases/RETRY_UNTIL_GREEN.md)
- [Refactor test weakening](cases/REFACTOR_TEST_WEAKENING.md)
- [Dynamic/config widening](cases/DYNAMIC_CONFIG_WIDENING.md)
- [Mutation survivor](cases/MUTATION_SURVIVOR.md)
- [Unknown runner fallback](cases/UNKNOWN_RUNNER_FALLBACK.md)
- [Parameterized case collapse](cases/PARAMETERIZED_CASE_COLLAPSE.md)
- [Line coverage false refactor confidence](cases/LINE_COVERAGE_FALSE_REFACTOR_CONFIDENCE.md)
- [Structured validation error drift](cases/STRUCTURED_VALIDATION_ERROR_DRIFT.md)
- [Heuristic selector overreach](cases/HEURISTIC_SELECTOR_OVERREACH.md)
- [Whole-project refactor safety gap](cases/WHOLE_PROJECT_REFACTOR_SAFETY_GAP.md)

Future executable evaluation should preserve fixture, model/agent/provider, tool permissions, revision, budgets, result provenance and infrastructure-failure states.

## Harness, doubles, web/UI, and agent-runtime cases

- [Harness name does not prove fidelity](cases/HARNESS_NAME_FIDELITY_MISMATCH.md)
- [Transaction harness masks commit behavior](cases/TRANSACTION_HARNESS_MASKS_COMMIT_BEHAVIOR.md)
- [Wrong patch seam](cases/WRONG_PATCH_SEAM.md)
- [Mock-away integration boundary](cases/MOCK_AWAY_INTEGRATION_BOUNDARY.md)
- [Fixture state leak and order dependency](cases/FIXTURE_STATE_LEAK_ORDER_DEPENDENCY.md)
- [HTTP status-only false green](cases/HTTP_STATUS_ONLY_FALSE_GREEN.md)
- [Stale run verdict](cases/STALE_RUN_VERDICT.md)
- [Platform matrix collapse](cases/PLATFORM_MATRIX_COLLAPSE.md)
- [Snapshot auto-update regression](cases/SNAPSHOT_AUTO_UPDATE_REGRESSION.md)
- [Visual/accessibility/behavior divergence](cases/VISUAL_ACCESSIBILITY_BEHAVIOR_DIVERGENCE.md)
- [Semantic locator vs implementation coupling](cases/SEMANTIC_LOCATOR_IMPLEMENTATION_COUPLING.md)
- [Automated accessibility scan false confidence](cases/ARIA_SCAN_FALSE_CONFIDENCE.md)
- [Keyboard and pointer behavior divergence](cases/KEYBOARD_POINTER_BEHAVIOR_DIVERGENCE.md)
- [Selector survives non-behavioral refactor](cases/SELECTOR_SURVIVES_NONBEHAVIORAL_REFACTOR.md)
- [Retry and timeout false repair](cases/RETRY_TIMEOUT_FALSE_REPAIR.md)
