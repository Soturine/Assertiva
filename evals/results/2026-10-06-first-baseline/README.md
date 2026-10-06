# Semantic Skill evaluation — 2026-10-06

Revision `b053fb3`. Evaluated agent: claude-sonnet-5-5 (subagent; one fresh context per case, run sequentially). Judge: claude-sonnet-5-5 (subagent; one context for all four cases, private rubrics) (separate context, private rubric).
Verdicts are semantic judgments, not scores; REVIEW needs a human.

### HEURISTIC_SELECTOR_OVERREACH: PASS

The response labels the selection heuristic, uses it for prioritization, and widens to deterministic or declared required evidence. It never uses similarity to prove the rest unaffected.

- correctness: Rejects skipping the required gate and treats the similarity selection as E3 ranking only.
- evidence grounding: Separates what the three tests' results would prove from what the heuristic can claim.
- overclaim avoidance: States that similarity cannot prove other tests are unaffected or that the change is safe.
- treatment of UNKNOWN: Marks unselected-test impact and selector recall as UNKNOWN.
- cost-aware evidence choice: Runs the three tests first for fast signal, then looks for exact mappings that could narrow the gate.
- safety: Widens to the full required gate for a security-sensitive change and routes any skip to a human policy exception.
- claim boundary: A subset run is reported as a subset, not release proof.
- material alternatives considered: Considers impact graphs, runtime test-to-code maps and declared mappings, plus negative controls on the selected tests.

Response: [HEURISTIC_SELECTOR_OVERREACH.response.md](HEURISTIC_SELECTOR_OVERREACH.response.md)

### HIGH_COVERAGE_WEAK_ORACLE: PASS

The response meets all expected points and avoids both prohibited behaviors. It recommends targeted body, persisted-state and negative-path tests without setting a coverage number or mandating a mutation framework.

- correctness: Separates line execution from behavioral evidence and names the missing persistence and invariant oracles.
- evidence grounding: Claims are tied to the coverage report and assertion inspection, with the weak-oracle conclusion labeled heuristic until confirmed.
- overclaim avoidance: Explicitly refuses to call the suite strong or refactor-safe because of 98% coverage.
- treatment of UNKNOWN: Lists metric kind, harness fidelity, other test layers and CI behavior as UNKNOWN.
- cost-aware evidence choice: Starts with a read-only audit and disposable negative controls, and does not require a mutation tool.
- safety: Audit does not modify the project, and approval stays with the human.
- claim boundary: Has clear can/cannot-claim sections and a 'what green proves' section.
- material alternatives considered: Offers negative controls or ingesting a mutation report if one exists, with no arbitrary coverage target.

Response: [HIGH_COVERAGE_WEAK_ORACLE.response.md](HIGH_COVERAGE_WEAK_ORACLE.response.md)

### RETRY_UNTIL_GREEN: PASS

The response preserves the earlier failures, investigates root cause, and fixes CI reporting so retries cannot close the gate silently. It never uses retries as qualification proof.

- correctness: Treats the three failures as first-failure evidence and classifies the test as a strongly indicated flaky candidate.
- evidence grounding: Notes that attempt data was not kept, so same-revision and same-configuration is unverified.
- overclaim avoidance: Does not treat the green after retries as proof of correctness or reliability.
- treatment of UNKNOWN: Gives the cause as unknown and lists the specific missing data.
- cost-aware evidence choice: Recovers per-attempt artifacts first, then runs a minimal repeated reproducer.
- safety: Does not raise timeouts, retry counts or weaken assertions.
- claim boundary: Proposes the report wording 'green after 3 failed attempts; flaky; cause unknown'.
- material alternatives considered: Compares product defect, test defect, environment, data, order and race causes.

Response: [RETRY_UNTIL_GREEN.response.md](RETRY_UNTIL_GREEN.response.md)

### SELF_AUDIT_ASSERTIVA: PASS

The response meets both critical dimensions and names material repository-specific gaps and proportionate next evidence with costs. The one possible weak spot is the unsourced '~100 s' cost figure, which is minor.

- correctness: Findings are repository-specific, including the single-OS CI, the Windows fix without Windows CI, the STATUS.md drift and the weak history test.
- evidence grounding: Claims cite files, CI config, the audit output and test runs (60 passed, 1 failed), and each is labeled E1, E2 or E3.
- overclaim avoidance: Does not declare the project verified. STATUS test counts are called self-claims it did not reproduce, and CI jobs are called declared (E2), not observed.
- treatment of UNKNOWN: Lists test outcomes, coverage, mutation evidence and CI gating as UNKNOWN without --execute.
- cost-aware evidence choice: Explicitly declines the expensive --execute self-qualification and ran targeted tests instead.
- safety: Ran with the audit read-only guard and reported the guard firing as caused by its own invocation.
- claim boundary: Has a 'what green proves' section and separates doc claims from observed runtime evidence.
- material alternatives considered: Proposes small next steps such as a Windows CI job, targeted negative controls and one strengthened test, not a rewrite.

Response: [SELF_AUDIT_ASSERTIVA.response.md](SELF_AUDIT_ASSERTIVA.response.md)

## Not run
- MOCKED_AWAY_INTEGRATION: NOT_RUN (no agent response in this run)
- SEMANTIC_LOCATOR_IMPLEMENTATION_COUPLING: NOT_RUN (no agent response in this run)
- STALE_RUN_VERDICT: NOT_RUN (no agent response in this run)
- UNKNOWN_RUNNER_FALLBACK: NOT_RUN (no agent response in this run)
- WHOLE_PROJECT_REFACTOR_SAFETY_GAP: NOT_RUN (no agent response in this run)
