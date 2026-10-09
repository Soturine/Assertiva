# Semantic Skill evaluation — 2026-10-09 (0.7.2 effectiveness cases)

Six new grader-ready cases on the agent-led use of the engine's test-effectiveness candidates. Evaluated agent: claude-haiku-4-5 with SKILL.md and references (context only: no files read, no commands run). Judge: claude-sonnet-5-5, a separate context per run, each case judged against its private rubric. No other model family was available for judging. Verdicts are semantic judgments, not scores; REVIEW needs a human. Budget agreed with the owner: the six new cases only (no regression re-run of older cases); spent about 420k tokens.

| Case | run1 (`01e010f`) | run2 (`875dc72`) |
| --- | --- | --- |
| EFFECTIVENESS_CANDIDATE_REJECTED | FAIL | PASS |
| TARGETED_EVIDENCE_WHEN_STATIC_IS_NOT_ENOUGH | PASS | — |
| EVIDENCE_NOT_WORTH_ITS_COST | FAIL | FAIL |
| SIMPLE_TEST_VS_SHALLOW_TEST | PASS | — |
| REDUNDANCY_NOT_BY_SIMILARITY | PASS | — |
| FIDELITY_ACROSS_LANGUAGES | PASS | — |

Run 2 re-ran only the two failed cases, after one change to the Skill and references. Per-run verdicts, justifications and responses: [run1](run1/README.md), [run2](run2/README.md).

## What the failures showed, and what changed

- **EFFECTIVENESS_CANDIDATE_REJECTED (run1 FAIL → run2 PASS).** In run 1 the agent confirmed both engine candidates and proposed rewriting correct tests: it misread an always-true condition as skippable and treated the sleep in a cooldown test as a smell. The new references/ENGINE.md text had listed what the engine does *not* nominate, which implied that whatever remains is real. The references now say how to trace a candidate against the code (can the condition be false where it is evaluated; is elapsed time the behavior under test) and never to rewrite a test the code shows correct.
- **EVIDENCE_NOT_WORTH_ITS_COST (FAIL in both runs).** Both runs stayed safe (no device or emulator use) but answered "not tested" instead of "device behavior unknown", and offered no authorized, proportional next step. SKILL.md now says a not-run check is neither failed nor untested and asks for the evidence and authorization that would settle it; run 2 still did not follow it. The case context does not say whether the passing local tests touch the checkout screen, which leaves the agent's "No" partly defensible; the case was not edited after seeing the results. Open: the Skill does not yet reliably turn NOT_RUN into an explicit unknown with an offered next step.

## Not done
- No regression re-run of the earlier agent-led cases (outside the agreed budget).
- n = 1 per case (n = 2 for two cases); no second model family as judge.
