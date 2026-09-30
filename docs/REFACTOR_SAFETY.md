# Refactor Safety

## Goal
Allow structural change while preserving intended behavior and detecting accidental semantic drift.

## Before refactor
Establish authoritative intended behavior, public/internal contracts, known defects, supported configurations/platforms, representative tests, and material performance/security/operational constraints.

## Characterization
Use characterization tests when legacy behavior is unclear. They describe what the current implementation does, not automatically what the product should do. Mark known defects and disputed behavior.

## Differential testing
When old/new implementations can coexist, run controlled inputs through both, compare normalized outputs/state/errors/effects, and classify differences as intended, defect fix, acceptable nondeterminism, regression, or unknown.

## Increment loop
~~~text
baseline
-> small coherent refactor
-> affected high-signal tests
-> inspect failure/diff
-> next increment
~~~

At integration/release boundaries expand confidence according to project policy.

## Test refactor
Do not delete tests just because they look redundant. Determine whether they add distinct risk, fidelity, platform, contract, or regression evidence.

Do not update expected values only because the refactored implementation produces different output.
