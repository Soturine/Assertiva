# Status

## Current milestone: M2 — Scale & Cross-Stack Intelligence (active)

M0 (foundation and contracts) and M1 (executable audit + improve vertical slice, closed 2026-10-06) are complete. M2 has started with scale hardening; see ROADMAP.md for what is done and what is not.

Python/pytest, packaging, GitHub Actions and pre-commit are the first reference adapters, **not the architecture**. The core works on capabilities, normalized records, stages, provenance and limitations. Contract tests drive measurement, qualification and the report with fake adapters (a runner with non-pytest ids, a non-wheel artifact, coverage from another source), and fail if a core module names a tool or parses a runner's id syntax.

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

### Execution budget (M2)
- Child processes inherit a nesting depth; at depth 2 Assertiva refuses to execute project code (BLOCKED, never PASS). A project whose tests audit themselves stops after one nested level instead of recursing until timeouts.
- Artifact qualification refuses to re-qualify a target an outer run is already qualifying (same `name==version`).
- Pipeline-equivalent reproduction reuses the candidate run when a delivery check selects the same tests (only cosmetic flags differ) and records the reuse.
- Audit, improve and the report record each expensive evidence decision: EXECUTED / REUSED / NOT_RUN / BLOCKED with its reason.

### Filesystem boundaries (M2)
- Links (symlinks, Windows junctions) are project entries identified by their target and are never followed: fingerprints and copies never include outside content, internal links are rebased into copies (they cannot point back into the original), and copies are removed without following links.
- Apply refuses traversal paths, writes through a linked directory (in the project or the candidate), candidate links that leave the project and case-only collisions, all before writing anything.
- Approved apply is transactional: writes are staged next to their targets and installed with atomic replaces, originals are backed up outside the project, every applied entry is verified against the candidate fingerprint, and any failure restores all touched entries, removes created directories and staging files (`ApplyFailedError`, "rolled back").
- Nested repositories are included from the working tree and reported; links leaving the project are reported (`PROJECT_LINK_ESCAPES_ROOT`). The executable bit is part of a file's digest on POSIX.

### Artifact fidelity (M2)
- Artifact evidence states what it proves per dimension: source isolation (imports resolve to the installed wheel), target-environment compatibility (tests pass against the wheel with the target environment visible), declared-dependency closure, clean install and sdist.
- Declared-dependency closure is checked offline: a clean environment sees only the wheel and the distributions it declares (resolved transitively with markers from the target environment) and every module of the package is imported. An undeclared import fails; a declared dependency that is not installed locally makes closure UNKNOWN, never PASS.
- Clean install from a package index and the sdist are NOT_RUN and reported as such.

### CI reproducibility (M2)
- CI installs are constrained by `constraints.txt`, uses the current official checkout/setup-python actions without persisted credentials, and runs a light Python 3.11 job (the declared minimum): fast suite, wheel build/install and CLI smoke. Contract tests keep the minimum-Python job tied to `requires-python`.
- Branch protection on `main` is not configured; requiring the CI checks is recommended in CONTRIBUTING.md (owner decision).

### Execution provenance
- Interpreter capability probes are evidence about one run: reused within a run (CLI command, audit, improve step), re-probed by the next, keyed by interpreter identity, never cached outside a run.
- Credential-looking values in recorded commands (`token=`, `password=`, `user:pass@` URLs) are redacted in traces.
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
