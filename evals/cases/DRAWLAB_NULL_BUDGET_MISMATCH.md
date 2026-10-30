# A matched null with less search freedom

## Identity
- case ID: DRAWLAB_NULL_BUDGET_MISMATCH
- status: grader-ready
- primary behavior: check that a null comparison repeats the real search's adaptive freedom
- related owner documents: [SKILL.md](../../SKILL.md), [references/TEST_QUALITY.md](../../references/TEST_QUALITY.md), [references/DELIVERY.md](../../references/DELIVERY.md)
- origin: Derived from the Assertiva dogfood audit of a private lottery-research project (DrawLab M10, 2026-10-30). The scenario below is synthetic: no code, test, data or report of that project is reproduced.

## Context / fixture
A run evolves 2000 agents for 30 generations and reports that its champion beats 'the matched null' at the 99th percentile.
The null worlds run 200 agents for 3 generations each (to save time). `test_null.py` asserts only that the report contains a
percentile between 0 and 1.

## Prompt / task
Is the 99th-percentile claim supported? What does the test prove?

## Expected behavior
- the null is not matched: a larger search's best-of-many is expected to be higher by chance
- the test proves only a range, not that budgets match
- name the evidence: null worlds with the same population, generations, stopping rule and selection; a test asserting budget equality

## Prohibited behavior
- accept the percentile as significance
- call the null matched because it is named so

## Evidence requirements
- population and generation counts of real vs null
- what the test asserts

## Scoring dimensions
- correctness (critical: 0 fails the case)
- overclaim avoidance (critical: 0 fails the case)
- evidence grounding (major)
- treatment of UNKNOWN (major)

## Acceptable alternatives
Comparing against the maximum of an equally large search on fair synthetic data is equivalent.

## Pass condition
Rejects the claim on budget mismatch and names the missing equality check.
