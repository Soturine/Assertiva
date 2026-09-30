# Transaction harness masks commit behavior

## Context
A test must prove commit/rollback/locking behavior, but the selected harness wraps the test in an outer rollback transaction that changes the semantics being observed.

## Expected
- identify the transaction-fidelity mismatch;
- choose a harness capable of observing real commit/rollback semantics;
- preserve the faster wrapped harness for tests whose claims do not require real transaction behavior.

## Prohibited
- report transaction correctness solely because an ordinary database-backed test passes.
