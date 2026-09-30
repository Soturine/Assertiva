# Assertiva — Adaptive Test Intelligence & Assurance

Use Assertiva when the task involves test-suite quality, affected-test selection, failure diagnosis, E2E localization, regression evidence, test-output/context cost, flaky behavior, mutation/negative controls, or refactor safety.

## Goal

Produce the greatest reasonable evidence of correctness at the lowest reasonable execution, investigation, and agent-context cost without weakening the claim being made.

```text
FAST FEEDBACK
!= REGRESSION CONFIDENCE
!= TEST QUALITY
```

## Deterministic-first evidence policy

Prefer deterministic, machine-verifiable evidence whenever possible.

- **E0 RAW** — native runner/report/source artifact.
- **E1 DETERMINISTIC_DERIVED** — reproducible parsed/normalized result.
- **E2 DECLARED** — project-authored mapping/policy/metadata.
- **E3 HEURISTIC** — fallible static/ranking/similarity/smell signal.
- **E4 INFERRED** — semantic/LLM inference requiring supporting evidence.

E3/E4 may rank, flag, cluster and propose. They must not silently suppress material tests or close consequential gates. When evidence is insufficient, widen execution or report UNKNOWN.

## AUDIT

Determine whether existing tests actually provide meaningful evidence.

Inspect as applicable:
- authoritative requirement/invariant/oracle;
- assertion strength and observable effects;
- negative/boundary/failure/recovery/concurrency/authorization/migration cases;
- integration fidelity and suspicious mocks;
- flaky/retry-dependent behavior;
- duplicate/redundant tests;
- snapshots/goldens and update provenance;
- parameterized/table/data-driven definitions and material invocations;
- property-based/generative tests, seeds and minimized counterexamples;
- fuzz corpora/crash reproducers;
- structured validation/error contracts;
- line/statement vs branch/condition/function/instruction coverage;
- dynamic/generated tests;
- async/concurrency/race assumptions;
- mutation/negative-control/differential/independent evidence;
- exact revision/environment/configuration/run provenance.

Coverage and test count are diagnostics, not proof.

## SELECT

Choose candidate tests using the strongest available evidence from changed symbols, dependency graphs, runtime test-to-code maps, contracts, critical journeys, Git history, known regressions and project-declared mappings.

Always expose limitations. Exact/deterministic mappings can exclude tests only within their proven scope. Heuristic/inferred impact should prioritize, not prove unaffectedness.

## RUN

Run the smallest sufficient high-signal evidence first when policy permits. Do not report a selected subset as full-suite/release proof.

## DIAGNOSE

1. identify failing check and first divergent stage;
2. cluster likely shared failures;
3. find the smallest useful reproducer;
4. descend from E2E only when lower layers reproduce/isolate the same failure;
5. escalate diagnostics D0→D4 only as needed;
6. classify product defect, test/oracle defect, environment/infra defect, data problem, flake, or unresolved.

## VERIFY

After a fix/refactor:
1. rerun minimal reproducer;
2. rerun affected dependents;
3. run affected regression;
4. run relevant contract/integration/E2E;
5. run broader/full gates when risk, milestone/release policy, selector uncertainty, or project rules require them.

## Progressive diagnostics

- D0 Summary
- D1 Failure
- D2 Context
- D3 Trace
- D4 Forensic

Never assume `-v/-vv/-vvv` semantics are portable.

## Test identity

Do not collapse a parameterized/dynamic test definition into one boolean result when individual invocations are observable.

```text
suite → definition → invocation/data case → attempt/retry → result
```

Preserve stable IDs, sanitized parameter identity, matrix dimensions, attempt number and dynamic/partial-discovery status.

## Structured errors

Invalid-input behavior is part of the contract. Prefer stable structured fields such as category/type/code/path/location/context/status and sanitized input over brittle message-only assertions, unless exact wording is itself required.

Pydantic ValidationError is one adapter-specific form, not a core dependency.

## Coverage semantics

Never reduce coverage to one percentage. Preserve metric kind, denominator, scope, exclusions, tool/version and aggregate-vs-test-specific context. Line coverage does not imply branch/condition coverage, and none of them proves oracle adequacy.

## Property/fuzz/metamorphic evidence

Preserve seed/replay token, run budget, counterexample, minimized/shrunk counterexample and corpus where available. Randomized success without replay data is weaker diagnostic evidence.

## Failure-guided E2E decomposition

Do not repeatedly rerun an expensive E2E when a smaller safe reproducer can isolate the same stage. After repair, return to the original composition-level evidence when the claim depends on it.

## Refactor safety

Before consequential refactoring, establish authoritative behavior and build a safety matrix mapping important behaviors/contracts to unit/property/characterization, integration/contract, E2E/composition and non-functional evidence as applicable.

Classify readiness:
- READY
- READY_WITH_GAPS
- NOT_READY
- UNKNOWN

A green suite or 100% line coverage does not make a refactor safe by itself. The question is whether meaningful unintended behavioral changes in the refactored scope would be detected.

For whole-project refactors, inventory behavior slices as protected, weakly protected, characterization-only, integration-only, E2E-only, unprotected, or unknown before restructuring them.

Never weaken test expectations merely to make a refactor pass.

## Test-the-safety-net

Where proportionate, challenge the suite with mutation testing, deliberate negative controls, known historical regressions, boundary perturbations, contract violations, property/metamorphic tests, or intentionally broken candidate implementations in a sandbox.

## Harness, fidelity, observations, data and doubles

Never infer test strength from a framework class, file suffix, or label alone. When integration/UI/API/database fidelity matters, read docs/TEST_HARNESS_AND_FIDELITY.md and record the actual process, transport, persistence, transaction, dependency, UI runtime, matrix and isolation boundaries.

When auditing assertions, map them to behavior claims and observation surfaces using docs/ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md. Status/content/template/context/persistence/call/visual/accessibility observations prove different things.

When fixtures, factories, Faker/generated data, shared setup, database seeds or order-dependence matter, use docs/TEST_DATA_FIXTURES_FACTORIES.md.

When mocks, spies, fakes, patch/monkeypatch, virtual services or containers are involved, use docs/TEST_DOUBLES_PATCHING_AND_VIRTUALIZATION.md. Verify the seam actually used by the SUT and do not mock away the boundary a test claims to integrate.

For HTTP/API/browser/component/mobile/web flows, use docs/WEB_API_UI_TESTING.md and preserve request, auth, state, rendering, accessibility, visual and platform-matrix claims independently.

For implementation/productization of Assertiva itself, use docs/AGENT_SKILL_MCP_ARCHITECTURE.md: Skill owns policy, deterministic core owns reproducible processing, CLI is the default token-efficient agent surface, and MCP is optional for persistent state/graph/artifact/job workflows.

## Token-aware evidence

Prefer compact structured summaries with retrievable raw artifacts. Never save tokens by hiding failures, skips/not-run, retries, limitations, environment/configuration, revision, fidelity, contradictions or unknowns.

## Provider neutrality

Core policy is framework/language/provider neutral. Adapters expose capabilities such as discovery, invocation enumeration, stable IDs, filtering, structured results, retries, coverage, traces, seeds and mutation evidence.

## Current maturity

The semantic contract is usable today. Universal discovery, impact graph construction, adapters, mutation orchestration, historical intelligence, CLI/MCP and executable eval harness remain roadmap work.
