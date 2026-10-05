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

It asks four related questions:

1. **Are these tests actually good?**
2. **Which tests and diagnostics do we need right now?**
3. **Does CI/CD actually execute the evidence the repository appears to have?**
4. **What does a green result really prove — and what remains unverified?**

Assertiva is not limited to Test Cases produced by Functional Test Designer and is not architecturally tied to Python, pytest, Django, Playwright, GitHub Actions, or any specific stack. Existing tests, validators, linters, type checkers, build/package steps, schema/migration checks, security checks, hooks, CI/CD gates and deployment verification are all first-class verification evidence through capability-driven adapters. FTD is an optional source of authority-rich Test Cases, not a prerequisite.

Framework/tool-specific support grows adapter by adapter; the core stays language-, framework-, runner- and CI-provider-neutral. Unknown tooling must be preserved as UNKNOWN/CUSTOM evidence rather than guessed or silently ignored.

## Core capabilities

### AUDIT — test quality
Inspect assertion strength, oracle authority, missing negative/boundary cases, mock fidelity, flaky behavior, redundant tests, E2E-only critical coverage, mutation/negative-control evidence, integration fidelity, and false-green patterns.

### SELECT / RUN — adaptive execution
Use change impact, dependency/runtime evidence, history, critical journeys, and project policy to run high-signal tests first without pretending a selected subset is equivalent to a full release gate.

### DIAGNOSE — failure localization
When an E2E or large suite fails, find the first divergent stage, descend to the smallest useful reproducer, cluster repeated failures, and progressively escalate diagnostics instead of dumping every trace into an agent context.

### VERIFY — confidence expansion
After a fix, rerun the reproducer, affected regression, relevant integration/E2E evidence, and broader/full gates when required by risk or release policy.

### SEMANTIC UI ASSURANCE — test the user contract
For browser/component UI tests, distinguish semantic role/name/state, keyboard/focus behavior, interaction, visual output, storage/network state and backend effects. Detect locators coupled to incidental DOM structure, preserve legitimate test-ID/structural contracts, and challenge UI tests with non-behavioral structural mutations when useful.

Accessibility-tree and ARIA evidence are first-class observation surfaces, but zero automated accessibility findings do not prove complete accessibility. Snapshot updates require intent/provenance, and retries/timeouts do not erase the first failure.

### VERIFICATION SURFACE — understand every gate
Inventory the checks that can influence confidence or block delivery: tests, lint, type checks, format/static analysis, generated-code/schema checks, migrations, localization/i18n validation, security scans, build/package/container/startup/health/deploy checks, hooks and custom project commands. Preserve where each check runs, whether it is blocking/advisory/unknown, and what evidence it actually produces.

### PIPELINE & DELIVERY ASSURANCE — challenge false green
Compare the repository verification surface with the commands and environments actually observed locally, in hooks, CI/CD and deployment. Surface omitted checks, narrowed scopes, matrix gaps, source-tree-vs-built-artifact gaps and other cases where one green stage does not represent the delivery path.

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

## User-facing workflow

Assertiva keeps the interface intentionally small:

```bash
assertiva audit
assertiva improve
```

- `audit` analyzes the project and **never changes project files**. It inventories tests/checks, measures available evidence, finds gaps and produces recommendations plus an HTML Assurance Report.
- `improve` starts from the audit, builds candidate test/verification improvements in an isolated workspace, **tests the tests**, compares baseline vs candidate, and asks for approval before any project change. Candidate qualification can include mutation/negative controls, original regression, coverage/oracle analysis, pipeline-equivalent checks, build/artifact verification and an explicitly authorized non-production preview deploy when supported.

Isolation, candidate workspaces, patch application and post-apply verification are implementation details rather than extra user-facing modes. The runtime enforces write boundaries; prompt instructions alone are not considered sufficient protection.

The HTML report is a first-class product surface. It should be responsive, accessible and visually calm, with summary cards, charts, filters, expandable evidence, before/candidate/applied comparisons, Evidence Delta, Verification Surface, and a final **What does green prove?** claim boundary. Candidate metrics must never be presented as already applied. Original tests stay untouched in the project until human approval; retirement candidates are never auto-deleted or silently commented out.

See [User Experience and Reporting](docs/USER_EXPERIENCE_AND_REPORTING.md).

## Current status

Assertiva is in **M1 — Executable Assurance (active)**. `audit` and `improve` work end to end for the first reference adapters (pytest, GitHub Actions, pre-commit); other ecosystems report UNKNOWN rather than "0 tests".

```bash
python -m pip install -e .

# Read-only audit (static); add --execute to run tests natively in a disposable copy.
assertiva audit .
assertiva audit . --execute --coverage-json coverage.json --output json

# Improve: one command, called again at each step.
assertiva improve .                      # measure baseline, create the candidate workspace
#   ...write candidate changes in the printed workspace...
assertiva improve . --negative-controls controls.json   # qualify; project still untouched
assertiva improve . --approve tests/test_new.py          # apply only the approved changes, then verify
assertiva improve . --discard                            # or drop the candidate
```

Reports (JSON + self-contained HTML) are written under `ASSERTIVA_HOME` (default `~/.assertiva`), outside the project. `--python` selects the project's interpreter.

What runs today:
- runtime-enforced read-only audit (exit code 3 if any project file changed);
- isolated candidate (Git worktree or copy) with ADD / MODIFY / RETIRE_CANDIDATE change sets, explicit approval by change id, stale-baseline refusal and post-apply verification;
- qualification stages including original regression against the candidate, coverage/oracle deltas, deliberate negative controls and pipeline-equivalent reproduction; unavailable stages are NOT_RUN/UNKNOWN, never PASS;
- native pytest evidence (invocations, parameters, markers, skip/xfail/xpass, collection errors, inherited materialization, coverage);
- Verification Surface from GitHub Actions and pre-commit with local-vs-CI parity findings;
- one Assurance Report model with baseline/candidate/applied states and "What does green prove?".

See [STATUS.md](STATUS.md) for the IMPLEMENTED / SPECIFIED / PLANNED split, [ROADMAP.md](ROADMAP.md), [Executable Assurance Core](docs/EXECUTABLE_ASSURANCE_CORE.md) and [Candidate Qualification and Test-the-Tests](docs/CANDIDATE_QUALIFICATION_AND_TEST_THE_TESTS.md).

Start with the [Documentation Portal](docs/README.md). Key owners include [Semantic UI and Browser Assurance](docs/SEMANTIC_UI_AND_BROWSER_ASSURANCE.md), [Determinism and Evidence Tiers](docs/DETERMINISM_AND_EVIDENCE_TIERS.md), [Refactor Safety](docs/REFACTOR_SAFETY.md), [Test Harness and Fidelity](docs/TEST_HARNESS_AND_FIDELITY.md), [Assertions/Oracles/Observation Surfaces](docs/ASSERTIONS_ORACLES_AND_OBSERVATION_SURFACES.md), and [Agent Skill/CLI/MCP Architecture](docs/AGENT_SKILL_MCP_ARCHITECTURE.md). See [STATUS.md](STATUS.md) and [ROADMAP.md](ROADMAP.md) for maturity.

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
