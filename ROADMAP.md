# Roadmap

## M0 — Skill foundation ✅
- [x] provider-neutral SKILL.md
- [x] quality model and adaptive execution protocol
- [x] diagnostics D0–D4 and E2E decomposition
- [x] Test Evidence Graph semantics
- [x] schemas/examples/evals/research
- [x] JUnit summarizer + validator + CI

## M0.1 — Deterministic semantic foundation ✅
- [x] evidence tiers E0–E4
- [x] definition vs invocation identity
- [x] multi-metric coverage
- [x] parameterized/property/fuzz/error semantics
- [x] capability-driven adapter contract
- [x] refactor readiness
- [x] harness/fidelity, assertions/oracles, fixtures/doubles
- [x] web/API/UI/browser evidence
- [x] semantic UI/browser assurance
- [x] Skill + CLI + optional MCP architecture benchmark

## M0.2 — Executable assurance core (active)
TDD first: reproduce the false-green/evidence gap, then implement the smallest deterministic capability. Core contracts remain tool-neutral; concrete behavior lives in adapters.

- [x] generic VerificationCheck / VerificationSurface model
- [x] generic adapter protocol with SUPPORTED / UNSUPPORTED / UNKNOWN capability semantics
- [x] Python package + technical-preview CLI
- [x] static pytest definition inventory
- [x] bounded GitHub Actions pytest command/scope discovery
- [x] CI execution-gap detection
- [x] coverage.py JSON line/branch ingestion
- [x] smoke-dominant / weak-oracle signals
- [x] high-line-coverage / weak-oracle contradiction
- [x] line-vs-branch divergence
- [x] wheel build + installed-artifact smoke in Assertiva CI
- [ ] native `pytest --collect-only` adapter
- [ ] collection errors, skip, xfail, markers and filters
- [ ] parameterized/dynamic invocation preservation
- [ ] source-tree vs wheel/sdist parity
- [ ] migration/startup/health/container verification
- [ ] local-vs-CI runtime/environment matrix
- [ ] adversarial CI-green/deploy-fail fixture corpus

## M1 — Deterministic runner adapters
- [ ] pytest execution/result adapter
- [ ] Jest/Vitest
- [ ] Playwright + semantic locator/accessibility evidence
- [ ] JUnit/Gradle/Maven
- [ ] .NET
- [ ] LCOV/Cobertura/JaCoCo coverage ingestion
- [ ] property/fuzz replay evidence
- [ ] secret/redaction tests

## M2 — CI/CD and delivery evidence
- [ ] generic local/hook/CI/deploy verification-surface discovery
- [ ] generic custom-command preservation when no first-party adapter exists
- [ ] richer GitHub Actions semantic workflow model
- [ ] Azure Pipelines
- [ ] GitLab CI
- [ ] Jenkins/generic command graph
- [ ] build/package artifact identity
- [ ] Docker/container build + startup
- [ ] migration/assets/startup checks
- [ ] preview/staging/deploy health evidence
- [ ] runtime/OS/browser/database/service matrix gaps
- [ ] tested-artifact vs deployed-artifact lineage

## M3 — Impact intelligence
- [ ] Git diff + symbol extraction
- [ ] import/dependency graph
- [ ] runtime test-to-code evidence
- [ ] conservative widening
- [ ] monorepo affected-set
- [ ] automatic Test Evidence Graph
- [ ] Chisel-style incremental graph/history ideas without treating opaque risk scores as proof

## M4 — Suite quality intelligence
- [ ] stronger deterministic weak/no-op patterns
- [ ] provenance-labeled semantic weak-assertion analysis
- [ ] mock-away heuristics
- [ ] duplicate/redundancy analysis
- [ ] mutation adapters (mutmut/Stryker/PIT-style)
- [ ] negative-control challenge harness
- [ ] snapshot provenance
- [ ] retry/timeout/first-failure analysis
- [ ] defect-to-test history

## M5 — Failure intelligence + governed verification
- [ ] failure fingerprinting/clustering
- [ ] E2E stage mapping and smallest reproducer
- [ ] flake/history and duration/cost
- [ ] progressive diagnostic automation
- [ ] safe healing: execution mechanics may change; oracle does not silently change
- [ ] reproduce → fix/heal → affected regression → broader required gate

## M6 — Productization
- [ ] stable CLI
- [ ] optional MCP server
- [ ] revision-aware local evidence store
- [ ] CI provider integrations
- [ ] project policy/config
- [ ] optional FTD import bridge
- [ ] optional FTE/Azure bridge

## M7 — Empirical validation
- [ ] Python/pytest
- [ ] JS/Jest/Vitest
- [ ] Playwright
- [ ] Django
- [ ] Java/JUnit
- [ ] .NET
- [ ] Android/Gradle/JUnit
- [ ] monorepo
- [ ] CI-green/deploy-fail corpus
- [ ] paired baseline vs Assertiva trials

Milestones may reopen when new evidence exposes reusable gaps.
