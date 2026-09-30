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

Assertiva does **not** require a graph database. The graph is a semantic model that can be derived from source analysis, runtime coverage, Git history, test metadata, requirements, and CI evidence.

## Progressive diagnostics

```text
D0 Summary
D1 Failure
D2 Context
D3 Trace
D4 Forensic
```

The agent starts compact and escalates only when the current hypothesis needs more evidence. Raw logs/traces remain retrievable artifacts rather than being discarded.

## Current status

Assertiva is currently **M0: useful Agent Skill + specification + deterministic utilities**.

Implemented now:
- canonical `SKILL.md`;
- architecture and evidence contracts;
- human-readable eval catalog;
- JSON schemas/examples for future tooling;
- JUnit XML compact summarizer;
- repository/spec validator;
- CI for the deterministic utilities.

Specified but not yet implemented:
- universal test discovery;
- multi-language Test Impact Analysis engine;
- automatic Test Evidence Graph construction;
- framework adapters for pytest/Jest/Vitest/Playwright/JUnit/Gradle/.NET/etc.;
- mutation orchestration;
- historical flake/runtime/failure intelligence;
- CLI/MCP service;
- real multi-agent benchmark harness integration.

See [STATUS.md](STATUS.md) and [ROADMAP.md](ROADMAP.md).

## Design principles

- **Evidence over green status.**
- **Behavior over coverage percentage.**
- **Smallest sufficient evidence first; broader confidence when required.**
- **Never weaken a test merely to make it pass.**
- **Retries classify flakiness; they do not erase the first failure.**
- **Selector uncertainty widens execution.**
- **Raw evidence is retained; agent context is compressed.**
- **Framework capability detection beats hardcoded `-vvv`.**
- **Provider-neutral core; thin Claude/Codex/Cursor/MCP/CI adapters later.**
- **No hard dependency on Derivanta, Chisel, testmon, Nx, Playwright, Stryker, PIT, or another external tool.**

## Repository map

```text
SKILL.md                      canonical agent contract
docs/                         architecture and engineering semantics
references/                   runner/adaptor reference material
schemas/                      machine-readable contracts
scripts/                      deterministic utilities
tests/                        tests for deterministic utilities
evals/                        behavioral conformance cases
examples/                     example structured evidence
research/                     dated ecosystem benchmarks
.github/workflows/            repository CI
```

## Ecosystem position

Assertiva combines ideas that currently exist separately:

- test impact analysis and code/test graphs;
- changed-project/test selection;
- mutation testing;
- test smell analysis;
- trace-on-failure diagnostics;
- risk-based test strategy;
- agent skill progressive disclosure;
- compact structured evidence for LLM contexts.

The differentiated goal is the **composition**:

```text
impact
-> test quality
-> evidence strength
-> failure localization
-> diagnostic cost
-> agent context cost
-> confidence expansion
```

See [research/2026-09-30-ecosystem-benchmark.md](research/2026-09-30-ecosystem-benchmark.md).

## Relationship with Derivanta

Assertiva is independent. Derivanta can consume it as a specialized test-assurance implementation, but neither project should duplicate the other's semantic ownership or require the other to function.

See [docs/DERIVANTA_INTEGRATION.md](docs/DERIVANTA_INTEGRATION.md).

## Non-goals

Assertiva is not:
- a universal replacement for pytest/Jest/Playwright/JUnit/etc.;
- a coverage-percentage optimizer;
- a mandate to run fewer tests at all costs;
- a retry-until-green system;
- a tool that assumes every failing test is correct;
- a reason to replace release gates with selective testing;
- a generic QA management suite.

## Quick use as an Agent Skill

Give an agent this repository or install/copy the skill according to the Agent Skills format, then ask for tasks such as:

- "Audit whether this test suite is actually strong."
- "Which tests should I run after this change?"
- "This E2E failed; localize the smallest reproducer."
- "Refactor this module without weakening confidence."
- "Why is CI green if this behavior is still wrong?"
- "Reduce test/trace token usage without hiding evidence."

The canonical behavior is in [SKILL.md](SKILL.md).

## License

No license has been selected yet. The repository is currently private; choose a license deliberately before public distribution.
