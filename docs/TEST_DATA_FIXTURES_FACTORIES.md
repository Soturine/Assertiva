# Test Data, Fixtures, Factories, and Lifecycle

Test data is part of the harness and can create false confidence, flakiness, or order dependence.

## Data-source classes

- literal inline examples;
- parameter/table/data-provider rows;
- static fixture files or seeded database snapshots;
- builders/factories/object mothers/helpers;
- framework fixtures/dependency injection;
- Faker/generated examples;
- property-based strategies/generators;
- fuzz seed corpus;
- production-derived anonymized fixtures where policy permits.

## Record for a fixture/data provider

Preserve where relevant:
- identity/source;
- scope/lifetime: invocation, test, class/file, worker, suite/session;
- setup and teardown/reset behavior;
- mutable/shared vs isolated;
- seed/version/corpus provenance;
- database/schema/config version;
- external resource ownership;
- parameterized dimensions;
- whether data is realistic, synthetic, sanitized, or production-derived;
- failure cleanup behavior.

## Isolation

Audit for:
- state leaking across tests;
- dependence on test order;
- setup that survives a failing test;
- session/class fixtures mutated by tests;
- database rows not reset;
- caches/files/environment variables left behind;
- parallel workers colliding on IDs/ports/databases;
- timestamps/random IDs making exact reproduction impossible.

Random/reverse/shuffle execution is useful as a detector for hidden ordering dependencies but is not a substitute for fixing them.

## Static fixtures vs factories

Static fixtures can be good for stable reference datasets and complex relational state, but may become opaque, stale, coupled to schema and expensive to understand.

Factories/builders often make the intent of each test clearer and vary only the fields that matter, but overly permissive defaults can accidentally create impossible states or hide required fields.

Use both when appropriate. Assertiva should judge whether the data source supports the claim, not mandate one style.

## Generated data

Faker/property/fuzz data should preserve reproducibility information when a failing case matters:
- library/tool version;
- seed/replay token;
- minimized counterexample;
- corpus entry;
- locale/timezone/configuration.

Do not hardcode expected values from a generator whose algorithm/version is intentionally allowed to change unless that exact output is the contract.

## Database fixtures

Framework lifecycle matters. A fixture loaded once per class under a transaction-wrapped harness has different cost/isolation semantics from one reloaded after table truncation or shared across a session.

Assertiva records actual lifecycle and reset semantics rather than treating all 'fixtures' as equivalent.
