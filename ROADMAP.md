# Roadmap

Milestones were simplified on 2026-10-05. The former M0, M0.1 and the completed part of M0.2 are merged into **M0**; the former M1–M7 lists are regrouped into M1–M3 below. Earlier milestone history remains in `CHANGELOG.md` and Git history.

TDD rule for every item: reproduce the false-green or evidence gap first, then implement the smallest deterministic capability. Core contracts stay tool-neutral; concrete behavior lives in adapters.

## M0 — Foundation and contracts ✅
- [x] provider-neutral SKILL.md, quality model, diagnostics D0–D4, Test Evidence Graph semantics
- [x] evidence tiers E0–E4, definition → materialization → invocation → attempt identity
- [x] multi-metric coverage, parameterized/property/fuzz and structured error semantics
- [x] harness/fidelity, assertions/oracles, fixtures/doubles, web/API/UI and semantic UI/browser models
- [x] refactor readiness model
- [x] two-command UX contract, write-boundary policy, candidate qualification and report architecture
- [x] generic VerificationCheck / VerificationSurface and adapter capability contract
- [x] schemas, examples, eval catalog, JUnit summarizer, repository validator
- [x] first static pytest inventory, bounded CI scope gaps, coverage.py JSON, smoke/weak-oracle findings

## M1 — Executable Assurance (active)
Audit and improve as a working vertical slice.

- [x] runtime-enforced read-only audit (tree fingerprint guard) with artifacts outside the project
- [x] isolated candidate workspace (Git worktree or copy) verified against the baseline
- [x] change set with ADD / MODIFY / RETIRE_CANDIDATE, fingerprints and diffs
- [x] explicit approval by change id, atomic stale-baseline refusal, post-apply verification
- [x] candidate qualification stages with honest NOT_RUN / UNKNOWN / BLOCKED
- [x] original regression against the candidate
- [x] deliberate negative controls on baseline and candidate
- [x] direction-aware baseline vs candidate deltas without a composite score
- [x] native pytest collection/execution: ids, parameters, markers, filters, skip/xfail/xpass, collection errors, custom items, inherited materialization
- [x] coverage.py line/branch measurement in qualification
- [x] Verification Surface discovery from GitHub Actions and pre-commit; local-vs-CI parity findings
- [x] pipeline-equivalent reproduction of adapter-understood delivery checks
- [x] Assurance Report model + accessible self-contained HTML
- [x] CI dogfood: installed wheel audits this repository with native execution
- [ ] mutation report ingestion (Stryker mutation-testing-elements JSON, PIT XML, mutmut / Cosmic Ray)
- [ ] build/package/installed-artifact stage (source tree vs wheel/sdist parity)
- [ ] startup/health/migration/container stage via declared project commands
- [ ] rerun-based stability signal (first failure preserved)
- [ ] expected-error depth: structured error fields and state after rejection
- [ ] JUnit XML / portable report ingestion as a generic runner fallback
- [ ] final visual design of the HTML report (after the visual reference is provided)

## M2 — Cross-stack Intelligence
- [ ] runner adapters: Jest/Vitest, Playwright (+ semantic locator/accessibility evidence), JUnit/Gradle/Maven, .NET, Go/Rust
- [ ] CI adapters: Azure Pipelines, GitLab CI, Jenkins / generic command graph
- [ ] LCOV/Cobertura/JaCoCo coverage ingestion
- [ ] runtime/OS/browser/database matrix gaps; tested vs deployed artifact lineage
- [ ] change impact: diff + symbols, dependency and composition/lifecycle graph, conservative widening, monorepo affected set
- [ ] history: flake, duration/cost, failure fingerprinting and clustering, E2E stage mapping
- [ ] shared-oracle concentration, redundancy, mock-away and snapshot provenance analysis
- [ ] authorized remote CI execution and non-production preview deployment as adapter capabilities

## M3 — Productization & Empirical Validation
- [ ] stable CLI contract and project policy/config
- [ ] optional MCP server and revision-aware local evidence store
- [ ] optional FTD import and FTE/Azure bridges
- [ ] benchmark corpora: CI-green/deploy-fail, inherited/composed tests, expected-error paths
- [ ] multi-stack qualification (Python, JS, Playwright, Django, Java, .NET, Android, monorepo)
- [ ] paired baseline vs Assertiva trials

Milestones may reopen when new evidence exposes reusable gaps.
