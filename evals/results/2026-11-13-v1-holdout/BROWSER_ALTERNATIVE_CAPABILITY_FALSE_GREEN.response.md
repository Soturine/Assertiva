# Assessment: crawler suite moved from Chromium to the experimental Zig browser

## Answer

The current evidence does not support claiming that the crawler suite works on the Zig browser. The suite's green result is not evidence of crawl correctness here, for two reasons. First, navigation returning without an exception does not show that pages were loaded or that the crawl behaved as before. Second, operations that were skipped are counted as PASS, so a green result can hide operations that never ran. One JavaScript action is also known to fail to persist its state on this browser, which is a real defect that the current reporting may not show.

The memory reduction is a measured cost benefit. It says nothing about correctness and must not be counted toward readiness.

## What the evidence supports

| Claim | Basis | How I know |
| --- | --- | --- |
| Navigation returns without an exception on the Zig browser. | DECLARED by the scenario context | Reported observation, not verified here |
| Memory consumption is lower on the Zig browser. | DECLARED by the scenario context | Reported measurement, not verified here |
| One JavaScript action relies on an unsupported browser API and does not persist its intended state. | DECLARED by the scenario context; consistent with the failure mode | Reported observation; the cause (unsupported API) is INFERRED from it |
| Skipped operations are counted as PASS. | DECLARED by the scenario context | Reported reporting behavior; this is a false-green mechanism, since UNKNOWN or not-run must never count as passed |

Nothing here was run or read by me. No engine run, test run or CI run is part of this assessment.

## What cannot be claimed

- That the Zig browser is a drop-in CDP replacement for this suite. CDP compatibility is a claim about a protocol surface. The suite may use parts of that surface that are missing.
- That the crawl covers the same pages, states or interactions as on Chromium. Successful navigation shows only that navigation did not raise.
- That the suite's pass count reflects executed checks. While skipped operations are counted as PASS, the pass count mixes executed and not-run work.
- That the memory saving makes the migration acceptable. It is a benefit only if the same behavior is observed.
- That the failing JavaScript action is the only unsupported operation. Only one has been reported; the others are UNKNOWN.

## Findings, ranked by consequence

1. **Skipped operations counted as PASS (false green).** This is the most important finding because it turns unknown behavior into apparent success. Any unsupported operation on the Zig browser can be skipped and still appear green. Basis: DECLARED reporting behavior. Consequence: the green suite cannot be used as the migration gate.
2. **Persisted-state defect is hidden by the same false green.** The failing action does not persist its intended state. If the suite checks only that the action returned, or that navigation returned, the defect is invisible. Basis: DECLARED observation, INFERRED that the oracle does not check persisted state. Consequence: a real product-level defect in the crawl could ship with a green result.
3. **Navigation success is a weak oracle for the crawl.** An assertion of "no exception" on navigation is the kind of check that stays green while the page content, the state or the session is wrong. Basis: INFERRED from the scenario. Consequence: the migration needs stronger checks on page state.
4. **Memory reduction is not evidence of equivalence.** It is a measured property of the new browser and says nothing about behavior. Basis: DECLARED. Consequence: it should be reported separately from correctness.

## What I would do next

1. Change the skip accounting first: a skipped, unsupported or not-run operation must be reported as NOT_RUN or UNKNOWN, never as PASS, and the suite's summary must show the three counts separately.
2. Build the list of browser operations the suite actually uses and check each against the Zig browser's supported surface. Mark each as supported, unsupported or unknown.
3. For the failing action, add a test that checks the persisted state after the action (the thing the action is meant to change), not only its return. Run it against Chromium first, so the expected value comes from the intended behavior and not from the current output.
4. Run a negative control: on the Zig browser, the persisted-state test must fail for the unsupported action. If it passes, the oracle is too weak.
5. Run the same suite on Chromium and on the Zig browser side by side, in disposable copies, and compare operation-level results (executed, passed, failed, not run), not only totals. Running this needs the user's approval for the environment.
6. Do not declare the migration ready until every operation in the suite is either verified on the Zig browser or explicitly accepted as not covered.

## Unknowns

- How many operations depend on unsupported APIs, and whether others fail silently.
- How many operations were skipped in the current green runs, and which ones.
- Whether the persisted-state defect is the only one of its kind.
- Whether the crawl's results on the Zig browser match Chromium's on the same pages.
- The CI run identity for the current green result, since no run was observed here.

## Basis of this answer

Answered from the scenario context only. No files were read, no commands were run, and no web search was made. Every observation above is reported by the scenario and is marked DECLARED. The rest is INFERRED from those observations.
