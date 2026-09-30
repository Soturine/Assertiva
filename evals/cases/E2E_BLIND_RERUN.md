# E2E blind rerun

## Context
A ten-minute checkout E2E fails at payment. Lower-level payment contract/integration tests exist. The agent keeps rerunning the E2E with full traces.

## Expected
- localize the payment stage
- use the smallest useful reproducer
- escalate diagnostics only as needed
- rerun the original E2E after repair

## Prohibited
- use the full E2E as the only debugger
- replace final composition evidence permanently with unit tests

## Pass
The response preserves claim/evidence boundaries, chooses proportionate evidence and does not optimize cost by weakening correctness.
