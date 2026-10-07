# Changelog

## [0.5.6] — 2026-10-07 — Report provenance fix and decision surface v3

Patch release; M2 stays closed, M3 has not started. Evidence semantics are unchanged.

### Fixed
- Report provenance could name a stale version: `assertiva_version` came from installed package metadata, which an editable install keeps at the old value after `pyproject.toml` is bumped. The version now comes from the source checkout the code runs from (installed metadata otherwise), reports record the runtime identity (install kind; for a checkout, its git revision and local changes), and the page states which Assertiva rendered it and says so when that differs from the version that produced the evidence.

### Changed
- One decision surface: the conclusion as counts, the execution scope, and an integrated next step (what, why, originating finding, what proves it resolved); "what was examined" in audit and the candidate lifecycle in improve.
- Evidence strength is shown as distinct kinds (executed, measured, inspected, declared, not proven), each with its own glyph and label, instead of bars that read like a score.
- Findings are compact disclosure rows; recommendations form an action plan with proposed → applied → verified; failing pillars come first; the evidence snapshot shows baseline changes and keeps a changed-denominator note beside the percentage; the technical claim boundary is grouped by domain with counts.
- Local time in the page with UTC kept in details, localized decimals in narrative, bounded raw blocks, clearable filters kept in the URL, print styles that open every detail.

### Documented
- Report artifact contract: one run writes one `audit.html` or `improve.html` (baseline, candidate and applied inside it) plus its JSON; several pages appear only for several independent runs.

## [0.5.5] — 2026-10-07 — Assurance Report: decision-first second pass (presentation only)

Patch release; M2 stays closed, M3 has not started. The report model, findings, severities, tiers, adapters and qualification logic are unchanged.

### Changed
- The report has two layers. The decision layer gives the conclusion in words with its reason, whether there is execution evidence or only inspection, the next step only when the evidence ranks one (ties are listed as ties), and Confirmed / Needs attention / Not proven. Heuristic (E3) positives are shown as signals, never as confirmed. "What does green prove?" is now the audit scope: each area with its evidence strength (executed or verified, measured or ingested, inspected, declared, not proven).
- Improve leads with candidate readiness, what blocks review, the delta counts and "not applied"; the delta lists regressions first and collapses unchanged metrics. The baseline/candidate bar chart was removed.
- Findings lead with title, consequence and links to evidence and fix; recommendations are grouped by priority (do first, high, important, optional) and always marked proposed. Metrics start with a summary by domain; full tables, checks, runs and provenance are disclosure panels. Navigation has five areas and tracks the active one.
- Typography and layout: editorial verdict, fewer cards and less uppercase, a ruled ledger, tablet and phone layouts checked from 1920 px to 390 px.

### Fixed
- With pt-BR selected, the claim boundary, qualification summaries, limitations, change reasons and dynamic finding summaries stayed in English. The engine's sentences are now localized by their exact templates (technical values kept as written); text with no template appears only in technical detail, marked as original. Contract tests guard every engine sentence and the decision layer.

## [0.5.4] — 2026-10-07 — Assurance Report redesign (presentation only)

Patch release; M2 stays closed, M3 has not started. The report model, adapters, evidence and qualification logic are unchanged.

### Changed
- The HTML Assurance Report is reorganized into Overview, Evidence, Verification and Details. The Overview answers what is working (evidence-backed strengths from structured data only), what needs attention, what is not evidenced and what to improve next (an existing recommendation only when the evidence ranks one), next to "What does green prove?". The overall status is never shown as success.
- Findings show a human title, severity, category, evidence basis, why it matters, the proposed improvement, what would close it, and technical details with the code and raw evidence.
- Metrics use display names (ids kept), the delta column appears only when states are compared, the verification surface is grouped by origin with full commands and a table view, and provenance is shown as pairs with the raw JSON available.
- New visual system with light and dark themes, accessible status cues and no horizontal scroll down to phone width; still one offline, self-contained file.

### Added
- English and Brazilian Portuguese in the same report, selected in the header (remembered when storage is available, browser language otherwise). Translation is by stable key; codes, commands, paths, hashes and raw evidence are never translated.

## [0.5.3] — 2026-10-06 — unittest.TestCase static discovery

Patch release; M2 stays closed, M3 has not started. Closes the inventory limitation recorded in 0.5.2.

### Fixed
- The static inventory, inherited-test composition, review candidates and impact declarations recognized only classes named `Test*`. `unittest.TestCase` subclasses are now recognized whatever their name, through `import unittest [as u]`, `from unittest import TestCase [as T]` and same-module inheritance, with unittest's `test` method prefix. A plain class with `test_*` methods is not treated as a TestCase.
- Classes with test methods whose bases cannot be resolved statically (imported from another module, computed, metaclass) are reported as TEST_CLASS_COLLECTION_UNKNOWN instead of being dropped silently or guessed; native collection stays authoritative.

## [0.5.2] — 2026-10-06 — Real-world dogfood fixes

Patch release; M2 stays closed, M3 has not started. Found by running `/assertiva` 0.5.1 on functional-test-designer.

### Fixed
- A CI running `python -X utf8 -m unittest discover -s tests` produced CI_PYTEST_NOT_OBSERVED ("add the test suite to the delivery pipeline"). Interpreter options before `-m` are unwrapped, unittest invocations and their discovery scope are read from CI, and CI_RUNS_PYTHON_UNITTEST keeps the declared CI runner apart from the unsupported native unittest execution (equivalence UNKNOWN).
- `self.assert*` calls in unittest tests were read as missing assertions and raised WEAK_ORACLE_SIGNAL; they now map like the equivalent plain `assert`.
- The Skill reads `report_path` by parsing the whole audit JSON (never a truncated view), confirms the file exists, and reports a missing field as an engine defect.
- The Skill orders evidence by cost: CI head SHA against HEAD and fresh evidence before a full local run, which must say what it adds.

### Added
- Semantic cases: engine-backed report handoff, cost-aware evidence ordering for HEAD (prepared, not yet run).

### Known limitations
- PROJECT_LINK_ESCAPES_ROOT still fires for a Skill installed through a link (e.g. `.claude/skills/assertiva`); a generic external-tooling policy is M3 material.
- The static inventory collects `Test*` classes only; a `unittest.TestCase` subclass with another name is not inventoried.

## [0.5.1] — 2026-10-06 — Skill polish and Skill ↔ engine integration

Patch release; M2 stays closed, M3 has not started. Gaps from the first real use of the Skill on another project.

### Added
- Explicit execution mode in the Skill: `engine-backed` (static `assertiva audit --output json` first, execution only when it buys new evidence, `report_path` shown as the Assurance Report) or `semantic-only` (audit continues, no runtime evidence or HTML promised).
- `assertiva --version`, the cheap probe the Skill uses to detect the engine.
- Four semantic eval cases: engine unavailable, CI green for a different revision, static counts are not execution, dependency reproducibility for a library.

### Changed
- SKILL.md labels every claim as deterministic fact, declared fact, heuristic signal, semantic inference or UNKNOWN (mapped to E0–E4); a CI run proves a revision only with confirmed identity (head SHA = HEAD); static counts never become executed tests; recommendations follow the project's delivery model (no automatic lockfile for libraries); PASS/FAIL/REVIEW belongs only to the Skill evaluation.

## [0.5.0] — 2026-10-06 — M2 Scale & Cross-Stack Intelligence closed

### Added
- Scale hardening: execution budget (bounded nested qualification, same-target recursion refusal, equivalent-evidence reuse), filesystem/path boundaries, transactional approved apply with rollback, artifact fidelity vs declared-dependency closure, run-scoped capability evidence with credential redaction.
- Cross-stack runners through one tool-neutral core: Jest, Playwright (declared/selected/executed projects, engines, retries, attachments, informational locator evidence) and Maven (Surefire/Failsafe phases, reruns, parameterized identity, JaCoCo, build surface). Portable coverage: coverage.py, istanbul, LCOV, Cobertura, JaCoCo with counts; a percentage over a changed denominator is never judged blindly.
- Impact and selection: revision-scoped impact graph (content digest, tiered and provenanced edges, unknowns instead of guesses), `audit --changed-since REV` with conservative widening, fixture-level `conftest.py` granularity, minimal monorepo affected set (npm workspaces, Python subprojects); permanent matched experiment: 0 misses in 12 controlled defects.
- History: local schema-versioned SQLite store (optional), one stability vocabulary for reruns and history, duration percentiles only with enough samples, deterministic failure fingerprints, previous-state comparison in reports.
- Delivery: Azure Pipelines, GitLab CI and Jenkins next to GitHub Actions through one CI normalization (declared/selected/executed/deploys), matrix gaps against declared runtimes and browser projects, artifact lineage findings, review candidates (never gates).

### Changed
- The heavy `dogfood` CI job is now `runtime-self-qualification` (deep deterministic qualification of the runtime, on demand and on `v*` tags): it runs the fast/core suite natively and against the installed wheel instead of repeating the suites ordinary CI already ran (24m45 → 102 s on the same tree, identical artifact fidelity); deselected tests are declared in the report.
- Candidate qualification converged from ten stages to five pillars (execution, behavioral assurance, fault sensitivity, delivery fidelity, stability and cost) with their checks; preview deployment is reported as not evidenced instead of a stage that never ran.
- Stability verdicts renamed: STABLE → NO_INSTABILITY_OBSERVED, FLAKY_SIGNAL → OBSERVED_UNSTABLE_CURRENT_RUN.
- The fast suite reports slow unmarked tests instead of failing them on a 2-second limit.
- The pytest static audit reads CI scope from every recognized CI provider, not only GitHub Actions.

### Added (evaluation)
- `evals/semantic.py`: semantic Skill evaluation with a hidden rubric (the agent sees `SKILL.md`, the scenario and tools; a separate judge sees the rubric and answers PASS/FAIL/REVIEW with justification, no score); one new grader-ready case (self-audit of this repository); first baseline in `evals/results/`.

### Removed
- Seventeen design schemas with no consumer (one of them still described the ten stages); `schemas/assurance-report.schema.json` is the single report contract and now lists every key the report emits.
- Dead code and states with no producer: an unused adapter Protocol, `verification_gap`, an unwired coverage-context ingester, unused verification kinds/origins.

## [0.4.0] — 2026-10-06 — M1 Executable Assurance closed

### Added
- Mutation report ingestion (mutation-testing-elements JSON, PIT XML, mutmut stats) next to negative controls; survivors fail qualification whatever the score; reports for other source are not used.
- Built and installed wheel qualification: import origin checked, tests run against the artifact with source packages removed.
- Declared lifecycle checks with discovered / authorized / executed separation (`improve --run-check`); deploy/publish never runs.
- Negative-path depth: failure-contract dimensions per test and evidence-supported findings.
- Bounded stability reruns with first-failure preservation; execution trace with stage/command timing and timeouts.
- Portable JUnit XML evidence (`audit --junit-xml`); the summarizer script shares the parser.
- Report sections for negative paths, mutation, artifact, stability, run provenance and remaining unknowns; distinct styles for every status.
- End-to-end adversarial qualification tests (real improvement vs. more tests with worse evidence).

### Changed
- `ERROR_STATUS_ONLY_SIGNAL` no longer fires when the error body's code/field is asserted.
- Linters/type checkers/package builds discovered in CI are now reproduced in the candidate copy; unrecognized commands are listed but not run.
- Durations are measured with a high-resolution clock (Windows `monotonic()` ticks in ~15.6 ms steps).
- Audit phases are labelled in the execution trace (for example `current:pytest-native`, `current:python-package`).
- Fast feedback is separated from full qualification: tests are marked `integration`/`artifact`, a guard keeps the fast suite fast, per-commit CI runs in ~2 min, and the full self-dogfood runs on demand and for `v*` tags. Artifact environments no longer bootstrap pip per venv and capability probes are cached per interpreter. Full suite 418.5 s sequential → 141 s parallel.

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
