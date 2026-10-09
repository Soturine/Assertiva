# Semantic Skill evaluation — 2026-10-09 (0.7.2 effectiveness cases)

Six new grader-ready cases on the agent-led use of the engine's test-effectiveness candidates. Evaluated agent: claude-haiku-4-5 with SKILL.md and references (context only: no files read, no commands run). Judge: claude-sonnet-5-5, a separate context per run, each case judged against its private rubric. No other model family was available for judging. Verdicts are semantic judgments, not scores; REVIEW needs a human. Budget agreed with the owner: the six new cases only (no regression re-run of older cases), about 420k tokens; then one targeted round of at most 80k tokens for the case still failing (run 3: 41,008 tokens for the evaluated agent, 38,281 for the judge).

| Case | run1 (`01e010f`) | run2 (`875dc72`) | run3 (`c3e2a0d`) |
| --- | --- | --- | --- |
| EFFECTIVENESS_CANDIDATE_REJECTED | FAIL | PASS | — |
| TARGETED_EVIDENCE_WHEN_STATIC_IS_NOT_ENOUGH | PASS | — | — |
| EVIDENCE_NOT_WORTH_ITS_COST | FAIL | FAIL | PASS |
| SIMPLE_TEST_VS_SHALLOW_TEST | PASS | — | — |
| REDUNDANCY_NOT_BY_SIMILARITY | PASS | — | — |
| FIDELITY_ACROSS_LANGUAGES | PASS | — | — |

Run 2 re-ran only the two failed cases, after one change to the Skill and references; run 3 re-ran only the case still failing, after a second change. Per-run verdicts, justifications and responses: [run1](run1/README.md), [run2](run2/README.md), [run3](run3/README.md).

## What the failures showed, and what changed

- **EFFECTIVENESS_CANDIDATE_REJECTED (run1 FAIL → run2 PASS).** In run 1 the agent confirmed both engine candidates and proposed rewriting correct tests: it misread an always-true condition as skippable and treated the sleep in a cooldown test as a smell. The new references/ENGINE.md text had listed what the engine does *not* nominate, which implied that whatever remains is real. The references now say how to trace a candidate against the code (can the condition be false where it is evaluated; is elapsed time the behavior under test) and never to rewrite a test the code shows correct.
- **EVIDENCE_NOT_WORTH_ITS_COST (FAIL in both runs).** Both runs stayed safe (no device or emulator use) but answered "not tested" instead of "device behavior unknown", and offered no authorized, proportional next step. SKILL.md now says a not-run check is neither failed nor untested and asks for the evidence and authorization that would settle it; run 2 still did not follow it. The case context does not say whether the passing local tests touch the checkout screen, which leaves the agent's "No" partly defensible; the case was not edited after seeing the results. Run 2's response showed the cause: the agent read "is it tested?" as "did a green run execute tests?", collapsed existence, execution and proof into one "No", declared the question settled, and so saw no reason to offer a next step; the one-line rule about not-run labels did not reach that reasoning. SKILL.md (`c3e2a0d`) replaced it with a general evidence ladder — exists, selected, executed, outcome, proven — where a missing step leaves the next ones unknown without making earlier ones false, a passing suite proves a behavior only through tests tied to it, and stopping early states the unknown and what would settle it, never resolves it. It names no ecosystem, device or case. Run 3 (rubric and case unchanged) PASSED: the response kept each step separate, left device behavior unknown, did not assume the simulated tests cover the screen, and offered a CI job or an authorized run; the judge noted it did not say what each option would prove.
- Caution on run 3: n = 1; the response follows the ladder's structure closely, so it shows the guidance is applied, not yet that the reasoning transfers. A transfer check in another ecosystem did not fit the 80k budget and was not run.

## Not done
- No regression re-run of the earlier agent-led cases (outside the agreed budget).
- n = 1 per case (n = 2 and 3 for the two re-run cases); no second model family as judge.
- No transfer check of the run-3 change in another ecosystem, and no re-run of the five other cases after it (the change touches SKILL.md, which they also load).
