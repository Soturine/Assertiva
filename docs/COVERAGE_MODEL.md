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

Implemented: coverage.py JSON, istanbul json-summary, LCOV, Cobertura XML and JaCoCo XML (report-level counters) normalize to covered/total per kind with tool, scope, source and limitations. A Cobertura report with rates only records that its denominators are unknown. An unreadable report carries an error and no numbers.

## Interpretation

Compare counts, not only percentages. Covered is higher-is-better; total is contextual. When the total changes, the two percentages measure different populations: the percentage delta is contextual and carries the denominator note. More covered and fewer missed units is better under every reading; otherwise qualification is UNKNOWN for it (80/100 = 80% vs 90/120 = 75%: covered rose, total changed, missed rose, percent fell). Fewer covered units over a population that did not shrink is a regression.

100% line coverage can still miss alternate branches and cannot prove that assertions/oracles are meaningful. Branch coverage can still miss condition combinations, integration fidelity and domain invariants.

Coverage gates may exist in the target project, but Assertiva must state what the metric does and does not prove.

## Refactor use

Coverage helps locate unexecuted surfaces and can support test-impact maps. Refactor confidence additionally needs behavioral/contract evidence and, where proportionate, test-the-test evidence such as mutation or deliberate negative controls.
