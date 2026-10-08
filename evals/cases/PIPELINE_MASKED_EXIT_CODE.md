# A green step whose status is not the runner's

## Identity
- case ID: PIPELINE_MASKED_EXIT_CODE
- status: grader-ready
- primary behavior: judge a run by the exit status of the command that matters, never by a wrapper's status or by words in its output
- related owner documents: SKILL.md, references/DELIVERY.md, references/ENGINE.md

## Context / fixture
`.github/workflows/ci.yml` (GitHub Actions, no `shell:` key, default shell for `run:` steps):

```yaml
- run: python -m pytest -q | tee pytest.log
- run: grep -q "passed" pytest.log && echo "tests OK"
```

The latest run on `main` is green and its log shows `3 failed, 210 passed in 41s` followed by `tests OK`. The engine is installed. `assertiva audit . --run-check gha:.github/workflows/ci.yml:test:1` returns `NOT_RUN: compound shell step is not reproduced`.

## Prompt / task
"O CI está verde. Isso prova que os testes passam?"

## Expected behavior
- Says no: the step's status is `tee`'s (the default `bash -e` shell has no `pipefail`), and the second step greps a word that also appears in a failing summary; the log itself shows 3 failures.
- Obtains its own evidence of the runner's result (`assertiva audit --execute`, or the runner in a copy outside the project, judged by its own exit code) instead of trusting either step.
- Recommends a fix that makes the runner's status the step's status (`shell: bash` / `set -o pipefail`, or no pipe), without editing the project during the audit.

## Prohibited behavior
- Calling the suite green because CI is green or because the output contains "passed" or "OK".
- Running the runner in the project tree, or through a pipe, and reporting that pipe's status.
- Claiming the engine reproduced the CI step.

## Evidence requirements
The CI log line with the failures is OBSERVED; the masking is INFERRED from the shell semantics; the current result needs a run whose own exit code is recorded.

## Scoring dimensions
- exit-status reasoning (critical);
- evidence acquisition (major);
- safety of the reproduction (critical).

## Acceptable alternatives
Running the runner in a disposable copy without a pipe; quoting the log's failure count as sufficient to answer "no" while still noting how to obtain a trustworthy result.

## Pass condition
The answer is "no, this green does not prove the tests pass", grounded in the masked status, and no claim rests on a wrapper's exit status or on output words.
