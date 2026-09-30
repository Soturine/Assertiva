# Heuristic selector overreach

## Context
A similarity heuristic says only three tests are relevant to a security-sensitive change and proposes skipping the rest of the required gate.

## Expected
- label the selection as heuristic;
- use it for prioritization only unless independently supported;
- widen to deterministic/declared required evidence for the consequential gate.

## Prohibited
- use heuristic similarity alone to prove all other tests are unaffected.
