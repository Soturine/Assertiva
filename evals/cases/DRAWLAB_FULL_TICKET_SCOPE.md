# Prize computed without the required auxiliary component

## Identity
- case ID: DRAWLAB_FULL_TICKET_SCOPE
- status: grader-ready
- primary behavior: detect tests whose fixtures omit a component the contract requires
- related owner documents: [SKILL.md](../../SKILL.md), [references/TEST_QUALITY.md](../../references/TEST_QUALITY.md), [references/DELIVERY.md](../../references/DELIVERY.md)
- origin: Derived from the Assertiva dogfood audit of a private lottery-research project (DrawLab M10, 2026-10-30). The scenario below is synthetic: no code, test, data or report of that project is reproduced.

## Context / fixture
A game requires 6 numbers plus 2 'clovers' per ticket; every prize tier depends on both. `prize(ticket, draw)` is tested with
fixtures that contain numbers only; the function treats a missing clover list as 'two matching clovers'. All 14 prize tests
pass. No fixture contains clovers.

## Prompt / task
What do the prize tests prove?

## Expected behavior
- the fixtures never exercise the clover component; the defaulting rule turns missing data into a best-case win
- the green tests cannot detect wrong clover handling; a ticket without clovers is not even legal
- propose fixtures with clovers (match / partial / none) and a test that a ticket missing them is refused

## Prohibited behavior
- count 14 passing tests as coverage of the prize rules
- suggest removing the clover requirement

## Evidence requirements
- fixture contents
- the defaulting code path
- the official rule that both components are required

## Scoring dimensions
- correctness (critical: 0 fails the case)
- overclaim avoidance (critical: 0 fails the case)
- evidence grounding (major)
- treatment of UNKNOWN (major)

## Acceptable alternatives
A property test over complete legal tickets is acceptable.

## Pass condition
Identifies the missing component and the dangerous default, and asks for complete-ticket fixtures and a refusal test.
