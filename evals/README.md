# Assertiva Evals

Two kinds of evaluation, never interchangeable:

- **Semantic Skill evaluation** (this folder): an agent using [`SKILL.md`](../SKILL.md) handles a case; a separate judge grades its reasoning and evidence discipline against a private rubric. It evaluates the Skill, not the runtime.
- **Deterministic runtime tests** (`tests/`, CI, and the on-demand runtime self-qualification): they prove the CLI, engine and adapters. A semantic verdict is never evidence that the runtime works, and a green suite is never evidence that an agent reasons well.

Grade behavior, evidence honesty and cost-aware reasoning, not whether an agent repeats Assertiva terminology.

## Hidden-rubric protocol ([`semantic.py`](semantic.py))

1. `python evals/semantic.py prepare --out DIR CASE ...` writes each case's agent context: `SKILL.md`, the case title, context and task, and the allowed tools. Expected/prohibited behavior, evidence requirements, scoring dimensions, acceptable alternatives and the pass condition are private. With `--workspace`, the agent works on a copy of the repository without `evals/`.
2. The evaluated agent answers from that context only (`response.md`; tool use listed in an evidence log).
3. `python evals/semantic.py judge --out DIR CASE ...` writes the judge context: the full case and the response. The judge, in a separate context, returns PASS, FAIL or REVIEW with a justification per dimension: correctness, evidence grounding, overclaim avoidance, treatment of UNKNOWN, cost-aware evidence choice, safety, claim boundary, material alternatives. No score; no keyword, regex, exact-answer or topic-order grading; equivalent answers in other words pass.
4. `python evals/semantic.py record --out DIR --results evals/results/NAME --agent ... --judge ...` validates every verdict and keeps verdicts, justifications, responses and provenance (revision, agent, judge). A missing or malformed verdict is recorded as not judged, never as a pass.

Semantic reasoning may infer freely, but facts must come from evidence: "this oracle looks weak" is inference; "419 tests executed" is deterministic evidence. Runs: [`results/`](results/).

Cases marked **grader-ready** use [CASE_SPEC.md](CASE_SPEC.md) with explicit evidence, scoring, alternatives and pass conditions; compact cases are judged with the same protocol.

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
- [Self-audit of the Assertiva repository](cases/SELF_AUDIT_ASSERTIVA.md)

Each run preserves revision, agent, judge, tool permissions and results; infrastructure failures stay visible.

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
