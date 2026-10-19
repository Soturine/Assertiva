# Competitive research, wave 1 (2026-10-19)

What tools close to Assertiva do better, how they do it in their code, what their inputs and outputs are, and what
Assertiva should integrate, adapt, build or reject — with the change and the proof each decision needs. This page
consolidates six cluster reports; each cluster report holds the repositories, commit SHAs, licenses, files and
`path:line` citations behind its claims.

| Cluster | Report | Depth |
| --- | --- | --- |
| Mutation testing | [mutation.md](mutation.md) | StrykerJS, Stryker.NET, mutation-testing-elements, PIT + pitest-history, Descartes, mutmut, Cosmic Ray, cargo-mutants (code); Mull, Infection, Stryker4s, Gremlins, mutant (metadata) |
| Test smells, oracles, fidelity, redundancy | [smells-oracles.md](smells-oracles.md) | test-fidelity-long-run, tsDetect, JNose, PyNose, pytest-tidy, Descartes, TOGA, SNUTS.js (code); smelly-test, AromaDr, Pytest-Smell, checked coverage, OASIs/GAssert, test-suite reduction (papers/metadata) |
| Testing agents and skills | [agents-skills.md](agents-skills.md) | dotnet/skills, microsoft/testfx, qodo-cover, Pynguin (code); Meta TestGen-LLM and ACH (papers); Diffblue, TestSprite, Playwright agents, anthropics/skills (documentary) |
| Selection, impact, flakiness, failure intelligence | [selection-flaky.md](selection-flaky.md) | pytest-testmon, Ekstazi, STARTS, Gradle test-retry, Smart Tests CLI, iDFlakies, DeFlaker, FlakeFlagger, NonDex, pytest-rerunfailures/randomly/flakefinder, target-determinator (code); Develocity, SeaLights, MS TIA, Nx, Jest/Vitest (documentary) |
| E2E, mobile, contracts, real dependencies, accessibility | [e2e-contracts-a11y.md](e2e-contracts-a11y.md) | Playwright, Cypress, axe-core, Pact core, Testcontainers Java, Schemathesis (code); Android/GMD, Pact Broker, Lighthouse, pa11y, Specmatic, WireMock (documentary) |
| Result analysis, reporting, observability | [reporting-observability.md](reporting-observability.md) | ReportPortal analyzer and model, Allure 2/3, allure-python, CTRF, OpenTelemetry semconv (code); Datadog, Trunk, Codecov, BuildPulse, Tesults (documentary) |

## Method and limits

- Each cluster was researched by a separate agent with the same brief: shallow clones in a scratch directory outside
  the repository, read and grep only — nothing installed, built or run — cloned content treated as data (one clone
  carried an agent instruction file; it was not followed). Claims are labeled CONFIRMED-IN-CODE (read at a cited line),
  DECLARED-ONLY (docs, README, papers) or HYPOTHESIS (closed tools). The clones are not part of this repository.
- **No external tool was executed and no benchmark was run against another tool.** Every comparison here is
  documentary or source-level; none is an executed comparison (see `benchmarks/README.md` for the design of one).
- Popularity was not used. Paper figures are quoted as published; figures recalled from memory are marked so in the
  cluster reports and must be verified before being quoted elsewhere.
- The reporting cluster's agent could not write its file; its report was recovered verbatim from its final message.
  The smells cluster's agent was stopped by a usage limit after writing its report; its "unfinished" list is its own.
- Token use (approximate, agents' own counts): mutation ~120k, smells ~190k, agents ~165k, selection ~125k, E2E
  ~105k, reporting ~100k (orchestration and the agents' overhead excluded).

### Claims the orchestrator verified in source or in Assertiva's code before acting on them

| Claim | Where checked | Outcome |
| --- | --- | --- |
| Playwright folds did-not-run and interrupted-only tests into `skipped`, and `flaky` covers mixes without an expected pass | `teleReceiver.ts` `computeTestCaseOutcome` at `41e6a18` | confirmed; adapter fixed in 0.7.3 |
| StrykerJS writes its options (`disableBail`, default false) into the report; PIT writes `killingTest` vs `killingTests` (full matrix) | `mutation-test-report-helper.ts:252`, `stryker-core.json`, `XMLReportListener.java:99-102` | confirmed; `killers_complete` added in 0.7.3 |
| Stryker.NET marks carried-over results "Result based on previous run" | `BaselineMutantFilter.cs:108` | confirmed; reuse counted in 0.7.3 |
| Assertiva's negative control counted a test that already failed as a detector | `assertiva/evidence.py` | confirmed and reproduced; fixed in 0.7.3 |
| Assertiva's retirement guard skipped detected mutants with no named killer | `assertiva/improve.py` | confirmed and reproduced; fixed in 0.7.3 |
| Imported Surefire XML loses `flakyFailure`/`rerunFailure` | `assertiva/adapters/junit.py` (the Maven adapter already handled them) | partially true; fixed for imports in 0.7.3 |
| `ASSERTION_ROULETTE` and `MYSTERY_GUEST` are engine smells no extractor emits | `assertiva/effectiveness.py`, repository grep | confirmed; removed in 0.7.3 |
| `assert (x, "msg")` is classed as a value oracle | Python AST and `test_facts.py` | confirmed; tautology in 0.7.3 |
| Playwright JSON `config.metadata` (git diff, committer e-mail) could leak into Assertiva's report | `assertiva/adapters/playwright.py` | not an issue: the adapter reads only `config.projects` |

Everything else in the cluster reports is the agents' reading, cited but not re-verified here.

## A. Landscape (the projects that matter most to Assertiva)

| Project | Category | License | Inputs → outputs | Why it matters |
| --- | --- | --- | --- | --- |
| StrykerJS / Stryker.NET | mutation (JS/TS, C#) | Apache-2.0 | project + config → mutation-testing-elements JSON (+HTML) | the interchange format Assertiva ingests; records its own config and (Stryker.NET) reuse |
| PIT (+ pitest-history, Descartes) | mutation (JVM) | Apache-2.0 / LGPL-3.0 | classes + tests → `mutations.xml`, Descartes `methods.json` | full-matrix mode is visible in the XML; Descartes classifies pseudo-tested methods from executed extreme mutants |
| mutmut, Cosmic Ray, cargo-mutants | mutation (Python, Rust) | BSD-3 / MIT / MIT | project → aggregate stats / JSONL dump / `outcomes.json` | baseline gating and forced-fail controls (mutmut), lossless dump (Cosmic Ray), diff-vs-tree check (cargo-mutants) |
| dotnet/skills, microsoft/testfx | agent skills for testing | MIT | prompts + project → audits, tests, evidence tables | the closest public agent-skill analogue; ledger discipline, mutation witness rule, baseline-vs-skill evals, `verify_execution.py` |
| qodo-cover, Meta TestGen-LLM / ACH, Pynguin | test generation | AGPL-3.0 / papers / MIT | source + tests → generated tests | keep rules: coverage-only (qodo, weak) vs "kills a mutant no existing test kills" (ACH, Pynguin assertions) |
| tsDetect, JNose, PyNose, pytest-tidy, SNUTS.js | test smells | GPL-3.0 / GPL-3.0 / Apache-2.0 / MIT / GPL-3.0 | test sources → smell counts or instances | breadth of smell catalogues; independent studies show weak validity of smell counts |
| test-fidelity-long-run | agent-written test fidelity harness | none (all rights reserved) | change requests + reference app → kill rate per clause | "mutation zero" (the change's tests against the base revision) and clause-tagged probes |
| pytest-testmon, Ekstazi, STARTS, target-determinator | test selection | MIT / Apache-2.0 / permissive / Apache-2.0 | code + history → selected tests | block/bytecode fingerprints that ignore cosmetic changes; "star" always-run tests; both-revision comparison |
| Gradle test-retry, iDFlakies, NonDex, pytest-randomly | retries and flakiness | Apache-2.0 / none / MIT / MIT | runs → attempts, OD/NOD labels, seeds | mass-failure retry cap; order-prefix classification; seeded, replayable nondeterminism |
| Playwright, Cypress | browser E2E | Apache-2.0 / MIT | specs → JSON results, traces | outcome semantics per attempt; traces prove the real engine |
| Pact, Testcontainers, Schemathesis | contracts and real dependencies | MIT | pacts, containers, OpenAPI → verifier JSON, JUnit, seeds | pending and vacuous verifications; privileged reaper risk; reproducible seeds |
| axe-core, Lighthouse, pa11y | accessibility | MPL-2.0 / Apache-2.0 / LGPL-3.0 | page state → violations/passes/incomplete | explicit `incomplete`; 57 % of WCAG issues at best by its own README |
| ReportPortal, Allure 2/3, CTRF, OpenTelemetry | results and observability | Apache-2.0 / Apache-2.0 / MIT / Apache-2.0 | results → histories, categories, portable JSON | stable identity with parameters, retry grouping, known-issue files; none is revision-scoped |
| Diffblue, TestSprite, Develocity, SeaLights, Datadog, Trunk | closed products | proprietary | — | documentary only; their algorithms are hypotheses |

## B. Deep dives

The deep dives are the cluster reports. The findings that changed Assertiva in 0.7.3 are listed above; the ones that
shape the next versions are summarized in C, D and F.

## C. What they do better, and where Assertiva stands after 0.7.3

| Capability | Who does it better, and how | Assertiva after 0.7.3 |
| --- | --- | --- |
| Knowing whether killers are complete and results fresh | Stryker writes its config; PIT's element name; Stryker.NET's reuse reason | IMPLEMENTED (killers_complete, reuse, incremental; retirement and stage stay unproven otherwise) |
| Orchestrating mutation tools | all mutation tools; baseline gating, forced-fail harness check (mutmut), diff-vs-tree check (cargo-mutants) | PLANNED (M4); ingestion only |
| Pseudo-tested methods from executed extreme mutation | Descartes, cargo-mutants FnValue | PLANNED; Descartes `methods.json` UNSUPPORTED |
| Keep rule for generated or strengthened tests | ACH, testfx mutation-test-improver, Pynguin assertion minimization | PLANNED (M3b); improve challenges candidates with controls/mutants but has no per-change "newly detects" verdict |
| Change binding ("mutation zero") | test-fidelity-long-run | UNSUPPORTED as a named protocol (generic negative controls exist) |
| Cannot-fail Python assertions | pytest-tidy (tuple assert, uncalled mock asserts, mock typos) | PARTIAL (tuple assert in 0.7.3; mock no-op patterns open) |
| Smell catalogue breadth | tsDetect/JNose/PyNose | deliberately narrow: research shows smell counts weakly tied to real defects |
| Fidelity: declared level vs simulated boundaries | none comparable | IMPLEMENTED (lead) |
| Cosmetic-change-aware selection | testmon (AST blocks), Ekstazi/STARTS (debug-stripped bytecode) | UNSUPPORTED (file digests) |
| Unknown-dependency safety | STARTS star tests, MS TIA run-all | IMPLEMENTED and stricter (widening, UNKNOWN_RELATION) |
| Declared dependency maps, lockfile-aware impact | MS TIA user map, Nx lockfile diff | UNSUPPORTED |
| Environment identity for flakiness | Develocity same-inputs, testmon package set | PARTIAL (OS, machine, executable only) |
| Retries that keep the first failure; mass-failure cap | Gradle test-retry, rerunfailures | PARTIAL (improve reruns; no cap) |
| Order dependence, seeds | iDFlakies, NonDex, pytest-randomly | PLANNED (M6) |
| Playwright outcome semantics | Playwright's own `outcome()` | IMPLEMENTED (0.7.3) |
| Real browser proven | Playwright trace `context-options` | UNSUPPORTED (project-name inference, E3) |
| Contract verification results | Pact verifier (pending, vacuous) | PLANNED (M7) |
| Accessibility results | axe incomplete/no-passes semantics | PLANNED (M7) |
| Portable results in and out | CTRF, allure-results | UNSUPPORTED |
| Revision-scoped evidence and claim boundary | none of the reporting tools | IMPLEMENTED (lead) |
| Skill evaluation | dotnet/skills baseline vs skill arms with a sign test; dormancy cases | PARTIAL (hidden rubrics and a separate judge are stronger; no baseline arm, no dormancy cases) |

## D. Integrate, adapt, build or reject

| Decision | Items | Why |
| --- | --- | --- |
| **Integrate (ingest)** | cargo-mutants `outcomes.json`; Cosmic Ray `dump` JSONL (cr-xml stays rejected); Descartes `methods.json`; Pact files and verifier JSON; axe/Lighthouse/pa11y output; CTRF (in and out); allure-results; Schemathesis JUnit + seed; Android connected-test XML | output formats only: no license obligation, no execution, provenance kept per file |
| **Integrate (orchestrate, M4)** | native mutation tools in disposable copies, complete killers requested when a retirement depends on them, reuse disabled by default | better than re-implementing mutation; every run bound to a revision |
| **Adapt the concept** | mutation zero; per-change "newly detects" keep rule; witness rule for survivors; ledger of protected tests; self-reconciliation before answering; no blind retry after a blocker; environment digest; order-prefix classification; known-issue files; fingerprint label memory as E3; Testcontainers-style session sweep | their ideas fit Assertiva's contracts; several sources have no license or GPL code, so only concepts are used |
| **Build** | mutant fingerprints; kill-set subsumption; AST-normalized change digests; declared impact map; lockfile diff; mass-failure retry cap; "no proven path to this change" annotation; baseline arm and seeded bad responses in `evals/semantic.py` | small, deterministic, inside existing modules |
| **Reject** | coverage-only keep rules; auto-heal or rewriting assertions to match the code; ML triage loaded from pickles (ReportPortal, FlakeFlagger); DeFlaker (credentials in source); remote/cloud execution (TestSprite); Testcontainers execution by default (privileged reaper, Docker socket); similarity-based redundancy; generated oracles (TOGA: independent studies report very low precision); aggregate scores or severities | each contradicts evidence discipline, safety or the no-score rule |

## Agent-led practice: what to adopt and what to keep

From [agents-skills.md](agents-skills.md) §7. Keep: question-first investigation and the "obtain the evidence
yourself" default (it works because the engine isolates execution — dotnet/skills defaults to static-only because it
cannot), hidden rubrics, engine-validated dispositions, no aggregate score, human approval of change ids. Adopt in
0.8.0 (each needs an eval before and after, and changes `SKILL.md`, so none is in 0.7.3): no retry of a blocked
operation through another tool or agent; reconcile the lead sentence, dispositions and counts before answering; credit
protected behavior next to the gaps; state the witness (input → original observation → mutant observation) before
calling a survivor a gap; label an expected value copied from current output as characterization. The engine must not
grow into judgment: these are instructions for the agent, while what the engine adds (completeness flags, fingerprints,
`requires_executed` validation) stays deterministic.

## E. Benchmark design

`benchmarks/README.md` holds the protocol (calibration, spent regression set, frozen confirmation set), the
effectiveness scorer, and the competitive benchmark design: fair conditions, scenarios with known defects and negative
controls, metrics (precision, recall, false positives on look-alikes, seeded defects detected, selection misses, cost,
safety, reproducibility) and the acceptance rule that no superiority is claimed without executed comparison. The
cluster reports add the fixtures each decision needs (for example: Pact `result: true` with zero interactions must not
pass; an axe report with zero violations must never yield "accessible"; a bail-mode mutation report must not prove
exclusive detection).

## F. Prioritized backlog

Targets: **0.7.3** (this stabilization, done), **C1** (the first competitive checkpoint after 0.7.3: integrity and
evaluation work that changes no user-facing capability), **0.8.0** (capabilities). Each item lists the modules it
touches and what proves it.

| # | Item | Target | Modules | Proof |
| --- | --- | --- | --- | --- |
| 1 | Negative controls need green-before detectors; retirement unproven under incomplete killers, unnamed detections and carried-over results; Playwright outcomes; imported Surefire reruns; tuple assert | 0.7.3 (done) | evidence, improve, models, adapters/mutation, playwright, junit, test_facts | reproductions that fail on 0.7.2 (see CHANGELOG) |
| 2 | Mutant fingerprint (path, operator, replacement, digest of the original snippet) | C1 | `evidence.py`, `models.py` | same mutant after an inserted line keeps its fingerprint |
| 3 | Typed `mutationRun` in the report schema (existing keys + completeness, reuse) | C1 | `schemas/assurance-report.schema.json`, `report.py` | schema validation test |
| 4 | Baseline arm (`--arm baseline|skill`) and a seeded bad response per grader-ready case in `evals/semantic.py`; dormancy cases | C1 | `evals/semantic.py`, `evals/cases/` | sign test over ≥5 discordant cases; a seeded overclaiming response FAILs (budget approval first) |
| 5 | Second labeler for confirmation set v2; agreement recorded | C1 | `tests/fixtures/confirmation/v2/` (labels reviewed, not edited silently) | agreement table in `benchmarks/README.md` |
| 6 | Mock no-op assertions and mock typos as tautologies (Python) | C1 | `adapters/test_facts.py` | labeled positives and negatives (`mock.assert_called_once()` legitimate) |
| 7 | Per-change "newly detects" keep rule for created or strengthened tests | 0.8.0 (M3b) | `improve.py`, `candidate.py`, report | an assertion-free test that raises coverage is not credited; a test killing a baseline survivor is |
| 8 | Ingest cargo-mutants, Cosmic Ray dump, Descartes `methods.json` | 0.8.0 (M4) | `adapters/mutation.py`, `effectiveness.py` | per-format fixtures; Descartes not-covered never pseudo-tested |
| 9 | Orchestrate native mutation tools in disposable copies (complete killers, no reuse, revision-bound targeting) | 0.8.0+ (M4) | new adapter per ecosystem, `improve.py` | red baseline → BLOCKED; requested complete killers recorded |
| 10 | Mutation zero (base-revision control) for change-scoped audits | 0.8.0 | `evidence.py`, references, evals | fixture pair where a base-passing test is caught |
| 11 | Pact and axe ingestion with their vacuity rules; Playwright trace engine; execution target per run | 0.8.0 (M7) | new `adapters/pact.py`, `adapters/axe.py`, `playwright.py`, schema | the "must not support" fixtures in the E2E report |
| 12 | Environment digest v2; mass-failure retry cap; order probe with seeds | 0.8.0 (M6) | `history.py`, `process.py`, `improve.py` | seeded OD/NOD benchmark, precision 1.0 for confirmed order dependence |
| 13 | AST-normalized change digests; declared impact map; lockfile diff; "no proven path" annotation; retrospective selection simulation | 0.8.0+ (M5) | `python_impact.py`, `impact.py`, `selection.py`, `components.py` | selection experiment extended; zero misses on defect rows |
| 14 | CTRF ingest/export and allure-results ingest | 0.8.0+ | new adapters, CLI | round trip; no finding text in the export |
| 15 | Agent-led adoptions listed above | 0.8.0 | `SKILL.md`, `references/` | evals before and after, rubrics fixed before running |

## Unfinished in this wave

Android result formats (AGP not cloned), Pact JVM/JS serializers, Testcontainers Python/Node defaults, Lighthouse
scoring internals, the dotnet/skills dashboard numbers, EvoSuite/TestPilot/Copilot testing agents, Jest/Vitest/
SeaLights/GZoltar code, and several paper figures recalled from memory (marked in the cluster reports). A second wave
would start from these, only when a decision depends on them.
