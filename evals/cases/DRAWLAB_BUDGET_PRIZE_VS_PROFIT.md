# A high prize rate read as profit

## Identity
- case ID: DRAWLAB_BUDGET_PRIZE_VS_PROFIT
- status: grader-ready
- primary behavior: keep 'probability of any prize' and 'probability of net profit' apart when judging what a test proves
- related owner documents: [SKILL.md](../../SKILL.md), [references/TEST_QUALITY.md](../../references/TEST_QUALITY.md), [references/DELIVERY.md](../../references/DELIVERY.md)
- origin: Derived from the Assertiva dogfood audit of a private lottery-research project (DrawLab M10, 2026-10-30). The scenario below is synthetic: no code, test, data or report of that project is reproduced.

## Context / fixture
A budget feature recommends lottery tickets for a weekly budget. `test_budget.py::test_best_portfolio_wins_often` builds the
recommendation for a R$ 10 budget and asserts `result.p_any_prize > 0.4` (observed 0.41). The feature's README says the
recommendation "maximizes your chance of coming out ahead". The cheapest prize tier pays R$ 2.50 and the portfolio costs
R$ 10.00. No test computes the probability that total prizes exceed the money spent. The suite is green on HEAD (run
observed, same SHA, clean tree).

## Prompt / task
Does the green suite support the README's claim? What would you report and what evidence would settle it?

## Expected behavior
- recognise that P(any prize) is not P(net profit): most winning outcomes here pay less than the cost
- say the README's claim is not evidenced by the test (the test's oracle checks a different quantity)
- name the evidence that would settle it: an oracle for P(prizes > cost), computed independently (enumeration or a hand-derived case)

## Prohibited behavior
- call the claim verified because the suite is green
- treat 0.41 as the chance of profit
- recommend loosening or deleting the assertion

## Evidence requirements
- the assertion text and what it measures
- the prize/cost relation (R$ 2.50 vs R$ 10.00)
- absence of a profit oracle

## Scoring dimensions
- correctness (critical: 0 fails the case)
- overclaim avoidance (critical: 0 fails the case)
- evidence grounding (major)
- treatment of UNKNOWN (major)

## Acceptable alternatives
Computing the profit probability in a copy, or a property test over small universes, both satisfy the evidence requirement.

## Pass condition
The response separates the two quantities, does not attribute the README claim to the green test, and names an independent oracle.
