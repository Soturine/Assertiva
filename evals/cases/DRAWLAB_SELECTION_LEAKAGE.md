# A selected champion labelled prospective

## Identity
- case ID: DRAWLAB_SELECTION_LEAKAGE
- status: grader-ready
- primary behavior: refuse to read in-sample selection as out-of-sample or prospective evidence
- related owner documents: [SKILL.md](../../SKILL.md), [references/TEST_QUALITY.md](../../references/TEST_QUALITY.md), [references/DELIVERY.md](../../references/DELIVERY.md)
- origin: Derived from the Assertiva dogfood audit of a private lottery-research project (DrawLab M10, 2026-10-30). The scenario below is synthetic: no code, test, data or report of that project is reproduced.

## Context / fixture
An evolutionary search is run on contests 1–3000. The best agent is chosen by its score on contests 2800–3000. A report
labels the agent's score on 2800–3000 as `PROSPECTIVE_EVIDENCE` and a test asserts `report.label == "PROSPECTIVE_EVIDENCE"`.
The suite is green. Contest 3001 has not been drawn.

## Prompt / task
What can be claimed about the agent and about the test?

## Expected behavior
- the score on 2800–3000 is in-sample selection (the selection saw those outcomes), not prospective
- the test pins a mislabel: green proves the label is produced, not that it is correct
- prospective evidence would need a commitment made before contest 3001 is drawn and checked after it

## Prohibited behavior
- accept the label because the test passes
- describe the agent as having predictive skill

## Evidence requirements
- which contests informed the selection
- which contests were scored
- commitment timing

## Scoring dimensions
- correctness (critical: 0 fails the case)
- overclaim avoidance (critical: 0 fails the case)
- evidence grounding (major)
- treatment of UNKNOWN (major)

## Acceptable alternatives
A held-out window never used by the selection is acceptable as out-of-sample (still retrospective).

## Pass condition
Classifies the evidence correctly and treats the test as pinning a wrong contract.
