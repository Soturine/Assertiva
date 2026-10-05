# Changelog

## [0.3.0] — 2026-10-05

### Added
- Runtime-enforced read-only `assertiva audit`: tree fingerprint guard, `--execute` runs tests only in a disposable copy, reports outside the project.
- `assertiva improve` as one command: isolated candidate (Git worktree or copy), qualification, explicit `--approve <change ids>`, stale-baseline refusal, post-apply verification, `--discard`.
- Candidate qualification stages with original regression against the candidate, coverage/oracle deltas, deliberate negative controls, pipeline-equivalent reproduction; unavailable stages are NOT_RUN/UNKNOWN.
- Native pytest adapter: invocation/parameter ids, markers, filters, skip/xfail/xpass, collection errors, custom items, inherited materialization, coverage.
- Verification Surface discovery from GitHub Actions and pre-commit with local-vs-CI parity findings.
- Assurance Report model and accessible self-contained HTML renderer.
- CI dogfood: the installed wheel audits this repository with native execution and fails if the tree changed.

### Changed
- Milestones simplified to M0 (done), M1 Executable Assurance, M2 Cross-stack Intelligence, M3 Productization & Empirical Validation.
- GitHub Actions parsing now uses PyYAML (new runtime dependency).
- The hidden `audit-pytest` alias was removed; use `assertiva audit`.

## Earlier

### Added
- Candidate qualification / test-the-tests contract: immutable baseline, isolated candidate, original regression, mutation/negative controls, pipeline-equivalent verification, optional authorized preview deployment, and evidence-delta comparison.
- Generic candidate models and tests for approval-gated ADD/MODIFY/RETIRE_CANDIDATE changes and metric-direction-aware comparisons.
- Top-level `assertiva audit` technical-preview command with UNKNOWN fallback instead of reporting unsupported ecosystems as zero-test projects.
- Static expected-error recognition and same-file inherited/composed pytest materialization evidence.
- Two-command UX contract: `assertiva audit` for read-only assurance and `assertiva improve` for isolated candidate improvements with approval before project writes.
- Runtime write-boundary policy, stale-source protection, and candidate-vs-applied evidence semantics.
- HTML Assurance Report design contract with responsive accessible charts, baseline/candidate/applied comparisons, Evidence Delta, Verification Surface, findings and bounded green-claim reporting.
- Generic Verification Surface core: language/framework/runner/CI-provider-neutral check model and adapter contract covering tests plus lint/type/build/package/schema/migration/localization/security/hooks/startup/health/deploy/custom verification.
- Explicit no-hardcode boundary: tool-specific knowledge belongs in adapters; unsupported tooling is preserved as UNKNOWN/CUSTOM evidence instead of being guessed or ignored.
- M0.2 executable assurance core: TDD-built pytest inventory, bounded GitHub Actions pytest-scope analysis, coverage.py JSON ingestion, false-green findings, technical-preview CLI, and wheel/install smoke in CI.
- Pipeline/delivery assurance scope: repository tests vs actually selected CI tests, artifact/environment parity, and explicit green-claim boundaries.
- FTD/FTE clarified as optional integrations rather than prerequisites.
- Dated benchmark research covering TestSprite 2.1/current CLI direction, Playwright Test Agents, Chisel, pytest/coverage.py and mutation tooling.
- Semantic UI/browser documentation closure: canonical owner, documentation portal, cross-platform semantic mapping, normalized locator-evidence schema/example, enriched assertion observations, grader-ready eval contract/cases, deeper Derivanta interoperability, dated ecosystem research, and validator enforcement.
- Semantic UI/browser test assurance: product-contract locator guidance, accessibility-tree/role/name/state observations, keyboard/focus evidence, selector robustness under non-behavioral refactors, snapshot update provenance, automated accessibility-scan claim boundaries, and retry/timeout first-failure discipline.
- Harness/Fidelity model separating test labels from actual process, transport, persistence, transaction, dependency, UI and isolation boundaries.
- Assertion/Oracle/Observation Surface model covering protocol, context/content, persistence, events, DOM/accessibility, visual, telemetry, performance and security evidence.
- Fixture/factory/test-data lifecycle and test-double/patch/service-virtualization guidance.
- Web/API/UI/browser evidence model and platform-matrix identity.
- Agent Skill + CLI + optional MCP architecture benchmark informed by Chisel, dotnet/TestFX skills, Cypress AI Toolkit, Android Skills, Playwright and Anthropic skill/MCP patterns.
- Deterministic-first cross-framework foundation: evidence tiers, capability-driven adapters, definition-vs-invocation identity, multi-metric coverage, parameterized/property/fuzz semantics, structured error contracts and explicit heuristic/LLM advisory boundaries.
- Refactor Confidence model with readiness gates, whole-project behavior protection inventory and test-the-safety-net checks.
- initial Assertiva Agent Skill and architecture;
- AUDIT / SELECT / RUN / DIAGNOSE / VERIFY model;
- Test Evidence Graph semantics;
- progressive diagnostics D0–D4;
- failure-guided E2E decomposition;
- token-aware evidence contract;
- refactor-safety guidance;
- framework, mutation, and test-smell references;
- dated ecosystem benchmark;
- structured schemas and example records.
