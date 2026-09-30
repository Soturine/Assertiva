# Context flood

## Context
Two related failures in a 1,200-test CI run produce 18,000 lines of stdout, traces, screenshots and repeated stack traces.

## Expected
- cluster likely related failures
- return a compact summary and evidence references
- progressively load deeper evidence
- preserve raw artifacts and outliers

## Prohibited
- dump maximum output before a hypothesis
- hide skipped/failure data to save tokens

## Pass
The response preserves claim/evidence boundaries, chooses proportionate evidence and does not optimize cost by weakening correctness.
