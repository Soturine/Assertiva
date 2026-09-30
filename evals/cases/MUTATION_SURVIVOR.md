# Mutation survivor

## Context
A boundary mutation from >= to > survives despite high coverage.

## Expected
- treat the survivor as an adequacy hypothesis
- inspect the boundary oracle and equivalent-mutant possibility
- add/improve a test when the behavior matters

## Prohibited
- declare the whole suite useless
- chase mutation score blindly

## Pass
The response preserves claim/evidence boundaries, chooses proportionate evidence and does not optimize cost by weakening correctness.
