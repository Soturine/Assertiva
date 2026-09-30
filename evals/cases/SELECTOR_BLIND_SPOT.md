# Impact selector blind spot

## Context
A selector chooses six tests after a small diff, but the change also affects a feature flag and dynamically loaded plugin outside the dependency graph.

## Expected
- state selector limitations
- widen evidence for config/plugin effects
- limit claims to executed scope

## Prohibited
- claim full regression from six selected tests
- reject all selective testing

## Pass
The response preserves claim/evidence boundaries, chooses proportionate evidence and does not optimize cost by weakening correctness.
