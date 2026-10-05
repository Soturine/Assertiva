# Status

## Current milestone: M0.2 — Executable Assurance Core

State: first executable TDD vertical slice is implemented; the core model is now explicitly language/framework/runner/CI-provider neutral, while concrete support expands through adapters.

### Implemented
- all M0/M0.1 semantic foundations: evidence tiers, test identity, coverage, harness/fidelity, assertions/oracles, fixtures/doubles, refactor safety and semantic UI/browser assurance;
- generic `VerificationCheck` / `VerificationSurface` model for tests, lint, type/static checks, build/package, schema/migration, security, localization, startup/health/deploy and arbitrary custom checks;
- generic adapter protocol: adapters discover/normalize capabilities and evidence without redefining assurance policy;
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
- dated research comparing TestSprite 2.1/current direction, Playwright Test Agents, Chisel, pytest/coverage.py and mutation tools;
- product UX contract reduced to two user-facing workflows: `audit` and `improve`;
- read-only audit / isolated-candidate / approval-gated application policy;
- HTML Assurance Report information architecture covering current/baseline/candidate/applied evidence, charts, findings, Evidence Delta and "What does green prove?";
- generic CandidateQualification model for baseline-vs-candidate evidence, qualification stages and approval-gated test changes;
- metric comparison that treats test count as contextual rather than automatically better;
- bounded static expected-error recognition and same-file inherited/composed pytest materialization analysis;
- user-facing technical-preview `assertiva audit` entry point with conservative UNKNOWN fallback for unrecognized ecosystems.

### Claim boundary
Python/pytest/GitHub Actions are the first executable reference adapters, **not the Assertiva architecture**. The core must not infer policy from a tool name, language, framework or CI provider.

The current pytest inventory is static AST inventory, not native pytest collection. It can miss plugins, cross-module inheritance, dynamic generation, runtime parameterization and collection-time behavior. The current GitHub Actions reader is a bounded command extractor, not a complete YAML/expression interpreter.

Assertiva must report these limitations rather than claiming universal discovery.

### Next
- implement stable `assertiva audit` over the generic Verification Surface;
- implement `assertiva improve` candidate generation/verification without touching the original project before approval;
- orchestrate test-the-tests qualification: original regression, mutation/negative controls, pipeline-equivalent checks, artifact/startup and optional preview deployment;
- implement the responsive accessible HTML Assurance Report after the visual reference is finalized;
- native pytest collection/result adapter;
- parameterized invocations, skip/xfail/markers/filters;
- package/source-tree parity and startup/migration/container checks;
- runtime/browser/database matrix comparison;
- Playwright/Jest/JUnit/.NET adapters;
- Azure Pipelines/GitLab CI/Jenkins adapters;
- mutation/negative-control orchestration;
- change impact, Test Evidence Graph construction and historical failure/flake intelligence.

See `docs/EXECUTABLE_ASSURANCE_CORE.md`, `docs/PIPELINE_AND_DELIVERY_ASSURANCE.md` and `ROADMAP.md`.
