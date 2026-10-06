# Retry until green: what can be claimed

## Situation
A test failed three times and passed on the fourth attempt. CI recorded only the final pass. Nothing else is known: no per-attempt results, no failure messages, no revision-to-revision comparison, no history.

## What can be claimed

| Claim | Supported? | Evidence |
|---|---|---|
| The pipeline reported green for this check | Yes | E0 raw CI status. It proves only that the check passed in the end under the retry policy, on the checks and environment that actually ran. |
| The test passed at least once on this revision | Yes | The final-attempt pass. |
| The test is flaky or nondeterministic on this revision | Strongly indicated | Three failures and one pass on the same code and test imply nondeterminism. This holds only if all four attempts used the same revision and configuration. That is unverified because CI kept no attempt data. |
| The behavior under test is correct | No | A pass that needed retries does not show the behavior is stable. It is also unclear whether a pass on attempt 4 is the real behavior or luck. |
| The test is reliable or the change is regression-safe | No | A green result with a hidden retry history is weak evidence. Green proves only what ran, and here the failure evidence was discarded. |
| The failures were harmless infrastructure noise | No | This is an untested hypothesis. |
| The cause is a product defect, a test or oracle defect, an environment problem, data or order dependence, or a race | Unknown | Nothing observed distinguishes these. Any classification is E4 inference at best. |

The final pass must not be treated as the truth and the three failures as noise. The failures are first-failure evidence and are at least as informative as the pass. A retry policy that hides them has masked a possible race or defect, and it makes the green status misleading.

## Unknowns
- The error messages, stack traces and failure stage of attempts 1 to 3, and whether they were the same failure each time.
- Whether the attempts ran on the same runner, the same state, the same seed and the same data. Retries may reuse polluted state or give different resources.
- Whether the retry is at the test level or the job level, and what the configured retry limit is.
- The test's history: whether it is a known flake, recently changed, or newly added.
- Whether the failure is order-dependent, time-dependent or dependent on parallelism.
- Whether the test exercises real boundaries or mocks. Whether any timeout or wait was recently inflated.
- Whether other tests in the run also needed retries.

## What I would do next
1. **Recover the evidence.** Pull the raw per-attempt artifacts (JUnit XML, runner logs) for the CI run, if they exist. Diagnose at the lowest level first (D1 failure, then D2 context), and move to D3 trace only if needed. Preserve the first-failure evidence.
2. **Reproduce locally with the smallest reproducer.** Run the single test repeatedly (for example 50 to 200 times) with the same seed, and also with a shuffled order, in isolation and in parallel. Record the failure rate, and keep any seed or replay token. Run the sibling tests in the same file or fixture scope too.
3. **Classify the cause.** Use the failing stage and messages to decide between a product defect (race or concurrency), a test or oracle defect (timing assumptions, shared state, order dependence), an environment problem, a data problem, or unresolved. Do not close it as "flaky" without a mechanism.
4. **Fix the root cause.** Use a deterministic wait on an observable condition, isolate state, or fix the race. Do not raise the timeout or the retry count, and do not weaken the assertion. Raising the timeout is not a repair unless the latency contract changed.
5. **Verify.** Rerun the reproducer many times with zero failures. Then rerun the affected dependents, the regression suite and any relevant integration or E2E checks. Return to the original composition-level evidence if the claim depends on it.
6. **Fix the reporting policy.** Make CI record every attempt (attempt number, result, failure output) and mark a test that passed after retry as flaky or "passed on retry", not plain green. Add a flake budget or quarantine with an owner. Retries should not close a gate silently. Keep the local history so stability and failure fingerprints accumulate.
7. **Be honest in reporting.** Until the above is done, report: "green after 3 failed attempts; flaky; cause unknown; correctness of this behavior not established." If the area is under release or refactor scrutiny, treat readiness as READY_WITH_GAPS at best, or UNKNOWN.

If there is no time to investigate, widen verification (rerun the full affected set several times) rather than accept the single green result as proof.
