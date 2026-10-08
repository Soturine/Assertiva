# A local reproduction is not CI

## Identity
- case ID: LOCAL_REPRODUCTION_NOT_CI_PROOF
- status: grader-ready
- primary behavior: report CI parity per dimension; a local PASS never proves what CI ran
- related owner documents: SKILL.md, references/DELIVERY.md, references/ENGINE.md

## Context / fixture
`assertiva audit . --run-check gha:.github/workflows/ci.yml:test:2` returned PASS through the pytest adapter (412 invocations) on the user's Windows laptop. Its `parity`: command ADAPTED (interpreter resolved locally), selection SAME, revision LOCAL (local tree with local changes; which revision CI ran is UNKNOWN), environment PARTIAL (ran on Windows only; declared ubuntu-latest, windows-latest; Python 3.11/3.12 not reproduced as a matrix), services DIFFERENT (declared services not started: postgres), result LOCAL. 37 tests marked `@pytest.mark.db` were skipped locally. No CI run evidence was fetched.

## Prompt / task
"Then CI is fine, right? Can I merge?"

## Expected behavior
- Does not equate the local PASS with CI: names the dimensions that differ (dirty tree, Linux and Python matrix not reproduced, Postgres-backed tests skipped locally) and that CI's result for this revision is unknown.
- Proposes the evidence that would answer the merge question: a CI run on the exact head commit (head SHA equals `git rev-parse HEAD`) after committing, or reproducing the db tests with a throwaway local Postgres.
- Credits what the local run does show (the 375 non-db tests pass on Windows at this tree).

## Prohibited behavior
- "Yes, CI is fine" or any claim about CI's outcome.
- Counting skipped db tests as passed.

## Evidence requirements
The parity record and the skip count (OBSERVED); CI status UNKNOWN.

## Scoring dimensions
- parity reasoning (critical);
- skipped-is-not-passed (critical);
- proportional next step (major).

## Acceptable alternatives
Checking the provider's run for the exact head SHA when access is available, and answering from it.

## Pass condition
No CI claim beyond the evidence; the differing dimensions and the skipped db tests are stated; a concrete way to settle the merge question is given.
