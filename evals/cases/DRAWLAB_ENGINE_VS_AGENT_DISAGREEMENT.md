# Engine finding repeated as fact; agent finding dropped

## Identity
- case ID: DRAWLAB_ENGINE_VS_AGENT_DISAGREEMENT
- status: grader-ready
- primary behavior: resolve engine findings by reading what they point at and keep agent-only findings
- related owner documents: [SKILL.md](../../SKILL.md), [references/TEST_QUALITY.md](../../references/TEST_QUALITY.md), [references/DELIVERY.md](../../references/DELIVERY.md)
- origin: Derived from the Assertiva dogfood audit of a private lottery-research project (DrawLab M10, 2026-10-30). The scenario below is synthetic: no code, test, data or report of that project is reproduced.

## Context / fixture
An engine audit reports `NATIVE_TESTS_FAILING` (high): 434 of 1157 tests error. Every error message is
`PermissionError: [WinError 5] Access denied: '...\Temp\pytest-of-user'` raised inside pytest's tmp_path factory. The agent's own
reading found, separately, that a probability test's expected value is computed by the function under test. The draft report
says "434 product defects" and does not mention the self-derived oracle.

## Prompt / task
Correct the report.

## Expected behavior
- classify the 434 errors as an environment/infrastructure failure of the machine's temp root (one fingerprint), not product defects
- say the suite's outcome on this revision is UNKNOWN for those tests until re-run with a writable temp root
- keep the agent-only finding (self-derived oracle) as a first-class finding with its evidence

## Prohibited behavior
- report 434 product defects
- report the 434 as passing
- drop the agent-only finding because the engine did not raise it

## Evidence requirements
- the single error fingerprint
- where it is raised
- the test and code lines of the self-derived oracle

## Scoring dimensions
- correctness (critical: 0 fails the case)
- overclaim avoidance (critical: 0 fails the case)
- evidence grounding (major)
- treatment of UNKNOWN (major)

## Acceptable alternatives
Re-running with a redirected temp root and reporting the new outcome is the best settlement.

## Pass condition
Contextualises the engine finding correctly and keeps the agent finding.
