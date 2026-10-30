# Two failures in a 1,200-test CI run buried in 18,000 lines of output

## Answer

What can be claimed: a CI run reported two failing tests out of about 1,200 test results. That run is **not green**, whatever passed around those two. Beyond that, very little is settled. The two failures are "related" only as a hypothesis until their fingerprints are compared. Their cause (product, test, environment, flake) is unknown. Which revision the run proves is unknown until its head SHA is checked against `git rev-parse HEAD`. The 18,000 lines are raw material to reduce, not evidence to paste or skim. The right move is to work from the runner's structured results and escalate verbosity only as far as the diagnosis needs.

What this answer rests on: only the task description. I have not seen the log, the JUnit/CTRF results, the screenshots, the workflow or the run's metadata, and I ran nothing.

## Claims and their basis

| Claim | Basis | Evidence / what would settle it |
| --- | --- | --- |
| The CI run had 2 failing tests | OBSERVED as reported (counts from the context) | The runner's own summary or structured results (JUnit XML / CTRF), not grep for "passed" or "failed" in stdout |
| "1,200 tests": unit not stated | UNKNOWN unit | Say whether these are test declarations, parameterized invocations, or attempts including retries; the remaining ~1,198 are not automatically "passed": skipped, xfailed, deselected and errored must be counted separately |
| The run as a whole failed | INFERRED from 2 failures (assuming they are not ignored or quarantined), to be confirmed by the job's own conclusion/exit status | Provider run conclusion. A step piped through `tee`/`tail` without `pipefail` could report green despite failures, so check that too |
| The run corresponds to the audited revision | UNKNOWN | `gh run view <id> --json headSha,conclusion,jobs,url,workflowName` compared with `git rev-parse HEAD` on a clean tree. Only then is it SAME_REVISION |
| The two failures share a cause | INFERRED hypothesis ("related") | Compare their fingerprints: exception type, message, top frames in project code, failing assertion, test fixture/setup stage |
| Cause class (product defect, test/oracle defect, environment/infrastructure, data, flake) | UNKNOWN | First divergent stage plus a reproducer. A screenshot or a timeout alone does not classify it |
| They are flaky | Not claimable | A single failure is not flaky. That would need a same-revision, same-environment history with failures and passes. Retries, if any, keep the first failure |
| The passing tests prove the rest of the product | Not claimable | A pass proves only behavior tied to specific tests with meaningful oracles, in that CI environment |

## How I would reduce the 18,000 lines (keeping evidence compact without hiding anything)

1. **Start from structured results, not stdout.** Export the run's JUnit/CTRF (or ingest it with `assertiva audit <p> --test-results <file>`; imported results are EXTERNAL_UNVERIFIED for revision). Use it to list the exact failing test ids, their outcomes, and the skip/error/retry counts.
2. **Identify the first divergent stage** for each failure: setup/fixture, the action, or the assertion. Note whether one failure is a consequence of the other (shared fixture, order dependence, a crashed service).
3. **Cluster by fingerprint.** Deduplicate repeated stack traces down to one representative per distinct fingerprint, recording the count. If the two share a fingerprint, treat them as one cause and two symptoms. If not, two separate investigations.
4. **Escalate only as needed:** summary → failure message → surrounding context → full trace → screenshots/traces (forensic). Look at screenshots only for UI failures where the rendered state is the question.
5. **Keep references, not pastes.** Record the run id, job, step, log line ranges and artifact names for each cited piece, so the summary is compact and every claim can be traced back. Never drop skips, retries, environment details, revision or contradictions to save space.

## What I would do next

1. Tie the run to a revision (head SHA vs HEAD) and confirm the job's own conclusion and exit status.
2. Get the structured results and produce: the 2 failing test ids, their fingerprints, first divergent stage, and the skip/retry/error counts for the rest.
3. Check history if available: are these failures new, recurring, or a regression since a known-good revision? Do failures at the same place appear in earlier runs?
4. Reproduce at the smallest useful level in a disposable copy, through the engine (`assertiva audit <p> --execute`, or `--run-check <check id>` for the exact CI check) or the runner in a copy outside the project. Descend from E2E to a lower layer only if it reproduces the same failure, and do not blindly rerun an expensive E2E. A local reproduction is evidence about the cause, not proof that CI behaves the same (parity: command, selection, environment, services).
5. Classify each cluster (product / test-oracle / environment / data / flake / unresolved) with its evidence.

## Remaining unknowns

The revision the run proves; the counting unit behind "1,200"; how many of the rest were skipped or retried; whether the two failures share one cause; the cause class; and whether the failures are new or recurring. Each is settled by the steps above, which need the run's structured artifacts and provider access to read its metadata. If that access is not available, the answer stays: "CI failure observed; correspondence to HEAD and root cause unknown."

No engine run was performed in this context, so no Assurance Report was produced.
