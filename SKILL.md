# Assertiva — Adaptive Test Intelligence & Assurance

Use Assertiva when the task involves test-suite quality, affected-test selection, failure diagnosis, E2E localization, regression evidence, test-output/context cost, flaky behavior, mutation/negative controls, or refactor safety.

## Goal

Produce the greatest reasonable evidence of correctness at the lowest reasonable execution, investigation, and agent-context cost without weakening the claim being made.

~~~text
FAST FEEDBACK
!= REGRESSION CONFIDENCE
!= TEST QUALITY
~~~

## Modes

### AUDIT
Determine whether existing tests actually provide meaningful evidence.

Inspect as applicable:
- authoritative requirement/invariant/oracle;
- assertion strength and observable effects;
- missing negative, boundary, failure, recovery, concurrency, authorization, migration, and retry cases where material;
- tests with no meaningful assertion;
- tests coupled to implementation instead of contract;
- mocks that replace the behavior/boundary being claimed;
- integration fidelity;
- duplicate/redundant tests;
- fixtures hiding impossible/privileged state;
- flaky or retry-dependent behavior;
- critical behavior protected only by E2E;
- E2E journeys with no useful lower-layer isolation;
- giant opaque snapshots;
- mutation, negative-control, differential, and independent evidence;
- exact revision/environment/configuration/test-run provenance.

Coverage and test count are diagnostics, not proof.

### SELECT
Choose candidate tests for the current change using the strongest available evidence from changed symbols, imports/dependencies, runtime coverage, test-to-code maps, contracts, critical journeys, past defects, ownership, Git history, and configuration/runtime relationships.

Always expose selector limitations. If impact data is incomplete, stale, dynamic, configuration-sensitive, or high-risk, broaden execution.

### RUN
Run the smallest sufficient high-signal evidence first when project policy permits.

~~~text
change
-> impact hypotheses
-> cheap/high-signal tests
-> compact structured result
-> failure? localize + diagnose
-> fix
-> reproducer
-> affected regression
-> confidence expansion
~~~

Do not report a selected subset as full-suite or release proof.

### DIAGNOSE
1. identify the exact failing check and first divergent stage;
2. cluster likely shared failures before flooding context;
3. find the smallest useful reproducer;
4. descend from E2E to integration/contract/component/unit only when it isolates the same failure;
5. increase diagnostics only as necessary;
6. classify product defect, test/oracle defect, environment/infra defect, data problem, flake, or unresolved.

After repair, return to composition-level evidence when the claim still depends on it.

### VERIFY
After a fix or refactor:
1. rerun the minimal reproducer;
2. rerun affected dependent tests;
3. run affected regression;
4. run relevant integration/contract/E2E;
5. run broader/full gates when risk, milestone, release policy, selector uncertainty, or project rules require them.

## Progressive Diagnostic Escalation

- D0 Summary — run identity, selected/executed/pass/fail/skip counts, duration.
- D1 Failure — exact test, assertion, exception, source location.
- D2 Context — expected/actual, relevant state, bounded logs, short traceback.
- D3 Trace — selected full traceback/log/network/DB/browser trace/screenshots.
- D4 Forensic — selective instrumentation, profiling, repeated executions, race/concurrency diagnostics.

Never assume -v, -vv, or -vvv mean the same thing across runners. Detect the framework and use native capabilities.

## Failure-guided E2E decomposition

~~~text
Checkout E2E
  -> Login
  -> Cart
  -> Payment
  -> Order

FAIL: Payment
  -> payment integration
  -> payment contract
  -> payment service/domain
  -> gateway/repository boundary
~~~

Do not repeatedly rerun an expensive E2E when a smaller safe reproducer can localize the same stage. Do not permanently replace required E2E evidence with lower-level tests.

## Test Evidence Graph

~~~text
Requirement
-> Behavior
-> Component
-> Code
-> Test
-> Assertion
-> Evidence
-> Run
~~~

Relations may include depends_on, validates, covers, kills_mutant, reproduces, isolates, and composes_into.

Treat graph edges as evidence-bearing claims with provenance and limitations, not automatic truth.

## Token-aware evidence

Prefer compact structured summaries with raw evidence references. Never save tokens by hiding failures, skipped/not-run tests, retries, selector limitations, environment/configuration, exact revision, fidelity, contradictions, or residual unknowns.

Raw logs/traces should remain retrievable when practical.

## Flaky tests

A retry is evidence about flakiness only if the first failure is preserved.

Never retry until green and discard earlier failures; never inflate timeout as the default fix; never quarantine silently.

## Test changes

Never weaken a test merely to make it pass. A test may change when evidence shows the oracle/specification/test is wrong, stale, ambiguous, or intentionally superseded.

## Refactor safety

Before consequential refactoring establish authoritative desired behavior. Use characterization tests when legacy behavior is unclear, mark known defects so characterization does not canonize them, and use differential/reference/golden/property tests when suitable.

Use affected tests for fast feedback; expand regression/integration/E2E evidence before claiming preserved behavior.

## Selection expansion triggers

Broaden execution when material behavior depends on reflection/dynamic loading/plugins, feature flags/configuration, schema/migrations, generated assets/code, global/shared fixtures, external services/files/devices, concurrency/timing, security/safety/financial/irreversible behavior, stale impact data, semantic effects wider than the diff, or release/milestone policy.

## Mutation and test-the-test

Use mutation testing, negative controls, deliberate invariant violations, differential checks, or independent tests when test strength is uncertain. Do not require one mutation tool or universal mutation score.

## Provider neutrality

Keep the core usable with Claude Code, Codex, Cursor-like agents, CI jobs, local shells, or future clients. Provider-specific packaging should be thin.

## Current maturity

The skill contract is usable today. Universal discovery, impact-graph construction, framework adapters, mutation orchestration, historical intelligence, CLI/MCP, and executable eval harness are roadmap work and must not be claimed as implemented.
