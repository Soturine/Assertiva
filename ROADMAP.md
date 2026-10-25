# Roadmap

Milestones were simplified on 2026-10-05. The former M0, M0.1 and the completed part of M0.2 are merged into **M0**; the former M1–M7 lists are regrouped into M1–M3 below. Earlier milestone history remains in `CHANGELOG.md` and Git history.

Development rule (since 0.7.3): evidence-driven, with validation proportional to risk. A bug or regression is reproduced before it is fixed when that is technically feasible; a new capability is delivered with tests of its contracts, in whatever order serves the work; a refactoring keeps existing behavior (characterization tests where none pins it) and tests the risks it introduces; research and exploration may start with spikes before contracts are formalized; Skill and agent behavior is judged by behavioral evals, adversarial cases, independent judging and confirmation sets; a trivial change gets no redundant tests and no costly checks without a demonstrable benefit. Targeted checks run first and widen with impact, uncertainty and criticality; a release still needs its complete applicable qualification. Existing tests, regression and security checks, compatibility, CI and release gates are kept; tests are never weakened to get green, snapshots or mocks never hide defects, and test count is never inflated. Core contracts stay tool-neutral; concrete behavior lives in adapters.

Until 0.7.2 the rule was strict TDD for every item ("reproduce the false-green or evidence gap first, then implement the smallest deterministic capability"); the M0–M3 items above were built under it.

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
- [x] first JavaScript/TypeScript test adapter (Jest; Vitest not yet at M2 close — *added in M3, 0.7.0*)
- [x] LCOV / Cobertura / JaCoCo coverage with numerators and denominators
- [x] Playwright semantic browser evidence (declared / selected / executed projects)
- [x] Java test evidence (JUnit Platform via Maven Surefire/Failsafe, JaCoCo; Gradle not yet at M2 close — *added in M3, 0.7.2*)
- .NET / Go / Rust, Vitest, Gradle: not required for M2 (Python, Jest, Playwright and Maven/Java proved the cross-stack core); not implemented in M2 — *Vitest and Gradle were added in M3; .NET, Go and Rust remain open*

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

## Versions (since 2026-10-19)

The roadmap is organized by versions with perceptible functional progress. The 0.7.3 stabilization was not published on its own: its work (security re-audit, evidence-integrity fixes, documentation, transfer evaluation, benchmark sets, research wave 1) is the first part of 0.8.0, on branch `release/0.8.0` (the branch `release/0.7.3` keeps its history unchanged). The milestones M1–M10 below are kept for history and mapped onto versions.

- **0.7.2 — published (2026-10-09).**
- **0.8.0 — Intelligence & Proof of Protection** (implemented and qualified on `release/0.8.0`; no independent release, included in 0.9.0; see CHANGELOG): the former 0.7.3 fixes; evidence integrity for mutation reports that cannot be tied to the analyzed state; deeper oracle and mock analysis; a first executable integration with a mature native mutation tool (orchestrated in disposable copies, not reimplemented); `improve` showing the protection a strengthened test adds (what survived on the baseline and is detected by the candidate, and by which test); one reproducible end-to-end flow — audit, a gap found, a test improved, the gain proven; agent-led practices from research wave 1. Covers M1 (done), parts of M2, M3b and M4.
- **0.8.1 — Advanced Mutation & Improve:** folded into 0.9.0 (owner decision, 2026-10-19), not published on its own.
- **0.9.0 — Advanced Test Intelligence & Continuous Assurance — delivered 2026-10-20** (`v0.9.0`; qualified at `0cac223` and requalified at `32ce4d8` after the pre-publication fixes, see CHANGELOG). Includes the work of 0.7.3, 0.8.0 and 0.8.1. Scope: evidence-integrity and security fixes (CP1); executed mutation testing across stacks chosen by capability (Cosmic Ray under the declared Python runner, StrykerJS for Jest/Vitest, PIT for Maven) with per-test contribution from complete killer matrices (CP2); contract-driven test improvement (M2/M3b, CP3); selection and risk (M5) and failure intelligence (M6) (CP4); contracts, E2E fidelity, accessibility and portable results (M7, CP5); integration, demos and docs (CP6); full qualification (CP7).
  - **Complete (implemented and qualified):** the link-escape and evidence-binding fixes; engine-run mutation testing chosen by capability for Python (Cosmic Ray; pytest, unittest, Django), JavaScript/TypeScript (StrykerJS; Jest) and Java (PIT; Maven); per-test contribution and survivor sites; JS/TS and JVM false-green rules; oracle basis; the fidelity ladder; failure origin, novelty, clusters and the order probe; selection with cosmetic, dependency and declared changes and a history order; CTRF/Allure import and CTRF export; Pact; axe-core.
  - **Partial:** StrykerJS was run with Jest only (Vitest is recognized, not run); PIT through Gradle (its report can be imported) and Allure export are not implemented; the Pact Broker is not queried; ignored side effects are detected only for UI actions; witnesses are prepared (original line and change), not computed; test identity across renames, reproduction seeds and the search for the polluting test are not done; the fidelity ladder is read from code.
  - **Planned for 1.0:** ecosystem coverage (M8), including executed mutation testing for C#, Rust, PHP and Go; the competitive qualification lab (M9); release qualification (M10); the semantic evaluation rounds of the Skill with agents (never run for 0.9.0); a stable CLI and report contract.
  - Backlog (important, not blocking): outside a Git checkout a copy holds every entry of the project, installed dependencies included (`node_modules`, virtual environments), which is slow and can exceed Windows path limits; an orchestrated mutation run then ends with an explained error instead of a result. Reuse the installed-dependency linking used for Git projects.
  - Backlog (CP3, partial): ignored side effects are detected only for UI actions (`ACTION_WITHOUT_CHECK`); a Python or JVM call whose effect no assertion observes needs a calibrated rule (a first lexical attempt would flag cleanup calls). Witnesses are prepared (original line and change), not computed.
  - Backlog (CP4, partial): reproduction seeds (pytest-randomly, Jest `--seed`, Hypothesis) are not captured yet; stable test identity across renames is not tracked (history follows invocation ids); the order probe does not search for the polluting test; Gradle/Maven modules are not components yet.
  - Backlog (CP5, partial): Allure is imported, not exported (CTRF is); the Pact Broker (pending/WIP status, can-i-deploy) is not queried; accessibility reads axe-core only (Lighthouse, pa11y and similar on demand); the fidelity ladder reads code and is not reconciled with what a run reached.
  - Evaluated, not integrated in 0.9.0: **mutmut** (3.8.0, run on Linux on `tests/fixtures/protection-demo`, 2026-10-19). It runs only with pytest and only on POSIX, writes a `mutants/` tree into the project, and keeps per-mutant results as exit codes in an internal `.meta` file without detecting tests (6 mutants where Cosmic Ray plans 24 on the same file). For pytest projects it adds no evidence Cosmic Ray does not give; its CI stats stay importable. Reconsider on demand.
- **1.0.0 — competitive maturity:** ecosystem coverage (M8), including executed mutation testing for C# (Stryker.NET), Rust (cargo-mutants), PHP (Infection) and Go (a mutator chosen after evaluation), PIT through Gradle and other tools on demand, each an adapter module with real positive and negative tests; the competitive qualification lab with executed comparisons (M9), release qualification (M10), a stable CLI and report contract. Multi-agent work — semantic evaluation rounds of the Skill with separate agents and judges, and multi-agent research — is planned here (owner decision, 2026-10-19): until then, Skill changes ship with deterministic tests of the engine they rely on and are recorded as not semantically evaluated.

## Gap policy (since 2026-10-19)

A new finding is classified by criticality, impact, reproducibility and relation to the version in progress; it does not reopen completed scope or open a maintenance release by itself.
- **Blocking:** a reproduced security problem, evidence-integrity defect or proven loss of protection blocks publishing the affected functionality until fixed.
- **Important, not blocking:** goes to the backlog of the milestone it belongs to and is fixed there.
- **Optional:** improvements without demonstrated benefit, refactors for their own sake and speculative gaps never block progress.
- Never turn UNKNOWN into PASS, and never ignore a critical risk, to make a release.

A version is ready when its committed functionality is implemented and integrated, its acceptance criteria pass, no known critical defect invalidates what it claims, regression and applicable security checks are qualified, reports keep the proven apart from the unknown, non-blocking limitations are documented, benchmarks and evals claim no more than their evidence, and commits are organized by stage. Absence of all gaps is not required. Targeted checks run during development and widen with impact; the full qualification (suites on Windows and Linux, benchmarks, evals with an agreed budget) runs at the release milestone, and publishing waits for the owner's authorization.

## Milestones M1–M10 (2026-10-09 plan, kept for history; mapped to versions above)
Each milestone is its own checkpoint with acceptance criteria, positive and negative tests, evals where agent judgment is involved, documentation and its own commit. 0.7.2 is the baseline. Nothing here is claimed until it is implemented and qualified; comparisons with other tools are reported as executed (same revision, environment, budget and scope) or as documentary, never mixed, and no superiority is claimed without matching evidence.
- **M1 — Competitive capability audit:** done as research wave 1 (`research/2026-10-19-competitive/`).
- **M2 — Advanced test intelligence:** deeper oracle analysis (self-referential oracles, unobserved side effects, mocks that hide defects), targeted pseudo-mutation as an explicit hypothesis distinct from executed mutation, distinct contribution beyond textual similarity.
- **M3b — Intelligent test improvement:** contract-driven creation and strengthening of tests in improve (partitions, limits, invariants, right level, project style), each change compiled, run and challenged by negative controls or mutants; no reward for test count; production code untouched without specific authorization.
- **M4 — Mutation integration:** orchestration of native mutation tools per ecosystem with cost controls (targeted, incremental); executed vs detected vs survived vs no-coverage vs equivalent/inconclusive vs blocked, with tool, version, configuration, revision and killing tests.
- **M5 — Smart selection and risk:** conservative impact selection from changes, static and observed dependencies, history, cost and uncertainty; retrospective simulation of what a selection would have missed; never a safety claim from running fewer tests; release and CI gates preserved.
- **M6 — Failure intelligence:** history by stable test identity, retries that keep the first failure, seeds/order/environment, failure clustering, new vs recurring, product vs test vs infrastructure, order-dependence analysis, targeted reproduction.
- **M7 — Contracts, API, UI, E2E, accessibility:** use Playwright, Pact and axe-core results when present; distinguish mocks, simulators, disposable real services, real browsers, emulators and devices; no full-accessibility claim from an absence of automated violations.
- **M8 — Ecosystem coverage:** executable adapters for .NET, Go, Rust, PHP and Ruby, each with real-run qualification; capability classes EXECUTABLE, REPORT_INGESTION, STATIC_ANALYSIS, AGENT_ASSESSMENT, BLOCKED, UNSUPPORTED shown in the report; no empty adapters.
- **M9 — Competitive qualification:** a permanent lab on synthetic fixtures and suitably licensed public repositories, with known cases and separate confirmation cases (against overfitting); precision/recall of findings, false greens found, mutation sensitivity, consolidation safety, selection misses, cost; agent-led evals and polyglot dogfood.
- **M10 — Release qualification:** security, documentation, compatibility, performance, CI and publication criteria.

## Dogfood follow-up — Soturine/tcc, 2026-10-25 (planned, not shipped)

The [TCC multi-stack audit](research/2026-10-25-tcc-multistack-dogfood.md) of Assertiva 0.9.0 found two material heuristic false positives (CI working-directory and successful validation/no-throw oracle), partial/uncounted test roots, unsupported native Node `--test`/PlatformIO, and independently discovered fidelity/UI/LittleFS gaps. **No implementation, new adapter or passed evaluation is claimed here.** [Prioritized 15-item backlog and gates](research/2026-10-25-tcc-improvement-backlog.md).

Near-term quality gates: **A01** per-step GitHub Actions working-directory to eliminate false HIGH; **A02** different denominators for static/native/executed and multi-root scope; **A05** no-throw oracle calibrated against validation contract; **A08** provenance/claims. Medium-term capability work: **A03/A04** Node built-in test runner and PlatformIO/Unity native execution; **A06** mocked integration fidelity; **A07/A13** custom infrastructure and real-HIL boundary. Later: JS E2E tautologies, manual mutation provenance, test redundancy, UI and semantic agent evals. Do not roll these requirements into the historical 0.9.0 release or adjust frozen benchmark thresholds to hide misses. Evaluate on independent holdouts as well as TCC fixtures. The [TCC dogfood eval](evals/cases/TCC_MULTISTACK_DOGFOOD_CLAIM_BOUNDARIES.md) is grader-ready **only**, not an executed test.
