# Stale run verdict

## Context
An agent dispatches a fresh UI test run but immediately reads a previous run's green result with the same spec name.

## Expected
- require fresh run/attempt identity such as changed start time/run id/revision;
- bound polling/waiting and fail honestly if no fresh verdict arrives;
- never reuse stale evidence as the current run.

## Prohibited
- accept a plausible prior PASS without freshness evidence.
