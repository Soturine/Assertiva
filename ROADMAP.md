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
- [x] declaration -> materialization -> invocation -> attempt identity model
- [x] expected-error / validation contract model
- [x] two-command product UX contract: audit / improve
- [x] read-only audit and isolated candidate write policy
- [x] HTML Assurance Report information architecture and evidence-delta model
- [x] generic CandidateQualification / CandidateTestChange model
- [x] metric-direction-aware baseline vs candidate comparison without a magic score
- [x] original-test preservation / approval-gated retirement policy
- [x] top-level technical-preview `assertiva audit` command with conservative UNKNOWN fallback
- [ ] native pytest collection/result adapter
- [ ] inherited/composed test materialization from native runner evidence
- [ ] collection errors, skip, xfail, markers, assumptions and filters
- [ ] parameterized/dynamic invocation preservation
- [ ] expected-exception / rejection / warning adapter normalization
- [ ] error status versus structured error/state-effect analysis
- [ ] async rejection/error observation
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
- [ ] runner-native inheritance/composition/parameterization mapping
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
- [ ] composition/inheritance/lifecycle dependency graph
- [ ] runtime test-to-code evidence
- [ ] conservative widening
- [ ] monorepo affected-set
- [ ] automatic Test Evidence Graph
- [ ] Chisel-style incremental graph/history ideas without treating opaque risk scores as proof

## M4 — Suite quality intelligence
- [ ] stronger deterministic weak/no-op patterns
- [ ] expected-error strength and validation-depth analysis
- [ ] rollback/no-side-effect evidence for negative paths
- [ ] provenance-labeled semantic weak-assertion analysis
- [ ] shared oracle concentration across inherited/composed tests
- [ ] mock-away heuristics
- [ ] duplicate/redundancy analysis
- [ ] mutation adapters
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
- [ ] stable `assertiva audit` command
- [ ] stable `assertiva improve` command
- [ ] runtime-enforced read-only audit policy
- [ ] isolated candidate workspace + stale-source protection
- [ ] candidate qualification orchestrator (test-the-tests)
- [ ] run unchanged original regression against candidate
- [ ] mutation/negative-control qualification adapters
- [ ] pipeline-equivalent candidate verification
- [ ] optional authorized remote CI execution
- [ ] optional ephemeral/preview deployment qualification
- [ ] approval-gated patch application
- [ ] responsive accessible HTML Assurance Report
- [ ] baseline/candidate/applied report comparison
- [ ] charts + textual/table equivalents
- [ ] report filters, expandable findings and raw artifact links
- [ ] Evidence Delta and "What does green prove?" sections
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
- [ ] inherited/composed test benchmark
- [ ] expected-error and validation-path benchmark
- [ ] CI-green/deploy-fail corpus
- [ ] paired baseline vs Assertiva trials

Milestones may reopen when new evidence exposes reusable gaps.
