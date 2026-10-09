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
- [x] candidate qualification (five pillars with internal checks) with honest NOT_RUN / UNKNOWN / BLOCKED
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
- [x] runtime self-qualification: installed wheel audits this repository, runs it natively and qualifies its own wheel (on demand / release tags)
- [x] fast feedback separated from full qualification: test markers, slow-test reporting in the fast suite, parallel per-commit CI, fixture-based installed-CLI invariant

Deferred out of M1 (tracked in STATUS as SPECIFIED): final visual design of the HTML report (waiting for the visual reference), sdist verification, Cosmic Ray, JUnit/mutation evidence as improve candidate state for non-native runners, order dependence.

## M2 — Scale & Cross-Stack Intelligence (done, 2026-10-06)
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
- .NET / Go / Rust, Vitest, Gradle: not required for M2 (Python, Jest, Playwright and Maven/Java proved the cross-stack core); not implemented

Impact and selection
- [x] revision-scoped test impact graph with evidence tiers
- [x] test selection with conservative widening (never "no impact found = nothing to run")
- [x] monorepo affected sets (npm workspaces, Python subprojects)

History
- [x] minimal revision-aware history store (local SQLite, schema-versioned, optional)
- [x] historical flake / duration intelligence (order dependence: not measured)
- [x] deterministic failure fingerprinting and conservative grouping

Delivery
- [x] Azure Pipelines, GitLab CI, Jenkins verification discovery with matrix gaps (declared / selected / executed / deployed; execution stays UNKNOWN without run evidence)
- [x] tested vs published vs deployed artifact lineage (as far as evidence goes)
- [x] shared-oracle concentration, redundancy and mock-away review candidates (review only, never gates)

Dogfood
- [x] matched full-suite vs selected+widening experiments with known injected defects (miss rate first): `tests/test_selection_experiment.py`, 0 misses in 12 controlled defects

## Agent-led architecture (0.6.0, between M2 and M3)
Found by dogfooding: a static-first Skill stopped at static evidence, sampled candidates and generalized, and handed back evidence it could acquire, while the report contradicted its own conclusions.
- [x] Skill rewritten around the auditor: question-first investigation, free tool choice, completion adequacy, provenance separate from importance; three references by progressive disclosure
- [x] auditing agent's assessment attached to the run (`audit --assessment`): dispositions of engine findings, agent findings, conclusion; the report renders them beside raw engine evidence
- [x] EXECUTION pillar as one check (former discovery and candidate-test checks merged with equivalent protection)
- [x] eight hidden-rubric eval cases for agent-led behavior, two on executable fixtures

## M3 — Productization & Empirical Validation (in progress)
Started with what the 0.6.0 dogfood exposed (evidence integrity, execution safety) and the Python runners real projects use.
- [x] evidence integrity: a run's own exit status, process-tree timeouts, signals, output digests; `--run-check` execution records with per-dimension CI parity
- [x] execution safety: credential-looking variables withheld; checks with effects outside the copy need the user's consent (`<ASSERTIVA_HOME>/consent.toml`, never the project's files); connection targets withheld; publishing build goals never run
- [x] native unittest and Django (`manage.py test`) adapters; the declared runner decides
- [x] Vitest adapter (3+, TypeScript and projects), sharing the Jest results normalization
- [x] Gradle adapter (0.7.2): Java, Kotlin/JVM, Android local tests, KMP JVM targets; catalogs, convention plugins, task confirmation by Gradle; qualified on Windows and Linux CI
- [x] consented provisioning (0.7.2): virtual environments, npm, JDK, Gradle, disposable PostgreSQL; interpreter downloads not done
- [x] cross-language test effectiveness (0.7.2): one model, per-language extractors, candidates for the agent
- [x] project configuration, minimal and optional (`.assertiva.toml`: runners, timeout; consent stays with the user)
- [x] report header names language, frameworks and stack with how each is known
- [ ] stable CLI contract
- [ ] optional MCP server and revision-aware local evidence store
- [ ] optional FTD import and FTE/Azure bridges
- [ ] benchmark corpora: CI-green/deploy-fail, inherited/composed tests, expected-error paths
- [ ] multi-stack qualification (Python, JS, Playwright, Django, Java, .NET, Android, monorepo) — unittest, Django, Vitest, Gradle/Kotlin/Android local done; .NET, Go, Rust, PHP open
- [ ] paired baseline vs Assertiva trials

Milestones may reopen when new evidence exposes reusable gaps.

## After 0.7.2 — evidence-backed capability growth (planned)
Each milestone is its own checkpoint with acceptance criteria, positive and negative tests, evals where agent judgment is involved, documentation and its own commit. 0.7.2 is the baseline. Nothing here is claimed until it is implemented and qualified; comparisons with other tools are reported as executed (same revision, environment, budget and scope) or as documentary, never mixed, and no superiority is claimed without matching evidence.
- **M1 — Competitive capability audit:** research test-quality auditors and agent skills, test-smell detectors, mutation tools (Stryker, PIT, mutmut, Cosmic Ray, cargo-mutants and others), test generators, test-selection and flaky-test tooling, result analysis (ReportPortal, Allure), and integration/E2E tools (Playwright, Cypress, Pact, Testcontainers, axe-core). Output: a dated technical comparison that separates demonstrated capability from claims, with licenses, maintenance and fit, plus the shared contracts to extend (no parallel models).
- **M2 — Advanced test intelligence:** deeper oracle analysis (self-referential oracles, unobserved side effects, mocks that hide defects), targeted pseudo-mutation as an explicit hypothesis distinct from executed mutation, distinct contribution beyond textual similarity.
- **M3b — Intelligent test improvement:** contract-driven creation and strengthening of tests in improve (partitions, limits, invariants, right level, project style), each change compiled, run and challenged by negative controls or mutants; no reward for test count; production code untouched without specific authorization.
- **M4 — Mutation integration:** orchestration of native mutation tools per ecosystem with cost controls (targeted, incremental); executed vs detected vs survived vs no-coverage vs equivalent/inconclusive vs blocked, with tool, version, configuration, revision and killing tests.
- **M5 — Smart selection and risk:** conservative impact selection from changes, static and observed dependencies, history, cost and uncertainty; retrospective simulation of what a selection would have missed; never a safety claim from running fewer tests; release and CI gates preserved.
- **M6 — Failure intelligence:** history by stable test identity, retries that keep the first failure, seeds/order/environment, failure clustering, new vs recurring, product vs test vs infrastructure, order-dependence analysis, targeted reproduction.
- **M7 — Contracts, API, UI, E2E, accessibility:** use Playwright, Pact and axe-core results when present; distinguish mocks, simulators, disposable real services, real browsers, emulators and devices; no full-accessibility claim from an absence of automated violations.
- **M8 — Ecosystem coverage:** executable adapters for .NET, Go, Rust, PHP and Ruby, each with real-run qualification; capability classes EXECUTABLE, REPORT_INGESTION, STATIC_ANALYSIS, AGENT_ASSESSMENT, BLOCKED, UNSUPPORTED shown in the report; no empty adapters.
- **M9 — Competitive qualification:** a permanent lab on synthetic fixtures and suitably licensed public repositories, with known cases and separate confirmation cases (against overfitting); precision/recall of findings, false greens found, mutation sensitivity, consolidation safety, selection misses, cost; agent-led evals and polyglot dogfood.
- **M10 — Release qualification:** security, documentation, compatibility, performance, CI and publication criteria.
