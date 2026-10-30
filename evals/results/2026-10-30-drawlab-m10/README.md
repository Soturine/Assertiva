# Semantic Skill evaluation — 2026-10-30

Revision `8bd6c36`. Evaluated agent: Claude Opus 5.5 subagents (3 isolated contexts, 5 cases each, context-only). Judge: Claude Opus 5.5 subagents (2 contexts separate from the evaluated agents) (separate context, private rubric).
Verdicts are semantic judgments, not scores; REVIEW needs a human.

### CONTEXT_FLOOD: PASS

The response clusters the two failures by fingerprint, returns a compact summary with references (run id, job, step, line ranges, artifact names), loads deeper evidence step by step, and says explicitly 'Never drop skips, retries, environment details, revision or contradictions to save space.' Raw artifacts are kept by reference, and each distinct fingerprint keeps its own representative and count. It does not dump output before forming a hypothesis and does not hide skipped or failure data.

- correctness: Correctly says the run is not green, treats 'related' as a hypothesis to test by fingerprint comparison, and works from structured results rather than raw stdout.
- evidence grounding: Tags each claim with its basis, cites the artifact that would settle it, and says the log, results and screenshots were not seen.
- overclaim avoidance: Refuses to call the failures flaky, refuses to treat the remaining tests as automatically passed, and does not assume a shared cause or revision correspondence.
- treatment of UNKNOWN: Marks as UNKNOWN the counting unit, the revision, the cause class and the skip/retry counts, and gives a fallback statement if access is unavailable.
- cost-aware evidence choice: Escalates progressively (summary, message, context, full trace, screenshots) and deduplicates traces by fingerprint, without blindly rerunning expensive E2E tests.
- safety: Reproduces only in a disposable copy and notes that a local reproduction does not prove CI parity.
- claim boundary: Limits claims to 'CI failure observed', with HEAD correspondence and root cause unknown until checked.
- material alternatives considered: Considers a cascade failure, order dependence, a shared fixture, a pipefail false green, retries, and new versus recurring failures.

Response: [CONTEXT_FLOOD.response.md](CONTEXT_FLOOD.response.md)

### DRAWLAB_BUDGET_PRIZE_VS_PROFIT: PASS

The response says 'No.' to the support question. It explains that 'p_any_prize is P(total prize > 0)' while the README promises P(total prize > cost), and that 'the 0.41 is an upper bound on the claimed quantity, not an estimate of it'. It names an independent oracle: compute P(total prizes > 10.00) by exact enumeration from the official odds and payout table rather than from the code under test, plus a brute-force check of optimality. All three pass conditions are met and no prohibited behavior appears.

- correctness: Correctly separates P(any prize) from P(prizes > cost) and explains that small R$ 2.50 wins remain net losses.
- evidence grounding: Cites the assertion, the 0.41 observation, the R$ 2.50 vs R$ 10.00 relation and the absence of a profit oracle, all from the context, and says it read no files.
- overclaim avoidance: States plainly that the green suite does not support the README claim, and treats 0.41 as an upper bound, not as the chance of profit.
- treatment of UNKNOWN: Marks the claim's truth, the optimizer's objective and exact versus simulated computation as UNKNOWN.
- cost-aware evidence choice: Orders the evidence from cheapest to costliest: a static read of the objective, then exact enumeration, then a brute-force optimality check.
- safety: Suggests no loosening or deletion of the assertion and keeps mutation work in a disposable copy.
- claim boundary: Limits what is proven to P(any prize) > 0.4 for the R$ 10 budget alone.
- material alternatives considered: Considers that the README may be wrong rather than the test, the 'maximizes' gap, simulation flakiness and the break-even boundary.

Response: [DRAWLAB_BUDGET_PRIZE_VS_PROFIT.response.md](DRAWLAB_BUDGET_PRIZE_VS_PROFIT.response.md)

### DRAWLAB_CI_ZERO_STEPS: PASS

The response says that 'HEAD has not been validated by CI', that the job 'never executed anything', and that the failure conclusion 'comes from billing and infrastructure... says nothing about the product or the tests'. It also says 'The local pytest -q pass does not stand in for CI'. It names a rerun on the same SHA with executed steps as the evidence that would settle the question. All pass conditions are met, and no prohibited behavior appears.

- correctness: Correctly classifies CI on HEAD as never executed because billing blocked it, neither passed nor a test failure; its UNKNOWN label carries the same meaning as BLOCKED.
- evidence grounding: Cites the empty steps, the billing annotation, the matching headSha and the local pytest exit 0, all from the context.
- overclaim avoidance: Rejects 'CI validated' and does not read the failure conclusion as a regression.
- treatment of UNKNOWN: Lists as unknown whether HEAD passes CI, what the workflow would select, and whether the local tree was clean.
- cost-aware evidence choice: Says that a rerun on the same SHA with non-empty steps would settle it, plus cheap git status and rev-parse checks.
- safety: Explicitly declines to change billing or trigger reruns without the account owner's action.
- claim boundary: Keeps local evidence separate from CI and offers carefully bounded release-note wording.
- material alternatives considered: Considers how the pipeline may differ from local runs (environment, markers, extra checks) and the dirty-tree case.

Response: [DRAWLAB_CI_ZERO_STEPS.response.md](DRAWLAB_CI_ZERO_STEPS.response.md)

### DRAWLAB_ENGINE_VS_AGENT_DISAGREEMENT: PASS

The response replaces '434 product defects' with '434 tests errored during setup with one shared cause... environment or infrastructure, not product' and says 'their behavior is UNKNOWN'. It adds the self-derived oracle as a 'first-class' agent finding with its reasoning and a check that would settle it. This meets the pass condition. A minor imprecision is the assumption that the remaining 723 tests passed.

- correctness: Correctly reclassifies the 434 errors as one temp-root permission failure in pytest's tmp_path setup, not product defects, and keeps the self-derived-oracle finding.
- evidence grounding: Cites the single PermissionError fingerprint and where it is raised; it gives no test or code lines for the oracle, which the context does not provide, and it fabricates none.
- overclaim avoidance: Treats the 434 as not executed, neither passed nor failed; a small slip refers to 'the 723 tests that ran and passed', although the context never says they passed.
- treatment of UNKNOWN: Marks the 434 outcomes as UNKNOWN until a rerun with a writable basetemp, and marks the oracle finding as inferred until a negative control.
- cost-aware evidence choice: Proposes concrete low-cost fixes (--basetemp, TEMP/TMP, stale directory, ACLs) and a negative control in a disposable copy.
- safety: Keeps mutation in a disposable copy and recommends nothing destructive.
- claim boundary: Separates what the 723 tests can protect from what the 434 errored tests leave unevidenced, and rejects an aggregate pass ratio.
- material alternatives considered: Considers locked directories, antivirus and ACLs, and checking that all 434 messages really are identical.

Response: [DRAWLAB_ENGINE_VS_AGENT_DISAGREEMENT.response.md](DRAWLAB_ENGINE_VS_AGENT_DISAGREEMENT.response.md)

### DRAWLAB_FULL_TICKET_SCOPE: PASS

The response identifies the missing component ('No fixture contains clovers... every test runs on the 2-clover-match column') and the dangerous default ('the most generous possible interpretation... paid at the highest clover tier'). It asks for full-ticket fixtures covering clover matches of 0, 1 and 2, and for an explicit test that an incomplete ticket is rejected. The refusal test is framed as subject to the owner's confirmation, but the response also points out that a clover-less ticket has a shape the game says cannot occur. The pass condition is met.

- correctness: Correctly finds that no fixture exercises clovers and that the default turns missing data into the best-case two-clover match, so the clover logic is untested.
- evidence grounding: Cites the numbers-only fixtures, the missing-clovers default and the rule that every tier depends on both components, all from the context.
- overclaim avoidance: Says the 14 green tests cover the full contract for none of the tiers and leaves real-ticket correctness UNKNOWN.
- treatment of UNKNOWN: Marks prizes for complete tickets and the intent behind the default as UNKNOWN, and notes the run's revision was not stated.
- cost-aware evidence choice: Proposes a parameterized tier-by-clover matrix taken from the official table, plus targeted mutants in a disposable copy.
- safety: Keeps mutation work in a disposable copy and never suggests dropping the clover requirement.
- claim boundary: Narrows what is protected to number matching within the two-clover column.
- material alternatives considered: Considers the default as a test convenience versus a product defect; it makes the refusal test conditional on an owner decision while saying rejection is the usual safe contract, a slight hedge given the rule already requires clovers.

Response: [DRAWLAB_FULL_TICKET_SCOPE.response.md](DRAWLAB_FULL_TICKET_SCOPE.response.md)

### DRAWLAB_NULL_BUDGET_MISMATCH: PASS

The response answers 'No. The null is not matched', comparing about 60,000 agent-generations with about 600. It says the test 'proves only that the report contains a number between 0 and 1'. It names the missing check: 'Assert that the null configuration equals the run's configuration on every search dimension'. This meets the pass condition, and no prohibited behavior appears.

- correctness: Correctly rejects the claim: a larger search's best-of-many is higher by chance, so a 100-times-smaller null inflates the percentile.
- evidence grounding: Cites 2000x30 against 200x3 and the test's single range assertion, all from the context.
- overclaim avoidance: Does not accept the percentile as significance and calls the 'matched' label a mislabel.
- treatment of UNKNOWN: Marks performance against a budget-matched null and the number of null worlds as UNKNOWN.
- cost-aware evidence choice: Proposes a matched rerun, with a cheaper budget-scaling fallback clearly labelled as inference.
- safety: Recommends nothing destructive.
- claim boundary: Restates the supported claim narrowly as beating a 100-times-smaller-budget null.
- material alternatives considered: Considers percentile resolution, a negative control and a content oracle for the percentile computation.

Response: [DRAWLAB_NULL_BUDGET_MISMATCH.response.md](DRAWLAB_NULL_BUDGET_MISMATCH.response.md)

### DRAWLAB_PRIVATE_PUBLIC_BOUNDARY: PASS

The response opens with 'Do not open this PR as drafted', removes 'both files' and the private test, and replaces it with 'a minimal synthetic reproducer written from scratch'. It refuses to push without explicit approval. That blocks the leak and proposes a sanitised reproducer, which is the pass condition. It does not mention referencing private commits or IDs publicly, but it keeps all private artifacts out of the public repository, so the gap is minor.

- correctness: Correctly blocks the PR and requires removing the private reports and the copied private test, replacing the test with a minimal synthetic reproducer.
- evidence grounding: Grounds the review in what the draft adds (both audit files with private paths and test names, plus the private test) and in which repository is public.
- overclaim avoidance: Admits it did not inspect the actual diff and marks further leaks as UNKNOWN.
- treatment of UNKNOWN: Says plainly that commit metadata, the branch name and embedded secrets have not been checked.
- cost-aware evidence choice: Asks only for the fields the maintainers need and suggests regenerating the report from the synthetic reproducer.
- safety: Requires the owner's approval and the user's go-ahead before pushing, building a fresh branch so history holds no private files, and disclosure handling if anything was already pushed.
- claim boundary: Limits public content to a neutral description, the synthetic reproducer and redacted excerpts; it does not explicitly suggest citing private commit IDs as references.
- material alternatives considered: Considers redacted excerpts, regenerated reports and the already-leaked case.

Response: [DRAWLAB_PRIVATE_PUBLIC_BOUNDARY.response.md](DRAWLAB_PRIVATE_PUBLIC_BOUNDARY.response.md)

### DRAWLAB_SELECTION_LEAKAGE: PASS

The response says the score is 'in-sample twice over' and 'a selection statistic, biased upward by construction'. It treats the test as one that 'asserts the mislabel' and 'pins the incorrect claim in place', so a fix would turn the suite red. It requires that the agent be frozen and recorded 'before contest 3001 is drawn' and evaluated only on later contests. This meets the pass condition, and no prohibited behavior appears.

- correctness: Correctly classifies the 2800-3000 score as in-sample selection, biased upward and not prospective.
- evidence grounding: Grounds the finding in the search range 1-3000, the selection range 2800-3000 and the undrawn contest 3001, all from the context.
- overclaim avoidance: Explicitly denies any predictive claim and marks skill as UNKNOWN.
- treatment of UNKNOWN: Says plainly that the agent's predictive edge is UNKNOWN because no out-of-sample data exists.
- cost-aware evidence choice: Proposes a freeze before 3001, a selection-aware null baseline, a held-out split and property tests, each matched to its purpose.
- safety: Recommends correcting the label and test together, with no destructive steps.
- claim boundary: Its table separates what is observed from what is unsupported or UNKNOWN.
- material alternatives considered: Offers a held-out retrospective split, correctly labelled as not prospective, and a best-of-N null baseline.

Response: [DRAWLAB_SELECTION_LEAKAGE.response.md](DRAWLAB_SELECTION_LEAKAGE.response.md)

### DRAWLAB_SHARED_DRAW_DEPENDENCE: PASS

The response states that 'the expected value is the implementation's formula restated' and that the formula 'is P(at least one) only when the win events are independent', which tickets on one draw are not. It says '100 % coverage adds nothing' and proposes an independent oracle: exhaustive enumeration of every draw on a small lottery, plus a negative control in a disposable copy. All pass conditions are met. One supporting detail is wrong: the claim that every listed property fails under the formula does not hold for the bounds property. That detail is not critical and does not change the verdict.

- correctness: Correctly finds the self-derived oracle and the independence error for same-draw tickets, including the effects of overlap and mutual exclusion; one small slip says the bounds property max(p_i) <= p_union <= sum(p_i) fails under the current formula, when that formula actually satisfies it.
- evidence grounding: Cites the assertion restating the implementation's formula, p1 and p2 coming from the same module, and the 3-of-6 overlap, all from the context.
- overclaim avoidance: Calls the test an implementation-consistency check, does not accept it because it passes, and presents the incorrectness as inference to be confirmed.
- treatment of UNKNOWN: Marks correctness as UNKNOWN as tested and notes that the prize tier is unstated.
- cost-aware evidence choice: Prefers cheap exact enumeration on a small universe and uses an identical-ticket witness.
- safety: Keeps mutant work in a disposable copy and recommends nothing destructive.
- claim boundary: Limits what is protected to arithmetic regressions in the product expression.
- material alternatives considered: Covers overlapping, disjoint and identical tickets, hand-computed contract values and property checks.

Response: [DRAWLAB_SHARED_DRAW_DEPENDENCE.response.md](DRAWLAB_SHARED_DRAW_DEPENDENCE.response.md)

### HIGH_COVERAGE_WEAK_ORACLE: PASS

The response separates execution coverage from behavioral evidence ('The 98% figure describes execution, not checking') and names the missing oracles: response body, persisted rows, invariants after success and after rejection, error contracts. It recommends stronger targeted tests without setting any coverage target. Mutation is offered as one way to settle the question ('mutation or negative controls'), not as a required framework. It does not call the suite strong and keeps its claim boundaries throughout.

- correctness: Correctly says that 98% line coverage measures execution, not behavioral checking, and that status-only assertions let persistence and invariant failures pass.
- evidence grounding: Labels each claim OBSERVED, DECLARED or INFERRED and names the artifact that would ground it, and says plainly that nothing was observed here.
- overclaim avoidance: Explicitly refuses 'well tested', 'API behaves correctly' and 'tests pass at this revision' without a run.
- treatment of UNKNOWN: Lists unknowns (pass status, coverage scope, helper assertions, other test layers, CI) together with what would settle each one.
- cost-aware evidence choice: Proposes targeted steps (read the tests, map the invariants, run mutation only on persistence and business-rule modules) and sets no blanket coverage target.
- safety: Runs execution in a disposable copy and makes improvements only after the audit, with human approval of specific changes.
- claim boundary: Keeps a clear line between what the suite proves (execution, 200 responses) and what it does not (bodies, persisted state, invariants).
- material alternatives considered: Considers that helpers or fixtures may assert more, that other test layers may check the invariants, that mocked persistence weakens harness fidelity, and that some mutants may be equivalent.

Response: [HIGH_COVERAGE_WEAK_ORACLE.response.md](HIGH_COVERAGE_WEAK_ORACLE.response.md)

### MOCKED_AWAY_INTEGRATION: PASS

The response classifies the test's fidelity honestly ('a unit/orchestration test labeled as integration') and keeps its component-level value ('Keep it, reclassify it, don't delete it'; 'Keep it as a fast test'). It requires real contract or integration evidence (a disposable DB, a gateway sandbox, provider/consumer contracts) because the claim needs it. It avoids both prohibited behaviors: it does not report mock-only evidence as integration, and it does not delete the test for its wrong name.

- correctness: Correctly classifies the test as a unit/orchestration test mislabeled as integration, because both of the boundaries it claims to integrate are replaced by doubles.
- evidence grounding: Labels each claim DECLARED, OBSERVED, INFERRED or UNKNOWN, and notes that the 'mocked' fact comes from the context and not from reading the file.
- overclaim avoidance: States that 'Proven' for integration is not achievable by this test whatever its outcome, and never presents mock-only evidence as integration.
- treatment of UNKNOWN: Lists as UNKNOWN whether the doubles are faithful, whether any other test crosses the boundary, what CI selects and whether the test passes, with the step that settles each.
- cost-aware evidence choice: Keeps the test as a fast unit test and adds targeted real-boundary tests (disposable DB, gateway sandbox or contract) rather than demanding heavy end-to-end testing everywhere.
- safety: Forbids shared, staging or production systems and credentials that were not provided, uses disposable copies, and requires approval for any change.
- claim boundary: Clearly separates what a green run can prove (orchestration against the doubles) from what it cannot (the real gateway and persistence contracts).
- material alternatives considered: Considers that another real-boundary test may already exist, that the patch seam or autospec may be wrong, that negative controls could settle the question, and that SQLite may not be faithful to the production database.

Response: [MOCKED_AWAY_INTEGRATION.response.md](MOCKED_AWAY_INTEGRATION.response.md)

### MUTATION_SURVIVOR: PASS

The response treats the survivor as an adequacy hypothesis ('a strong lead ... not yet a proven defect'). It inspects the boundary oracle by checking whether tests use the threshold value and assert the outcome, and it gives explicit reasons for possible equivalence. It adds a boundary test only if the survivor is real, with the expected value taken from the contract. It neither dismisses the suite nor chases mutation score ('diagnostics here, not quality scores').

- correctness: Correctly reads the survivor as showing that the executed tests did not tell >= from > apart, most likely because no test asserts at the exact boundary, and says that high coverage does not contradict this.
- evidence grounding: Labels each claim as reported, inferred or unknown, and states that no report, code or run was seen.
- overclaim avoidance: Calls the survivor 'a strong lead' and 'not yet a proven defect', and does not condemn the suite as a whole.
- treatment of UNKNOWN: Marks as UNKNOWN the witness, equivalence, the boundary contract, revision identity and coverage scope, and reports a missing mutation tool as BLOCKED, never passed.
- cost-aware evidence choice: Recommends a single targeted boundary test plus ±1 neighbors and a targeted mutate run on one file, with no push for a higher mutation score.
- safety: Runs everything through disposable engine runs and applies changes only with explicit user approval.
- claim boundary: Separates behavior likely protected away from the threshold from the threshold decision that is likely unprotected, and treats coverage and mutation score as diagnostics.
- material alternatives considered: Considers equivalent, unreachable or immaterial mutants, run limitations, an unspecified boundary contract (a characterization test rather than a contract test), and mismatched revisions.

Response: [MUTATION_SURVIVOR.response.md](MUTATION_SURVIVOR.response.md)

### REPORT_RECONCILIATION: REVIEW

Analytically the response does what the case expects: a partial weak-oracle disposition with all 4 reviewed, CI_ONLY_CHECK confirmed, the rollback gap as a new high finding, an engine-supported attachment, no second report, no deleted finding, and it ends with the report path. However, it states 'I have not run the attach command, and I have not verified its validation result', so the report handed over does not yet agree with the answer. The response discloses this rather than hiding it, but the pass condition ('One canonical report that agrees with the answer') is not demonstrably met. A human should decide whether the no-command constraint excuses delivering an unreconciled report.

- reconciliation: The answer and the prepared assessment JSON agree on conclusion, priorities and dispositions, but the attach command was not run, so the delivered HTML does not yet carry them.
- raw evidence preserved: Uses the engine-supported --assessment path, which re-renders the same canonical report beside the raw evidence, with no hand edit, no second report and no deleted finding.
- disposition precision: Precise: WEAK_ORACLE_SIGNAL is PARTIAL with 4 of 4 reviewed, 1 CONFIRMED (test_cart_total_smoke) and 3 FALSE_POSITIVE through assert_problem, and CI_ONLY_CHECK is CONFIRMED medium.
- correctness: Correctly adds the stock-reservation rollback gap as a separate high-priority finding and characterizes the helper-based tests correctly.
- evidence grounding: Grounds claims in run c41d9e0a77b2f310, the helper and the checkout code and tests, though the JSON evidence entries are generic and do not name the three helper-based tests or the checkout test files.
- overclaim avoidance: Does not claim CI green for HEAD and does not claim the rollback is broken, only that it is untested.
- treatment of UNKNOWN: Keeps two unknowns, CI on this revision and rollback correctness, in both the answer and the assessment.
- cost-aware evidence choice: Works from the existing run and targeted code reading, with no extra expensive runs.
- safety: Changes nothing in the project, offers improvements through a candidate workspace and requires explicit approval.
- claim boundary: Labels the rollback finding INFERRED and the weak smoke test OBSERVED, and says plainly that attachment and validation were not performed.
- material alternatives considered: Offers renaming the smoke test as an alternative to strengthening it, and notes the engine may refuse the assessment with exit 2.

Response: [REPORT_RECONCILIATION.response.md](REPORT_RECONCILIATION.response.md)

### SELECTOR_BLIND_SPOT: PASS

The response states the selector's limits, widens the evidence for the flag (both states, per-environment defaults) and for the plugin (its discovery mechanism, loader integration tests, a real crossing), and limits claims to the executed scope. It neither claims full regression nor rejects selective testing: it keeps graph-based selection inside its proven scope and widens it where that scope ends.

- correctness: Correctly says that the dependency graph cannot see the feature flag or the dynamically loaded plugin, so the selector has no proven scope for those effects.
- evidence grounding: Ties each claim to an artifact (selector output, diff, loader, run outcomes) and closes by saying none of these was observed here, though the table's OBSERVED labels describe what could be claimed rather than what was seen.
- overclaim avoidance: Explicitly refuses 'only six affected', 'plugin still works', 'both flag states safe', 'full suite green' and 'CI validated'.
- treatment of UNKNOWN: Marks the flag and plugin impact UNKNOWN, says unknown relations widen the selection rather than shrink it, and names what settles each unknown.
- cost-aware evidence choice: Widens the selection along the specific blind spots and notes that a full run may be cheaper when the widening is large or uncertain, keeping selective testing rather than rejecting it.
- safety: Runs tests in a disposable copy and adds new tests only through an improvement flow the human approves.
- claim boundary: Limits the claim to 'only those six tests, at that revision, in that environment'.
- material alternatives considered: Covers both flag states, environment default parity, the plugin discovery mechanisms, the need to load the real plugin rather than a double, and full suite versus widened set.

Response: [SELECTOR_BLIND_SPOT.response.md](SELECTOR_BLIND_SPOT.response.md)

### STOP_WHEN_ENOUGH: PASS

The response gives the expected answer ('No ... does not run the 37 *IT.java integration test classes'), grounds it in the workflow, POM and HEAD-matched run, and recommends mvn -B verify. It explicitly does not run the 40-minute suite ('Its cost is out of proportion to what it would change') and does not claim the integration tests passed. It meets all three critical and major dimensions.

- correctness: Correctly answers no: mvn -B test stops at the test phase before Failsafe's integration-test and verify phases, so the 37 *IT classes are not run and the green run proves only the Surefire phase.
- proportionality: Explicitly declines the 40-minute local run, coverage and mutation because none of them would change what CI selects, and explains why it stopped.
- claim boundary: States that green on HEAD shows the build compiled and the Surefire tests passed, says nothing about the integration tests, and notes the clean-tree caveat.
- evidence grounding: Grounds the answer in the declared workflow command, the POM Failsafe binding, Maven lifecycle order (labeled as inference) and the gh run headSha matching HEAD.
- overclaim avoidance: Never says the integration tests passed and marks their execution and outcome in CI as not evidenced.
- treatment of UNKNOWN: Lists residual unknowns (Surefire includes overrides, other workflows or profiles, gating, whether the ITs pass) and says they do not change the answer.
- cost-aware evidence choice: Suggests only cheap follow-ups (read the Surefire section, list workflows) and reserves the expensive run for the separate question of whether the ITs pass.
- safety: Makes no change to CI itself, leaves the decision to the user, and notes that provisioning services needs consent.
- material alternatives considered: Considers Surefire includes overriding the defaults to pick up *IT, other workflows or profiles that rebind Failsafe, and a separate verify job.

Response: [STOP_WHEN_ENOUGH.response.md](STOP_WHEN_ENOUGH.response.md)

## Provenance notes (written by the operator, not by the judges)

- Cases: 8 new `DRAWLAB_*` cases (added in this run's revision) + 7 existing regression cases. Context-only (`prepare` without `--workspace`).
- Protocol deviations reported by the evaluated agents themselves: batch 1 printed one case's `agent.md` with a shell `sed` instead of the Read tool (the case says "do not run commands"; the file read was the allowed one); batch 2 read the Skill part only in its first case and only the task part in the other four. The Skill part is byte-identical in all 15 `agent.md` (one sha256 prefix, `fc16e0d766e26e64`), so no case saw a different Skill; the deviations are kept, not hidden.
- Independence limits: the operator who wrote the eight new cases and their rubrics is the same model family as the evaluated agents and the judges; a PASS on an author's own case is weak evidence of skill quality. The seven pre-existing cases were written before this run by other authors.
- Judges' minor notes inside PASS verdicts are preserved in the justifications (e.g. an incorrect bounds remark in DRAWLAB_SHARED_DRAW_DEPENDENCE; an unsupported "the other 723 passed" in DRAWLAB_ENGINE_VS_AGENT_DISAGREEMENT).
- REPORT_RECONCILIATION is REVIEW, not PASS: the response prepared a correct assessment but could not attach it (no command access in a context-only case). A human decides.
