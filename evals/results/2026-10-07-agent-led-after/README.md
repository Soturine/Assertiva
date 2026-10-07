# Semantic Skill evaluation — 2026-10-07

Revision `87a830b`. Evaluated agent: claude-haiku-4-5 with the agent-led SKILL.md (a5a3967). Judge: claude-haiku-4-5, one separate context, blind to before/after (separate context, private rubric).
Verdicts are semantic judgments, not scores; REVIEW needs a human.

### CONTEXTUAL_FALSE_POSITIVE: REVIEW

The response correctly handles the fact-vs-interpretation challenge. It keeps the engine fact (PROJECT_LINK_ESCAPES_ROOT is real) but contextualizes it as an untracked development artifact not part of the product, build, or CI. Prioritization is sound: failing test and matrix gap are HIGH, link is reprioritized to INFO based on evidence (git status, absence from package.json/.github/). The agent proposes attaching the assessment to the engine report to reconcile the answer with the HTML display, showing awareness of the requirement. However, like J01/J06, it does not demonstrate execution of the critical step (actually attaching to the report or showing the result). A human should decide if the clear contextual reasoning and proposed attachment mechanism are sufficient, or if execution proof is required for full PASS.

- fact_vs_interpretation: Correctly preserves engine fact (link exists and escapes root) while reinterpreting priority as contextual/info.
- prioritization: Properly ranks failing test and matrix gap as high priority, deprioritizes the link as info-level (untracked development artifact).
- report_coherence: Assessment and answer coherently identify the contexts (untracked, not in package.json/CI) but report attachment mechanism not demonstrated.

Response: [CONTEXTUAL_FALSE_POSITIVE.response.md](CONTEXTUAL_FALSE_POSITIVE.response.md)

### ENGINE_FACT_VS_SEMANTIC_IMPORTANCE: PASS

The response correctly prioritizes findings by consequence rather than provenance. The refund oracle/ledger gap (inferred from code inspection) is ranked HIGH as the critical finding, while artifact omission (deterministic) is kept MEDIUM and CI single-OS INFO. The agent explains that high line coverage and passing tests mask weak oracle strength in ledger verification, properly distinguishing between line coverage and semantic correctness. All evidence is labeled with its classification. The provenance labeling supports rather than drives the ranking, and the safety implications of ledger verification gaps correctly elevate the inferred finding above the deterministic ones.

- prioritization: Refund oracle/ledger gap correctly ranked first (high consequence) despite being inferred; deterministic findings kept lower.
- provenance_labeling: Evidence types clearly labeled (E0/E1 observed, E2 declared, E4 inferred) without letting provenance drive priority.
- coverage_discipline: Avoids citing 812 passes and 91% coverage as proof that refunds are protected; correctly identifies mock-induced false assurance.

Response: [ENGINE_FACT_VS_SEMANTIC_IMPORTANCE.response.md](ENGINE_FACT_VS_SEMANTIC_IMPORTANCE.response.md)

### EVIDENCE_SATURATION: PASS

The response demonstrates excellent evidence acquisition. It executes the test suite and reports deterministic outcomes: 6 passed, 1 failed (discount rounding), 2 skipped (storage module). The failing test is identified with specific assertion error and execution evidence. Storage tests are correctly reported as completely untested due to the skip gate (INVOICING_DB_URL not set). Coverage metrics (74.4% line, 64.3% branch) are reported from execution. Evidence types are clearly labeled (OBSERVED vs INFERRED vs UNKNOWN). The response correctly never counts skipped tests as passed. Recommendations are grounded in observed facts. The agent follows the acceptable alternative of using engine execution without modifying project files.

- evidence_acquisition: Agent acquires runtime evidence through execution: reports test outcomes (6 passed, 1 failed, 2 skipped), coverage metrics (74% line, 64% branch).
- correctness: Correctly identifies failing test (test_discount_rounds_half_up_to_the_cent) as observed fact and storage tests completely untested due to skip gate.
- claim_boundary: Properly distinguishes OBSERVED (execution evidence), INFERRED (code inspection), and UNKNOWN (unavailable without GitHub access); skipped tests never counted as passed.

Response: [EVIDENCE_SATURATION.response.md](EVIDENCE_SATURATION.response.md)

### REPORT_RECONCILIATION: REVIEW

The response improves on simpler answers by providing a structured JSON assessment that could attach to an engine report, with clear dispositions per test and the semantic finding included. The analysis is sound: 3 tests are false positives (using assert_problem helper), 1 confirmed weak oracle, CI_ONLY_CHECK stays confirmed, rollback gap is high-priority. The JSON structure suggests understanding of engine attachment. However, the pass condition requires 'One canonical report that agrees with the answer' with the assessment actually attached. The response states the engine will re-render the report but does not show execution (the `assertiva audit . --assessment` command being run, the resulting HTML, or proof of attachment). A human should decide if providing the structured JSON in the correct format and stating attachment intent meets the pass condition, or if execution proof is required.

- reconciliation: Semantic findings correctly analyzed; JSON assessment format provided shows understanding of engine-supported attachment mechanism.
- raw_evidence_preserved: Assessment JSON indicates intentions to preserve raw engine evidence, but actual execution not demonstrated.
- disposition_precision: Dispositions are correct and detailed in JSON (WEAK_ORACLE_SIGNAL partial with per-test disposition, CI_ONLY_CHECK confirmed, stock-rollback-gap finding added).

Response: [REPORT_RECONCILIATION.response.md](REPORT_RECONCILIATION.response.md)

### SAMPLE_OVERGENERALIZATION: PASS

The response correctly bounds conclusions to the 6 reviewed tests from test_formatting.py: 5 are false positives (using assert_renders helper that the engine missed), 1 is a confirmed weak oracle (no assertion). It explicitly marks the remaining 28 tests in 8 other files as UNKNOWN without review. The response notes the sample is not representative (one file, one helper pattern) and proposes two clear paths forward: either review the remaining files or leave them unresolved with explicit acknowledgment. This avoids overclaiming and prohibits population-level conclusions, properly demonstrating generalization discipline as required.

- generalization_discipline: Sample conclusions strictly bounded; remaining 28 candidates marked UNKNOWN; no extrapolation to the full 34-test population.
- proportionate_follow_up: Provides balanced recommendations: either review remaining 8 files or accept the unresolved state; acknowledges sample limitations.
- correctness_of_sample: Analysis of 6 reviewed tests correct: 5 false positives through helpers, 1 confirmed weak oracle (test_render_does_not_crash).

Response: [SAMPLE_OVERGENERALIZATION.response.md](SAMPLE_OVERGENERALIZATION.response.md)

### SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE: PASS

The response demonstrates excellent semantic discovery. It identifies that tests mock away the actual error-code transformation: the real gateway raises GatewayError('HTTP 429') but tests inject GatewayError('RATE_LIMITED'), so production rate-limiting would be misclassified as permanent failure. The finding is grounded in specific code lines and complemented with grep results showing no mapping exists. The agent properly labels this as inferred from code inspection, not engine-detected or execution-proven, and emphasizes it as a deterministic mismatch. The contract gap at the test-double boundary is correctly identified as high-impact despite the engine reporting no weak oracles. Safety implications are explicit.

- discovery: Correctly identifies the critical rate-limit/429 code mismatch at the service-gateway boundary, a contract gap masked by test doubles.
- grounding: Evidence cited with precision: service.py line 22 (RATE_LIMITED check), gateway.py line 27 (HTTP status format), test_service.py line 21 (mock bypass), grep results showing no 429 mapping.
- claim_labeling: Finding properly labeled as high-impact inference from code inspection, not engine output or execution proof; test-double seam issue clearly explained.
- safety: Correctly recognizes that production rate-limiting would fail silently while tests pass; identifies as regression risk.

Response: [SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE.response.md](SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE.response.md)

### STOP_WHEN_ENOUGH: PASS

The response correctly answers 'no' to whether CI runs integration tests, with strong grounding in declared evidence: the workflow runs 'mvn -B test' which invokes only maven-surefire-plugin, while maven-failsafe-plugin's 37 *IT.java classes require the verify goal. The agent notes the confirmed run proves unit-test success only, and suggests the fix (mvn verify) without running the 40-minute suite. Evidence is properly classified (DECLARED and INFERRED from Maven standard behavior). The answer demonstrates cost-aware evidence choice and respects claim boundaries.

- correctness: Answer is correct: CI does not run integration tests because mvn test stops before the integration-test phase.
- proportionality: Evidence acquisition is minimal and sufficient; declared facts (workflow, POM, Maven lifecycle) answer the question without expensive runs.
- claim_boundary: Properly distinguishes what green CI proves (unit tests only) from what it does not prove (integration tests).

Response: [STOP_WHEN_ENOUGH.response.md](STOP_WHEN_ENOUGH.response.md)

### TOOL_CHOICE_FREEDOM: PASS

The response demonstrates excellent tool choice by answering directly from reading the test and function code, avoiding a whole-repository engine pass. Written in Portuguese as the case specifies. The weakness analysis is correct: assertions check only truthiness without verifying returned date values or testing the documented rejection contract. The agent identifies three specific weaknesses (weak oracle, missing negative path, missing format disambiguation) and provides concrete stronger test code showing date equality assertions and ValueError cases. The claim boundary is clear—the weakness claim is valid from static inspection; runtime correctness claims would require execution. No unnecessary expensive evidence is acquired.

- tool_choice: Answers narrow question directly from code inspection in Portuguese; avoids whole-suite engine invocation; proportionate tool choice.
- correctness: Weakness correctly identified: truthiness assertions only, no value verification, no rejection-path testing, format ambiguity.
- claim_boundary: Properly distinguishes between what static inspection proves (weakness) and what requires execution; provides concrete stronger oracles.

Response: [TOOL_CHOICE_FREEDOM.response.md](TOOL_CHOICE_FREEDOM.response.md)

## How to read this run

- Same evaluated model on both sides (claude-haiku-4-5), one response per case, judged by one Haiku context that saw anonymized folders (J01–J16) and did not know which side a response came from. It is evidence about these cases, not a benchmark: n = 1 per case and the judge is of the same family.
- Before vs after: EVIDENCE_SATURATION, SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE and REPORT_RECONCILIATION moved from FAIL; nothing regressed. The before agents ran against the same engine (which already accepted `--assessment`); only the Skill differed.
- The two REVIEW verdicts are on context-only cases, where the agent may not run commands, so it cannot show that the assessment was attached; the judge asked for that demonstration. Both answers keep the engine fact, restate its priority with evidence and plan the attachment.
- Defect found by this run and fixed after it: in REPORT_RECONCILIATION the agent marked tests that are *not* weak as `CONFIRMED` subjects; `references/ENGINE.md` now states that a disposition is about the engine's claim, item by item.
