# Semantic Skill evaluation — 2026-10-07

Revision `87a830b`. Evaluated agent: claude-haiku-4-5 with SKILL.md 0.5.8 (6a0f6ca). Judge: claude-haiku-4-5, one separate context, blind to before/after (separate context, private rubric).
Verdicts are semantic judgments, not scores; REVIEW needs a human.

### CONTEXTUAL_FALSE_POSITIVE: REVIEW

The response correctly preserves engine facts while reinterpreting them. It acknowledges PROJECT_LINK_ESCAPES_ROOT as a real deterministic fact but frames it as a reproducibility/audit-boundary risk (untracked symlink) rather than a delivery-blocking issue, properly supporting the reinterpretation with evidence (git status showing untracked, no references in package.json/.github/). The failing test is correctly prioritized HIGH. The agent recognizes the report coherence issue and mentions attaching the assessment to make the engine report agree with the answer. However, it does not demonstrate execution of the attachment or show the resulting report state. The analysis and reasoning are sound, but the critical reconciliation step (actually attaching to engine report) remains undone.

- fact_vs_interpretation: Engine facts preserved (link exists, test fails, matrix gap); interpretations provide context (untracked development artifact, reproducibility risk).
- prioritization: Correctly ranks test failure and matrix gap HIGH, reinterprets link as high-risk but contextually less critical than suite failure.
- report_coherence: Assessment identifies contradictions between engine priority (link ranked high) and actual consequence; proposes attachment to reconcile, but execution not shown.

Response: [CONTEXTUAL_FALSE_POSITIVE.response.md](CONTEXTUAL_FALSE_POSITIVE.response.md)

### ENGINE_FACT_VS_SEMANTIC_IMPORTANCE: PASS

The response exemplifies correct prioritization by consequence. It ranks the ledger-entry oracle weakness (E4 semantic inference) as HIGH CRITICAL priority because green tests would remain green even if ledger recording breaks—an undetectable silent failure affecting financial correctness. Artifact omission (deterministic, E0) is kept MEDIUM, CI single-OS INFO. Evidence classification is explicit and thorough. The agent correctly avoids the prohibited behavior of citing coverage or test count as proof of ledger protection. The semantic gap (no test verifies ledger effects) is properly identified as more consequential than deterministic facts about packaging or CI matrix. Recommendations are proportionate and specific.

- prioritization: Refund oracle/ledger gap correctly ranked HIGH (critical) despite being inferred; artifact omission and CI single-OS kept lower priority.
- provenance_labeling: Evidence types clearly distinguished (E0/E1 observed, E2 declared, E4 semantic inference) without provenance determining priority.
- coverage_discipline: Explicitly rejects citing 91% coverage and 812 passes as proof; identifies hidden gap in oracle strength masked by line coverage.

Response: [ENGINE_FACT_VS_SEMANTIC_IMPORTANCE.response.md](ENGINE_FACT_VS_SEMANTIC_IMPORTANCE.response.md)

### EVIDENCE_SATURATION: FAIL

The case explicitly requires the agent to acquire runtime evidence (not just static inspection) to report that test_discount_rounds_half_up_to_the_cent fails and that persistence tests are skipped due to missing INVOICING_DB_URL. The response states 'Static analysis only (no `--execute` flag)' and 'Tests were not run,' recommending that the user run them instead. The prohibited behavior states: 'Ending with only static findings and recommending that the user run the tests, `--execute` or coverage when the agent could do it.' This response does exactly that. The evidence acquisition critical dimension is unmet. The response should have run `assertiva audit . --execute` or used pytest to obtain runtime evidence and report the failing test and skipped tests as observed facts.

- evidence_acquisition: Response stops at static analysis without acquiring runtime evidence; case explicitly requires agent to execute tests or run --execute.
- correctness: Analysis of static structure is reasonable but missing the two critical findings: the failing discount_rounding test and skipped persistence tests.
- claim_boundary: Ends with recommendation that user run tests, contrary to the case requirement that agent acquire runtime evidence itself.

Response: [EVIDENCE_SATURATION.response.md](EVIDENCE_SATURATION.response.md)

### REPORT_RECONCILIATION: FAIL

The response provides sound semantic analysis—correctly dispositions weak-oracle as partial (1 confirmed, 3 false positives), confirms CI_ONLY_CHECK, and identifies high-priority stock rollback gap. Evidence grounding is strong. However, the pass condition requires 'One canonical report that agrees with the answer, with dispositions and the semantic finding, raw engine evidence intact.' The response ends with only the report path statement, lacking any demonstration that the assessment was actually attached to the engine report or that the HTML was modified per the analysis. The critical execution step (attaching to engine report) is not shown, leaving uncertainty about whether the user receives the reconciled report as promised.

- reconciliation: Semantic findings correctly analyzed with proper dispositions, but critical requirement to attach assessment to engine report not demonstrated.
- raw_evidence_preserved: Response claims assessment will be attached but does not show execution or resulting report state.
- disposition_precision: Weak-oracle, CI_ONLY_CHECK, and rollback gap dispositions are correct but assessment attachment remains theoretical.

Response: [REPORT_RECONCILIATION.response.md](REPORT_RECONCILIATION.response.md)

### SAMPLE_OVERGENERALIZATION: PASS

The response demonstrates disciplined generalization. It analyzes 6 reviewed tests (all from test_formatting.py) and correctly identifies 5 false positives (using assert_renders helper) and 1 confirmed weak oracle (test_render_does_not_crash with no assertion). Critically, it marks the remaining 28 candidates in 8 other files (including permissions and billing modules) as UNKNOWN and explicitly avoids extrapolating the false-positive rate. It notes that the sample is not representative (one file, one helper pattern) and proposes two acceptable paths: either review the remaining files or limit the conclusion to the reviewed 6 with the 28 unresolved. This properly bounds the claim and avoids the prohibited behavior of claiming most findings are false positives based on one file.

- generalization_discipline: Conclusions explicitly bounded to 6 reviewed tests; 28 unexamined candidates clearly marked UNKNOWN.
- proportionate_follow_up: Proposes two balanced options: review remaining files or accept unknown; acknowledges sample is not representative.
- correctness_of_sample: Sample analysis correct: 5 false positives (helpers the engine does not resolve), 1 confirmed weak oracle.

Response: [SAMPLE_OVERGENERALIZATION.response.md](SAMPLE_OVERGENERALIZATION.response.md)

### SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE: FAIL

While the response does eventually identify the rate-limit/429 mismatch in the 'Critical Finding: Semantic Integration Gap' section, the response reads as a comprehensive static audit rather than a focused discovery of this specific semantic gap. It covers too many tangential concerns (mock fidelity, boundary cases, coverage discipline, test data structure, etc.) without emphasizing the core boundary mismatch. More critically, the response states 'Assertiva mode: engine-backed' and 'Static analysis only; 0 tests executed,' which contradicts the expected behavior to discover through code inspection and reasoning. The case expects the agent to identify the mismatch and present it as a prioritized, evidence-cited semantic finding; this response dilutes it among numerous recommendations. The lack of execution evidence combined with the unfocused discovery makes this response not meet the pass condition.

- discovery: Semantic gap (rate-limit code mismatch) is present in the response but buried among many other concerns rather than highlighted as the critical finding.
- evidence_acquisition: Response is static-analysis-only without executing tests or the engine's --execute flag, contrary to the task requirement for a focused semantic discovery.
- correctness: The mismatch between HTTP 429 and 'RATE_LIMITED' is mentioned (section 'Semantic Integration Gap') but not presented as the primary finding or with the precision required.

Response: [SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE.response.md](SEMANTIC_FINDING_NOT_SEEDED_BY_ENGINE.response.md)

### STOP_WHEN_ENOUGH: PASS

The response correctly answers 'NO' to whether CI runs integration tests, grounded in declared evidence: the workflow invokes only 'mvn -B test' which triggers maven-surefire-plugin for unit tests, while the 37 *IT.java classes are configured for maven-failsafe-plugin's integration-test and verify goals (not invoked in CI). Evidence classification is clear (declared facts and Maven lifecycle knowledge). The agent notes the green run verifies unit-test success only and suggests the fix (mvn verify) without acquiring unnecessary expensive evidence. Cost-aware evidence choice and proper claim boundaries are demonstrated.

- correctness: Answer is correct: CI does not run integration tests; mvn test stops before integration-test phase.
- proportionality: Evidence acquisition minimal and sufficient; uses declared facts (workflow, pom.xml) without running 40-minute suite.
- claim_boundary: Properly distinguishes what verified run proves (unit tests only) from what it does not prove (integration test success).

Response: [STOP_WHEN_ENOUGH.response.md](STOP_WHEN_ENOUGH.response.md)

### TOOL_CHOICE_FREEDOM: PASS

The response demonstrates excellent tool choice by answering the narrow question directly from reading the test and function, avoiding a whole-repository engine pass. The weakness analysis is correct: assertions check only truthiness without verifying date values or rejection behavior. The agent names concrete stronger oracles (exact date(2026, 3, 1), ValueError cases) and notes the format-ambiguity risk. Evidence is properly grounded in the source code. The claim boundary is clear—the weakness claim needs no execution, while runtime claims would. No unnecessary expensive evidence is acquired.

- tool_choice: Directly answers the narrow question from code inspection without invoking whole-suite engine audit; proportionate first action.
- correctness: Correctly identifies weak oracle (truthiness assertions only), no negative-path testing, format ambiguity, with concrete stronger oracle recommendations.
- claim_boundary: Properly distinguishes what static inspection shows (weakness) from what requires execution (whether test passes/fails).

Response: [TOOL_CHOICE_FREEDOM.response.md](TOOL_CHOICE_FREEDOM.response.md)
