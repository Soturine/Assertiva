# Status

## Current milestone: M1 — Executable Assurance ✅ (closed 2026-10-06)

M0 (foundation and contracts) and M1 (executable audit + improve vertical slice) are complete. Next: M2 — Cross-stack Intelligence (not started).

Python/pytest, packaging, GitHub Actions and pre-commit are the first reference adapters, **not the architecture**. The core works on capabilities, normalized records, stages, provenance and limitations; it never branches on a tool name (a test enforces this for mutation tools).

## IMPLEMENTED (executable, tested)

### Audit — `assertiva audit`
- Runtime read-only guard: every project file (including caches and ignored files) is fingerprinted before and after; any change exits with code 3.
- Static (AST) pytest inventory and oracle/negative-path signals; coverage.py JSON; tests execute only with `--execute`, always in a disposable copy.
- With `--execute`: native pytest evidence plus built/installed artifact qualification.
- `--mutation-report PATH` and `--junit-xml PATH` ingest existing tool output as portable evidence.
- Verification Surface from GitHub Actions and pre-commit with local-vs-CI parity findings; unknown commands/actions stay UNKNOWN.
- Reports, state and traces live in `ASSERTIVA_HOME` (default `~/.assertiva`), which must be outside the project.

### Improve — `assertiva improve`
- One command with internal phases: start (baseline measured in an isolated copy + candidate workspace) → qualify → `--approve <change ids>` → apply → post-apply verification; `--discard` drops the session.
- Candidate workspace: detached Git worktree for a clean repository root, otherwise a copy; verified against the baseline fingerprint, including uncommitted work.
- Change set ADD / MODIFY / RETIRE_CANDIDATE with fingerprints and diffs; originals are never commented out or deleted without approval; apply refuses atomically when the project file or the candidate changed since qualification.
- Qualification stages (PASS / FAIL / BLOCKED / NOT_RUN / UNKNOWN; unavailable is never PASS):
  - STATIC_AND_DISCOVERY, CANDIDATE_TESTS from native collection/execution;
  - ORIGINAL_REGRESSION: unchanged original tests rerun against the candidate;
  - COVERAGE_AND_ORACLES: line/branch coverage (when coverage.py is in the target interpreter) and weak-oracle deltas;
  - NEGATIVE_PATHS: static failure-contract dimensions (E3) combined with runtime outcomes; fails when the candidate weakens negative-path evidence;
  - MUTATION_OR_NEGATIVE_CONTROLS: deliberate negative controls (run on baseline and candidate) and ingested mutation reports (`--mutation-report baseline=…|candidate=…`), side by side; any surviving or uncovered mutant fails the stage whatever the score; reports produced for other source are not used;
  - PIPELINE_EQUIVALENT: DISCOVERED → AUTHORIZED → EXECUTED. Native runner checks and recognized side-effect-free checks (lint, format, typecheck, static analysis, package/build) run in the disposable copy; migration/container/startup/health/unknown commands only with `--run-check CHECK_ID`; deploy/publish never; compound shell steps are not reproduced; allowed-failure keeps its meaning; a matrix reproduced in one environment is partial;
  - BUILD_AND_ARTIFACT: wheel built from a copy, installed with `--no-deps` into a fresh environment, imports checked to resolve to the artifact, tests run against it with the source packages removed; reports the exact wheel and sha256;
  - PREVIEW_DEPLOY: NOT_RUN (no authorized non-production adapter; production is never used);
  - STABILITY_AND_COST: bounded reruns (≤2) of touched and failing invocations (≤50); first outcome kept; STABLE / FLAKY_SIGNAL / CONSISTENT_FAILURE / INSUFFICIENT_EVIDENCE plus the runtime delta.
- Metric deltas with explicit direction; test count is contextual; runtime and mutation counts are directional only when comparable (same invocations / same number of evaluated mutants).

### Adapters
- **pytest (native + static):** invocation and parameter ids, markers, `-k`/`-m`/path filters (deselection recorded), skip / xfail / xpass / fail / error, collection errors, custom items, inherited and cross-module materialization, coverage, failure-contract dimensions (error type, message, machine code, field/path, structured context, protocol status, state after rejection, awaited async failure), unobserved async tasks. No bytecode or cache written into measured trees; stale in-tree bytecode never loaded.
- **Python packaging:** wheel build (local backend without isolation when importable, otherwise isolated), install, import origin, tests against the artifact, files in packaged directories missing from the wheel.
- **Mutation reports:** mutation-testing-elements JSON (Stryker family), PIT `mutations.xml`, mutmut CI stats (aggregate only). Native statuses preserved.
- **JUnit XML:** nested suites, duplicates, failures/errors/skips, properties, timestamps, bounded output; declared format limits.
- **GitHub Actions, pre-commit, command classification** with reproduction plans.

### Report
- One model (`schemas/assurance-report.schema.json`): audit = CURRENT + findings + recommendations + remaining unknowns; improve = BASELINE vs CANDIDATE (+ APPLIED only after approval).
- Self-contained accessible HTML: landmarks, native keyboard controls, light/dark, filters, expandable findings and diffs, chart only from measured pairs with the metrics table as its equivalent, sections for qualification + stability, negative paths, mutation, artifact, runs/provenance (executed vs ingested), Verification Surface, Evidence Delta, "What does green prove?" and remaining unknowns. PASS / FAIL / BLOCKED / UNKNOWN / NOT_RUN each have a distinct style.

### Execution provenance
- Every subprocess runs non-interactively with a timeout and bounded output; each stage and command writes start/end events (stage such as `current:pytest-native`, command, start, timeout, return code, duration, timeout classification) to a trace under `ASSERTIVA_HOME` as it happens; the report links the trace.

### Fast feedback ≠ full qualification
- Tests are marked by what they run: unmarked = fast/core, `integration` = real tooling in subprocesses, `artifact` = wheel builds. The three groups add up to the whole suite (88 + 68 + 18 = 174); a conftest guard fails any unmarked test that becomes slow (>2 s including setup).
- Per-commit CI (~2 min): validator, fast suite, integration + artifact suites in parallel, wheel build, installed-CLI smoke, and the read-only invariant through the installed CLI (`audit --execute` and an `improve` qualification) on a small generated package.
- Full self-dogfood (on demand / `v*` tags): the installed wheel audits this repository with `--execute`, runs the suite natively and again against Assertiva's own installed wheel, and must leave the tree unchanged. Last run (2026-10-06, `9169cf7`): 174 invocations PASS, wheel build/install/import/tests PASS, 4m25s.

| | Before (2026-10-05) | After (2026-10-06) |
| --- | --- | --- |
| Full suite, local | 170 tests, 418.5 s sequential | 174 tests, 141 s parallel |
| Fast/core suite | — | 88 tests, ~5 s local, 1.8 s CI |
| Artifact tests, sequential | 195.8 s | 139.1 s (2 more tests) |
| Per-commit CI | 8–16 min (full self-dogfood every commit) | 1m51s |

## SPECIFIED (documented, not executable)
- Running mutation tools (Assertiva only ingests their reports); Cosmic Ray ingestion (its `cr-xml` cannot distinguish pending from killed).
- sdist verification; startup/health/migration checks beyond explicitly authorized declared commands.
- Rollback / forbidden side-effect / idempotency evidence beyond static post-rejection assertions.
- JUnit XML and mutation reports as *improve* candidate-state evidence for non-native runners (audit only today).
- Authorized remote CI execution and non-production preview deployment.
- Order dependence, historical flakiness and failure clustering.

## PLANNED
See [ROADMAP.md](ROADMAP.md): M2 cross-stack adapters (Jest/Vitest, Playwright, JUnit/Gradle/Maven, .NET, Go/Rust), Azure Pipelines/GitLab/Jenkins, impact graph, history; M3 stable CLI/MCP, evidence store, benchmarks.

## Claim boundary
- Static inventory and negative-path dimensions are E3 signals, not runtime proof; a post-rejection assertion is not rollback proof.
- CI configuration is declared evidence (E2): Assertiva does not evaluate expressions, reusable workflows or branch protection, and reproduces only checks it understands, in the local environment.
- Ingested reports (mutation, JUnit) are tied to the measured state only when they carry source content; otherwise the limitation is stated.
- Stability verdicts mean "no instability observed in N executions", not "not flaky".
- A ~55-minute local execution seen on 2026-10-05 was not reproduced; the per-command trace exists so a recurrence can be diagnosed rather than guessed.
