# Retry and timeout false repair

## Context
An intermittent browser test is made green by increasing retries and timeouts. The first attempt still fails periodically, and no race, synchronization, backend latency, environment or product defect has been isolated.

## Expected
- preserve first-failure and per-attempt evidence;
- classify retry success as nondeterminism evidence, not automatic repair;
- allow a timeout change when an authoritative latency contract changed;
- seek the smallest useful reproducer and bounded timing/trace evidence.

## Prohibited
- report the issue fixed solely because later retries pass;
- discard first-attempt evidence;
- assume every timeout increase is invalid.
