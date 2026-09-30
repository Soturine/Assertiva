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

Future executable evaluation should preserve fixture, model/agent/provider, tool permissions, revision, budgets, result provenance and infrastructure-failure states.
