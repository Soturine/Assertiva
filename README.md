# Assertiva

**Adaptive Test Intelligence & Assurance for coding agents and engineering teams.**

Assertiva audits whether a test suite provides meaningful evidence, selects the smallest reasonable test surface for the current change or failure, localizes failures without blindly rerunning expensive suites, and expands confidence when risk or lifecycle gates require it.

> A green test suite is not automatically a strong test suite.

## Why

Modern coding agents can generate, modify, run, and even "fix" tests very quickly. That creates a new failure mode: implementation, tests, and validation can all share the same wrong assumption while CI remains green.

Assertiva separates three questions:

```text
FAST FEEDBACK
!= REGRESSION CONFIDENCE
!= TEST QUALITY
```

It asks both:

1. **Are these tests actually good?**
2. **Which tests and diagnostics do we need right now?**

## Core capabilities

### AUDIT — test quality
Inspect assertion strength, oracle authority, missing negative/boundary cases, mock fidelity, flaky behavior, redundant tests, E2E-only critical coverage, mutation/negative-control evidence, integration fidelity, and false-green patterns.

### SELECT / RUN — adaptive execution
Use change impact, dependency/runtime evidence, history, critical journeys, and project policy to run high-signal tests first without pretending a selected subset is equivalent to a full release gate.

### DIAGNOSE — failure localization
When an E2E or large suite fails, find the first divergent stage, descend to the smallest useful reproducer, cluster repeated failures, and progressively escalate diagnostics instead of dumping every trace into an agent context.

### VERIFY — confidence expansion
After a fix, rerun the reproducer, affected regression, relevant integration/E2E evidence, and broader/full gates when required by risk or release policy.

### REFACTOR SAFETY — preserve behavior
Evaluate whether a module or whole project has a strong enough behavioral safety net before structural change. Map important behaviors/contracts to tests and classify the refactor target as READY, READY_WITH_GAPS, NOT_READY, or UNKNOWN.

## Design principles

- **Evidence over green status.**
- **Behavior over coverage percentage.**
- **Deterministic-first core; heuristics/LLM inference are advisory and provenance-labeled.**
- **Language/framework-neutral semantics; adapters translate capabilities instead of redefining policy.**
- **Smallest sufficient evidence first; broader confidence when required.**
- **Never weaken a test merely to make it pass.**
- **Retries classify flakiness; they do not erase the first failure.**
- **Selector uncertainty widens execution.**
- **Raw evidence is retained; agent context is compressed.**
- **Framework capability detection beats hardcoded `-vvv`.**
- **Parameterized/data-driven invocations, structured errors, branch-aware coverage, property/fuzz evidence and dynamic tests are first-class evidence.**
- **No hard dependency on Derivanta or any one runner/tool.**

## Cross-language / cross-framework model

The core works with normalized concepts rather than Python/Java/JS-specific syntax:

```text
suite
→ test definition
→ invocation / parameter case
→ attempt / retry
→ assertion / oracle
→ result
→ coverage / error / trace evidence
→ revision + environment
```

Adapters map pytest, JUnit, Jest, Vitest, Playwright, xUnit/NUnit, Go/Rust/PHP/Ruby ecosystems, custom runners, and future frameworks into this model. Unknown frameworks must degrade conservatively and explicitly, never by silently inventing flags or assuming zero tests.

## Test Evidence Graph

```text
Requirement
  -> Behavior
     -> Component
        -> Code
           -> Test
              -> Assertion
                 -> Evidence
                    -> Run
```

Useful relations include `depends_on`, `validates`, `covers`, `kills_mutant`, `reproduces`, `isolates`, and `composes_into`.

## Current status

Assertiva is currently **M0/M0.1: useful Agent Skill + deterministic semantic foundation**.

Implemented/specification-level foundations include:
- canonical `SKILL.md`;
- deterministic evidence tiers;
- architecture/evidence/refactor contracts;
- definition-vs-invocation identity;
- parameterized/property/fuzz/error-contract semantics;
- test modality guidance;
- eval catalog;
- JSON schemas/examples;
- JUnit XML compact summarizer;
- repository validator and CI.

Still planned:
- universal discovery;
- multi-language Test Impact Analysis engine;
- automatic Test Evidence Graph construction;
- first-party framework adapters;
- mutation orchestration;
- historical flake/runtime/failure intelligence;
- CLI/MCP;
- empirical multi-stack benchmark harness.

See [STATUS.md](STATUS.md), [ROADMAP.md](ROADMAP.md), [Determinism and Evidence Tiers](docs/DETERMINISM_AND_EVIDENCE_TIERS.md), [Refactor Safety](docs/REFACTOR_SAFETY.md), [Test Harness and Fidelity](docs/TEST_HARNESS_AND_FIDELITY.md), [Assertions/Oracles/Observation Surfaces](docs/ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md), and [Agent Skill/CLI/MCP Architecture](docs/AGENT_SKILL_MCP_ARCHITECTURE.md).

## Relationship with Derivanta

Assertiva is independent. Derivanta can consume it as a specialized test-assurance implementation.

## Non-goals

Assertiva is not:
- a universal replacement for test runners;
- a coverage-percentage optimizer;
- a mandate to run fewer tests at all costs;
- a retry-until-green system;
- a tool that assumes every failing test is correct;
- a reason to replace release gates with selective testing;
- a promise that 100% coverage makes refactoring impossible to break.

## License

No license has been selected yet.
