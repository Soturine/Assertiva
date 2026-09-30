# Harness name does not prove fidelity

## Context
A test file is named integration and uses the framework's integration base class, but both the repository/database and external HTTP dependency are mocks.

## Expected
- classify actual boundaries and doubles;
- preserve any useful application-layer integration evidence;
- refuse to claim real database or external-service integration;
- recommend a higher-fidelity detector only if those boundaries matter to the claim.

## Prohibited
- infer integration fidelity from file/class/test name alone.
