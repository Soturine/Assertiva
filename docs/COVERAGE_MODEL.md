# Coverage Model

Coverage is execution evidence, not correctness evidence.

## Metrics

Normalize without conflating:
- statement / line;
- branch / decision;
- condition when exposed by the tool;
- function / method;
- instruction / bytecode;
- path when supported;
- per-test runtime mapping;
- mutation outcome;
- requirement/behavior traceability as a separate concept.

## Record

Preserve tool/version, metric kind, covered/missed/total units, scope, aggregate-vs-test-specific context, revision, exclusions, generated/synthetic-code treatment and raw artifact reference.

## Interpretation

100% line coverage can still miss alternate branches and cannot prove that assertions/oracles are meaningful. Branch coverage can still miss condition combinations, integration fidelity and domain invariants.

Coverage gates may exist in the target project, but Assertiva must state what the metric does and does not prove.

## Refactor use

Coverage helps locate unexecuted surfaces and can support test-impact maps. Refactor confidence additionally needs behavioral/contract evidence and, where proportionate, test-the-test evidence such as mutation or deliberate negative controls.
