# Refactor Safety

## Goal

Allow structural change while preserving intended behavior and detecting accidental semantic drift.

A suite is not refactor-safe merely because it is green or has high coverage. It is refactor-safe only to the extent that it can detect unintended changes to the behaviors, contracts, invariants, state transitions, errors, integrations, and non-functional properties that matter.

## Refactor Confidence

Before a consequential refactor, Assertiva should answer:

- what behavior must remain unchanged?
- which tests currently protect each important behavior/contract?
- which important behavior is unprotected or protected only weakly?
- which tests are too implementation-coupled and may fail even when behavior is preserved?
- which behaviors are protected only by expensive E2E tests?
- which error/validation contracts can accidentally drift?
- which configuration/platform/database/integration variants matter?
- which performance/security/reliability properties must not regress?
- what evidence is still missing before the refactor is considered safe?

The goal is not literal "100% of everything". The goal is **behavioral protection proportional to risk**.

## Refactor Safety Matrix

For the refactored scope, map material behavior to evidence:

~~~text
Behavior / Contract
    -> unit/property/characterization evidence
    -> integration/contract evidence
    -> E2E/composition evidence
    -> non-functional evidence when relevant
    -> current confidence / known gaps
~~~

A strong refactor safety net usually contains multiple complementary layers rather than one giant test type.

## Refactor Readiness Gate

A large refactor should not start as "safe" when important behavior has no credible detector.

Classify the target scope:

- **READY** — material behavior and contracts have adequate, replayable protection for the intended refactor.
- **READY_WITH_GAPS** — refactor may proceed incrementally, but named gaps require extra characterization/contract/integration evidence and tighter checkpoints.
- **NOT_READY** — important behavior is unknown or weakly protected enough that structural change could silently break the product.
- **UNKNOWN** — inspection/evidence is insufficient.

Do not convert this into an arbitrary coverage threshold.

## Before refactor

Establish:
- authoritative intended behavior;
- public/internal contracts;
- known defects;
- supported configurations/platforms;
- state transitions and side effects;
- structured error/validation contracts;
- representative parameter/data partitions;
- concurrency/timing assumptions where material;
- persistence/schema/migration behavior;
- external integration contracts;
- representative E2E journeys;
- material performance/security/operational constraints.

## Characterization

Use characterization tests when legacy behavior is unclear. They describe what the current implementation does, not automatically what the product should do.

Mark:
- known defects;
- disputed behavior;
- historical quirks;
- accidental behavior that must not silently become a permanent requirement.

Characterization establishes a behavioral baseline so structural changes become visible.

## Differential testing

When old/new implementations can coexist:
- run controlled inputs through both;
- compare normalized outputs;
- compare state changes and persisted data;
- compare emitted events/messages;
- compare structured errors;
- compare externally visible side effects;
- classify differences as intended, defect fix, acceptable nondeterminism, regression, or unknown.

Differential equality is useful evidence, not automatic proof of correctness: both implementations can share the same bug.

## Contract preservation

Refactoring must protect more than return values.

Depending on the project, contracts may include:
- API/schema shape;
- error type/code/path/status;
- database effects and transactionality;
- emitted events/messages;
- ordering/idempotency;
- authorization boundaries;
- file/network/device behavior;
- backward compatibility;
- serialization;
- latency/resource ceilings.

## Coverage during refactor

Coverage is useful for finding unexecuted surfaces, but line coverage alone is not a refactor-safety guarantee.

Use the strongest available evidence:
- branch/decision coverage for alternate control flow;
- parameterized/data-driven cases for relevant partitions;
- property tests for invariants;
- mutation/negative controls to challenge the safety net;
- test-specific/runtime coverage to connect changed code to tests;
- integration/E2E evidence for cross-boundary behavior.

The question is not "did tests execute every line?" but "would the suite detect a meaningful unintended behavioral change in the refactored scope?"

## Increment loop

~~~text
baseline
-> establish/refine safety net
-> small coherent refactor
-> run smallest affected high-signal evidence
-> inspect failure/difference
-> fix or classify intentional change
-> affected regression
-> next increment
~~~

At coherent checkpoints:
- rerun broader affected evidence;
- re-evaluate the impact graph;
- update characterization/contract tests if authority changed deliberately;
- preserve exact revision and run evidence.

At integration/release boundaries expand confidence according to project policy.

## Whole-project refactor

For a broad modernization/rewrite, do not treat one global green suite as enough.

Partition the system into behaviors/vertical slices and track preservation across them:

~~~text
Project behavior inventory
  -> protected
  -> weakly protected
  -> characterization only
  -> integration-only
  -> E2E-only
  -> unprotected
  -> unknown
~~~

Prioritize high-risk/unprotected slices before restructuring them.

For rewrite/strangler/replacement work, use old-vs-new differential/reference evidence where feasible, plus contract/E2E verification at system boundaries.

## Test refactor

Tests themselves may need refactoring.

Do not delete tests just because they look redundant. Determine whether they add distinct:
- risk coverage;
- fidelity;
- platform/configuration coverage;
- contract protection;
- historical regression evidence;
- diagnostic localization.

Do not update expected values only because the refactored implementation produces different output.

## Test-the-safety-net

Before trusting the suite for a high-consequence refactor, challenge it where proportionate:

- mutation testing;
- deliberate negative controls;
- known historical regressions;
- boundary perturbations;
- contract violations;
- property/metamorphic checks;
- intentionally broken candidate implementation in a sandbox.

If material faults survive, the suite is not yet a sufficient safety net for that claim.

## Completion claim

"Refactor preserved behavior" requires evidence that matches the refactored scope.

Report:
- what behavior/contracts were protected;
- which tests/evidence were used;
- which refactor increments were verified;
- what changed intentionally;
- what remains weakly protected, untested, not run, or unknown;
- whether broader integration/E2E/release evidence is still required.
