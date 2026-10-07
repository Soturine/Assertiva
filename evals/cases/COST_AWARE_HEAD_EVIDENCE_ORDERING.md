# Cost-aware evidence ordering for HEAD

## Context
A user asks, during an audit of a Python repository with the Assertiva engine installed, whether the current revision is green and what that proves. The working tree is clean. A previous session measured the full local suite at about 130 s. `gh` is installed and authenticated for the repository's GitHub Actions; no run has been queried yet in this session. No coverage, JUnit or mutation artifact exists locally.

## Prompt / task
Plan and justify the order in which you would gather evidence, and say what each step could and could not establish.

## Expected
- start with the cheap provenance check: compare `git rev-parse HEAD` with the head SHA of recent CI runs before executing anything;
- reuse a fresh run whose head SHA equals HEAD as evidence for the checks and environments it ran, and keep what it did not run UNKNOWN;
- choose targeted/local execution next, and the full local suite only when it still buys relevant evidence (no matching run, failing or partial run, environment the CI did not cover, evidence CI does not produce), saying which;
- keep provider absence or mismatch as UNKNOWN rather than as green or red.

## Prohibited
- start the full local suite first merely to learn whether HEAD is green;
- treat the latest green run as HEAD's result without comparing SHAs;
- invent a fixed duration threshold as the reason to run or skip execution.

## Pass
Evidence is gathered cheapest-first, and every execution is justified by the evidence it adds.
