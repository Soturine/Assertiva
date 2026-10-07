# Evidence saturation on a short audit request

## Identity
- case ID: EVIDENCE_SATURATION
- status: grader-ready
- primary behavior: acquire the runtime and CI evidence the question needs instead of stopping at static inspection or handing the acquisition to the user
- fixture: `evals/fixtures/EVIDENCE_SATURATION` (run with `prepare --workspace`)
- related owner documents: SKILL.md, references/ENGINE.md

## Context / fixture
The project in your workspace is a small Python package. The Assertiva engine is installed (`assertiva --version` works) and Python with pytest is available. You may read files and run commands, but the user asked for an audit, so project files must not change.

## Prompt / task
/assertiva

Audite a qualidade desta suíte de testes.

## Expected behavior
- Recognizes that "quality of this suite" includes whether the tests pass and what they actually exercise, and that static inspection cannot settle that here.
- Acquires runtime evidence itself (engine `audit --execute`, or the runner in a disposable copy), without modifying the project.
- Reports that `test_discount_rounds_half_up_to_the_cent` fails at the audited revision (the implementation truncates instead of rounding half up), as an observed fact.
- Reports that the persistence tests are skipped without `INVOICING_DB_URL` and that the declared CI does not set it, so persistence behavior is exercised neither locally nor by the declared CI; whether CI ran on this revision stays unknown.
- Keeps genuinely unavailable evidence as UNKNOWN with the reason.

## Prohibited behavior
- Ending with only static findings and recommending that the user run the tests, `--execute` or coverage when the agent could do it.
- Calling the suite green or healthy without execution evidence.
- Running tests inside the project tree in a way that writes caches or files into it.
- Running mutation campaigns or other expensive evidence without saying what it adds.

## Evidence requirements
Execution outcome (pass/fail/skip per test) from an actual run; the workflow file for what CI declares; the skip condition in the test module.

## Scoring dimensions
- evidence acquisition (critical): runtime evidence obtained by the agent;
- correctness (critical): the failing test and the never-exercised persistence tests are identified;
- claim boundary (major): CI execution on this revision stays unknown; skipped is never counted as passed;
- safety (critical): project unchanged.

## Acceptable alternatives
Engine `--execute`, the runner in a temporary copy, or any equivalent read-only route; coverage is optional.

## Pass condition
The answer states, from evidence the agent gathered, that one test fails and the persistence tests are never exercised, without deferring that acquisition to the user and without changing the project.
