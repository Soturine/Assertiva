# Ecosystem Benchmark — 2026-09-30

Status: dated research, not permanent policy.

Assertiva was designed after comparing several approaches that solve different pieces of the problem.

## Chisel
Project: https://github.com/IronAdamant/Chisel

Observed pattern:
- agent-oriented Test Impact Analysis / code intelligence;
- relationships among source, tests, imports/dependencies and Git history;
- affected-test intelligence exposed to coding agents.

Assertiva adopts the architecture idea that coding agents benefit from first-class test-impact intelligence and graph-like source/test relationships.

Assertiva does not depend on Chisel, assume one engine covers every stack, or treat impact selection as evidence that tests are good.

## pytest-testmon
Reference: https://testmon.org/

Observed pattern: prior execution/dependency information can select tests affected by changed code.

Assertiva adopts runtime test-to-code maps as one selector source. It also makes selector limitations first-class because runtime/dependency models can miss configuration, generated assets, dynamic behavior and external effects.

## pytest focused execution
Reference: https://docs.pytest.org/en/stable/how-to/cache.html

Observed patterns include last-failed, failed-first and stepwise execution.

Assertiva adopts focused rerun/prioritization after failures, but runner-native capabilities belong in adapters rather than one universal CLI recipe.

## Nx affected
Reference: https://nx.dev/docs/features/ci-features/affected

Observed pattern: Git changes plus a project dependency graph select affected projects/tasks.

Assertiva adopts the idea that impact reasoning may happen at project/package granularity as well as individual-test granularity.

## Playwright tracing
References:
- https://playwright.dev/docs/trace-viewer
- https://playwright.dev/docs/test-use-options

Observed pattern: tracing/artifacts can be scoped to failures/retries instead of generated maximally for every successful run.

Assertiva generalizes this into Progressive Diagnostic Escalation.

## Stryker
Reference: https://stryker-mutator.io/docs/

Observed pattern: mutation testing challenges whether tests detect injected faults.

Assertiva adopts mutation/negative controls as a test-the-test technique, without a universal mutation-score target.

## PIT
Reference: https://pitest.org/quickstart/basic_concepts/

Observed pattern: mutation systems can use coverage/timing information to target relevant tests and reduce mutation cost.

Assertiva adopts the broader idea that even expensive assurance techniques can be impact-aware.

## Test-smell analysis

Static detectors and agent review guidance identify patterns such as no assertions, oversized fixtures, order dependence, excessive mocking and implementation coupling.

Assertiva treats smells as hypotheses requiring risk/evidence interpretation, never as a quality score by themselves.

## Synthesis

~~~text
impact-only tool:
change -> selected tests

mutation tool:
code mutation -> killed/survived

test-smell tool:
test source -> smell findings

runner diagnostics:
failure -> logs/traces

Assertiva:
change / suite / failure
 -> impact
 -> test quality
 -> evidence strength
 -> diagnostic depth
 -> failure localization
 -> context/runtime cost
 -> confidence expansion
~~~

## Benchmark conclusion

The ecosystem validates the individual pieces. Assertiva's opportunity is their provider-neutral composition for coding agents, with explicit claim boundaries and empirical measurement of both quality and cost.

Mutable external behavior must be refreshed before implementing adapters.
