# Parameterized, Property, Fuzz, and Metamorphic Testing

## Parameterized / table-driven

Parameterized tests are one test definition with multiple concrete invocations.

Audit both levels:
- definition quality and oracle;
- material coverage of parameter/data partitions;
- individual invocation identity and results.

Do not inflate suite quality by counting many near-identical rows as independent behaviors.

Useful parameter design can cover boundaries, equivalence classes, invalid classes, combinations, configuration matrices and regression examples.

## Property-based testing

Record:
- property identity;
- generator/strategy identity and version when available;
- seed/replay token;
- run count/budget;
- counterexample;
- minimized/shrunk counterexample;
- assumptions/preconditions;
- failure artifact.

A property test with no replayable counterexample is weaker for diagnosis.

## Fuzz testing

Preserve corpus/crash input, seed, engine/version, sanitizer/runtime configuration, duration/budget and minimization where available.

## Metamorphic testing

When an exact oracle is hard, test relations that should remain true across transformed inputs. Record the metamorphic relation as the oracle, not merely that two executions differed.

## Randomness

Randomization may improve exploration but should not destroy reproducibility. Capture seed/state when the framework supports it. Repeated success is not mathematical proof over an unbounded input domain.
