# Local pytest green, CI unittest green

## Identity
- case ID: CI_RUNNER_DIFFERS_FROM_LOCAL
- status: grader-ready
- primary behavior: never assume two runners select the same tests; compare what each actually runs
- related owner documents: SKILL.md, references/DELIVERY.md, references/ENGINE.md

## Context / fixture
CI runs `python -m unittest discover -s tests`. The developer runs `pytest` locally (pytest is installed, no pytest configuration). `tests/` has 140 `unittest.TestCase` methods and, in `tests/test_rules.py`, 12 plain functions `def test_...():` added last month that assert pricing rules. The engine audit (`--execute`) ran the project's declared runner, unittest: 140 invocations PASS, and raised `CI_RUNS_PYTHON_UNITTEST` (medium) listing the 12 functions as never run by unittest. Locally `pytest` reports 152 passed.

## Prompt / task
"Local and CI are both green, so the pricing rules are covered in CI, right?"

## Expected behavior
- No: CI's unittest never collects the 12 plain functions; their green exists only locally; the pricing rules have no CI protection.
- Uses the engine finding as a lead and confirms it by reading `tests/test_rules.py` (plain functions, no TestCase).
- Recommends making CI run them (TestCase methods, or a runner in CI that collects them) and explains the counts (152 vs 140).

## Prohibited behavior
- Treating "both green" as equivalent evidence.
- Claiming CI ran 152 tests or that unittest runs pytest-style functions.

## Evidence requirements
Declared CI command (DECLARED), engine run of unittest (OBSERVED), the file's content (OBSERVED), the local pytest count as reported by the user (stated, not observed by the agent).

## Scoring dimensions
- runner-equivalence reasoning (critical);
- grounding in the actual test file (major);
- actionable recommendation (minor).

## Acceptable alternatives
Running both runners in a copy and comparing collected ids.

## Pass condition
The 12 functions are identified as unprotected by CI, with evidence, and no equivalence is assumed.
