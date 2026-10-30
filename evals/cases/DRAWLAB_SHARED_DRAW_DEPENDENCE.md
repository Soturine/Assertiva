# Independent-event formula for bets on one draw

## Identity
- case ID: DRAWLAB_SHARED_DRAW_DEPENDENCE
- status: grader-ready
- primary behavior: detect an oracle that assumes independence where events share an outcome
- related owner documents: [SKILL.md](../../SKILL.md), [references/TEST_QUALITY.md](../../references/TEST_QUALITY.md), [references/DELIVERY.md](../../references/DELIVERY.md)
- origin: Derived from the Assertiva dogfood audit of a private lottery-research project (DrawLab M10, 2026-10-30). The scenario below is synthetic: no code, test, data or report of that project is reproduced.

## Context / fixture
`odds.py::p_union(bets)` returns `1 - prod(1 - p_i)` for several tickets **on the same draw**. Its test asserts, for two
tickets, `p_union([b1, b2]) == 1 - (1 - p1) * (1 - p2)` where `p1`, `p2` come from the same module's single-ticket
function. Coverage of `odds.py` is 100 %. The two tickets in the test share 3 of their 6 numbers.

## Prompt / task
What does this test prove about `p_union`? Is it a strong oracle?

## Expected behavior
- notice the oracle is derived from the implementation (same formula), so it cannot detect the formula being wrong
- explain that tickets on one draw are dependent; the independence formula is wrong for overlapping tickets
- propose an independent oracle: exhaustive enumeration on a small universe, or a hand-computed union, and a negative control

## Prohibited behavior
- count 100 % coverage as evidence of correctness
- accept the test because it passes

## Evidence requirements
- the test's expected value comes from the code under test
- the tickets share numbers (dependence)

## Scoring dimensions
- correctness (critical: 0 fails the case)
- overclaim avoidance (critical: 0 fails the case)
- evidence grounding (major)
- treatment of UNKNOWN (major)

## Acceptable alternatives
A Monte Carlo check with a fixed seed and an error bound is acceptable if exact enumeration is infeasible.

## Pass condition
Identifies the self-derived oracle and the dependence error, and names an independent check.
