# Selector survives non-behavioral refactor

## Context
A test suite is being evaluated for refactor safety. The UI is intentionally restructured with wrapper insertion and class renaming while accessible role/name, visible content, actions and resulting state remain unchanged.

## Expected
- use the mutation as a challenge to test implementation coupling;
- treat semantic behavior preservation as the invariant;
- identify tests that fail only because incidental structure changed;
- keep legitimate structural/visual-contract tests separate from behavior-contract tests.

## Prohibited
- require all tests to survive changes to behavior they actually own;
- treat any failing selector as proof that the product changed.
