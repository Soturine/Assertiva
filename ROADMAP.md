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

## M1 — Executable Assurance ✅
Audit and improve as a working, dogfooded vertical slice.

- [x] runtime-enforced read-only audit (tree fingerprint guard) with artifacts outside the project
- [x] isolated candidate workspace (Git worktree or copy) verified against the baseline
- [x] change set with ADD / MODIFY / RETIRE_CANDIDATE, fingerprints and diffs
- [x] explicit approval by change id, atomic stale-baseline refusal, post-apply verification
- [x] candidate qualification stages with honest NOT_RUN / UNKNOWN / BLOCKED
- [x] original regression against the candidate
- [x] deliberate negative controls on baseline and candidate
- [x] mutation report ingestion: mutation-testing-elements JSON (Stryker family), PIT XML, mutmut stats
- [x] direction-aware baseline vs candidate deltas without a composite score
- [x] native pytest collection/execution: ids, parameters, markers, filters, skip/xfail/xpass, collection errors, custom items, inherited materialization
- [x] coverage.py line/branch measurement in qualification
- [x] Verification Surface discovery from GitHub Actions and pre-commit; local-vs-CI parity findings
- [x] pipeline-equivalent reproduction with discovered / authorized / executed separation
- [x] built and installed wheel qualification (import origin, tests against the artifact)
- [x] negative-path depth: failure-contract dimensions + evidence-supported findings
- [x] bounded stability signal with first-failure preservation
- [x] JUnit XML portable result fallback (audit)
- [x] Assurance Report model + accessible self-contained HTML
- [x] execution trace with stage/command timing and timeout provenance
- [x] CI dogfood: installed wheel audits this repository, runs it natively and qualifies its own wheel (on demand / release tags)
- [x] fast feedback separated from full qualification: test markers, fast-suite cost guard, parallel per-commit CI, fixture-based installed-CLI invariant

Deferred out of M1 (tracked in STATUS as SPECIFIED): final visual design of the HTML report (waiting for the visual reference), sdist verification, Cosmic Ray, JUnit/mutation evidence as improve candidate state for non-native runners, order dependence.

## M2 — Scale & Cross-Stack Intelligence (active)
Make the proven model scale, generalize beyond Python and select evidence without fabricating confidence. Internal areas (not separate milestones): scale hardening, cross-stack adapters, impact and selection, history, delivery.

Scale and hardening
- [x] execution budget: bounded nested qualification depth, same-target recursion refusal, equivalent-evidence reuse, recorded reasons
- [x] filesystem/path boundaries (symlinks, junctions, escapes, nested repos, case collisions)
- [x] transactional approved apply with rollback
- [x] artifact fidelity vs dependency closure (offline declared-dependency closure; clean index install and sdist still NOT_RUN)
- [x] run-scoped runtime capability evidence and credential redaction in traces
- [x] CI reproducibility and Python 3.11 compatibility (current official actions, constrained installs, minimum-Python job)

Cross-stack
- [x] cross-stack core contract tests (fake runner/coverage/artifact adapters)
- [x] first JavaScript/TypeScript test adapter (Jest; Vitest not yet)
- [x] LCOV / Cobertura / JaCoCo coverage with numerators and denominators
- [x] Playwright semantic browser evidence (declared / selected / executed projects)
- [x] Java test evidence (JUnit Platform via Maven Surefire/Failsafe, JaCoCo; Gradle not yet)
- [ ] .NET / Go / Rust, only if the core is still simple after the above

Impact and selection
- [x] revision-scoped test impact graph with evidence tiers
- [x] test selection with conservative widening (never "no impact found = nothing to run")
- [ ] monorepo affected sets

History
- [ ] minimal revision-aware history store
- [ ] historical flake / order / duration intelligence
- [ ] deterministic failure fingerprinting and clustering

Delivery
- [ ] Azure Pipelines, GitLab CI, Jenkins verification discovery with matrix gaps (declared / selected / executed / deployed)
- [ ] tested vs published vs deployed artifact lineage
- [ ] shared-oracle concentration, redundancy and mock-away review candidates

Dogfood
- [ ] matched full-suite vs selected+widening experiments with known injected defects (miss rate first)

## M3 — Productization & Empirical Validation
- [ ] stable CLI contract and project policy/config
- [ ] optional MCP server and revision-aware local evidence store
- [ ] optional FTD import and FTE/Azure bridges
- [ ] benchmark corpora: CI-green/deploy-fail, inherited/composed tests, expected-error paths
- [ ] multi-stack qualification (Python, JS, Playwright, Django, Java, .NET, Android, monorepo)
- [ ] paired baseline vs Assertiva trials

Milestones may reopen when new evidence exposes reusable gaps.
