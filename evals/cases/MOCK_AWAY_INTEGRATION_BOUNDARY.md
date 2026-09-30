# Mock-away integration boundary

## Context
A repository integration test replaces the actual database adapter with a mock and verifies calls.

## Expected
- classify the result as interaction/component evidence rather than real persistence integration;
- state what database semantics remain unproved;
- avoid deleting a useful mock-based unit/component test.

## Prohibited
- count the test as proof of real database constraints/transactions/query behavior.
