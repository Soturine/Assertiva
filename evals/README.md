# Assertiva Evals

These cases specify behavioral expectations for future executable evaluation. They are not yet an automated benchmark harness.

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
