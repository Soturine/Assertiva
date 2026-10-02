# Status

## Current milestone: M0.2 — Executable Assurance Core

State: first executable TDD vertical slice is implemented; broader cross-runner assurance remains incremental.

### Implemented
- all M0/M0.1 semantic foundations: evidence tiers, test identity, coverage, harness/fidelity, assertions/oracles, fixtures/doubles, refactor safety and semantic UI/browser assurance;
- executable Python package `assertiva` and technical-preview CLI;
- bounded static pytest definition inventory;
- bounded GitHub Actions pytest command/scope discovery;
- repository-tests-vs-observed-CI scope comparison;
- coverage.py JSON line/branch ingestion;
- first deterministic findings:
  - `CI_PYTEST_NOT_OBSERVED`;
  - `CI_TEST_EXECUTION_GAP`;
  - `SUITE_SMOKE_DOMINANT`;
  - `WEAK_ORACLE_SIGNAL`;
  - `LINE_BRANCH_COVERAGE_DIVERGENCE`;
  - `HIGH_COVERAGE_WEAK_ORACLE`;
- TDD tests for discovery, CI-scope gaps, smoke-dominant suites and coverage/oracle contradictions;
- Assertiva CI now builds a wheel and smoke-runs the installed CLI from outside the source tree;
- dated research comparing TestSprite 2.1/current direction, Playwright Test Agents, Chisel, pytest/coverage.py and mutation tools.

### Claim boundary
The current pytest inventory is static AST inventory, not native pytest collection. It can miss plugins, dynamic generation, runtime parameterization and collection-time behavior. The current GitHub Actions reader is a bounded command extractor, not a complete YAML/expression interpreter.

Assertiva must report these limitations rather than claiming universal discovery.

### Next
- native pytest collection/result adapter;
- parameterized invocations, skip/xfail/markers/filters;
- package/source-tree parity and startup/migration/container checks;
- runtime/browser/database matrix comparison;
- Playwright/Jest/JUnit/.NET adapters;
- Azure Pipelines/GitLab CI/Jenkins adapters;
- mutation/negative-control orchestration;
- change impact, Test Evidence Graph construction and historical failure/flake intelligence.

See `docs/EXECUTABLE_ASSURANCE_CORE.md`, `docs/PIPELINE_AND_DELIVERY_ASSURANCE.md` and `ROADMAP.md`.
