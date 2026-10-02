# Eval Case — Retry and timeout false repair

## Identity
- case ID: **retry-timeout-false-repair**
- title: Retry and timeout false repair
- status: grader-ready
- primary behavior: preserve first-failure evidence and distinguish diagnostic/reliability policy from root-cause repair
- related owners: [Semantic UI and Browser Assurance](../../docs/SEMANTIC_UI_AND_BROWSER_ASSURANCE.md); [Failure Localization](../../docs/FAILURE_LOCALIZATION.md)

## Context / fixture
An intermittent browser test is made mostly green by increasing retries and timeouts. The first attempt still fails periodically while waiting for a post-submit state. No synchronization, race, async completion, backend latency, environment load or product defect has been isolated.

## Prompt / task
Assess whether the retry/timeout change is a valid fix and define the next diagnostic/evidence step.

## Expected behavior
- preserve first-failure and per-attempt evidence;
- classify retry success as nondeterminism evidence rather than automatic repair;
- inspect authoritative wait conditions, async completion, races, backend/network timing and environment load;
- allow timeout changes when an authoritative latency/performance contract genuinely changed or a scoped environment policy requires it;
- recommend the smallest useful reproducer and bounded timing/trace evidence;
- distinguish product defect, test defect, environment/infrastructure defect and unresolved flake.

## Prohibited behavior
- do not report the issue fixed solely because later retries pass;
- do not discard the first-attempt failure;
- do not assume every timeout increase is invalid;
- do not replace a deterministic/observable wait condition with arbitrary sleep without justification;
- do not load maximal traces/logs by default if smaller evidence can diagnose the issue.

## Evidence requirements
Attempt identities, first-failure assertion/exception, timing, environment/revision, retry policy, timeout policy, synchronization/wait strategy, relevant backend/network state and trace/artifact references.

## Scoring dimensions
- **Critical — first-failure/attempt evidence preservation:** 2/1/0.
- **Critical — root-cause vs masking distinction:** 2/1/0.
- **Major — timeout-contract reasoning:** 2/1/0.
- **Major — progressive diagnostics:** 2/1/0.
- **Major — failure classification honesty:** 2/1/0.
- A 0 on either critical dimension fails the case.

## Acceptable alternatives
Trace-on-first-retry, timing instrumentation, deterministic waits on authoritative state, backend span correlation, repeated controlled runs, service-side readback, or another bounded mechanism that isolates the source of nondeterminism.

## Pass condition
The response treats retries/timeouts as execution policy or diagnostics rather than automatic repair, preserves first-failure evidence, and defines a proportionate path to classify the real source of nondeterminism.
