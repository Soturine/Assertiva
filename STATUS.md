# Status

## Current milestone: M1 — Executable Assurance (active)

M0 (foundation and contracts) is complete. M1 turns those contracts into an executable core behind two commands: `assertiva audit` and `assertiva improve`. Python/pytest, GitHub Actions and pre-commit are the first reference adapters, **not the architecture**.

## IMPLEMENTED (executable, tested)

### Audit
- `assertiva audit` runs inside a runtime read-only guard: a fingerprint of every project file (including caches and ignored files) is compared before and after; any change exits with code 3.
- Tests execute only with `--execute`, always in a disposable copy; reports and state go to `ASSERTIVA_HOME` (default `~/.assertiva`), which must be outside the project.
- Static (AST) pytest inventory, oracle/negative-path signals and coverage.py JSON ingestion; native pytest evidence with `--execute`.
- Verification Surface discovery: GitHub Actions steps and pre-commit hooks become `VerificationCheck`s (test, lint, format, typecheck, package, security, dependency, migration, container, unknown/custom...), keeping `continue-on-error`, conditions and matrices. Unrecognized commands/actions stay UNKNOWN.
- Findings include `LOCAL_CHECK_NOT_OBSERVED_IN_CI`, `CI_ONLY_CHECK`, `UNCLASSIFIED_VERIFICATION`, `NO_DELIVERY_PIPELINE_OBSERVED`, `NATIVE_COLLECTION_ERRORS`, `NATIVE_TESTS_FAILING`, `STATIC_INVENTORY_DIVERGES_FROM_NATIVE` and the earlier static findings.
- Unknown toolchains report `UNKNOWN`, never "0 tests".

### Improve
- One command with internal phases: start (baseline measured in an isolated copy + candidate workspace) → qualify → `--approve <change ids>` → apply → post-apply verification. `--discard` drops the session.
- Candidate workspace: detached Git worktree for a clean repository root, otherwise a copy; verified against the baseline fingerprint (including uncommitted work).
- Change set from baseline vs candidate: ADD / MODIFY / RETIRE_CANDIDATE with original and candidate fingerprints and a reviewable diff. Originals are never commented out or deleted without approval.
- Apply requires explicit change ids, refuses atomically if the project file or the candidate changed since qualification, and verifies the applied files and the applied project's native run.
- Qualification stages, each PASS / FAIL / BLOCKED / NOT_RUN / UNKNOWN:
  - STATIC_AND_DISCOVERY and CANDIDATE_TESTS from native collection/execution;
  - ORIGINAL_REGRESSION: unchanged original tests rerun against the candidate (a weakened test cannot hide a production regression);
  - COVERAGE_AND_ORACLES: line/branch coverage (when coverage.py exists in the target interpreter) plus weak-oracle deltas;
  - NEGATIVE_PATHS: static signals only, so it is never PASS yet;
  - MUTATION_OR_NEGATIVE_CONTROLS: deliberate find/replace negative controls run on baseline and candidate (KILLED / SURVIVED / INVALID);
  - PIPELINE_EQUIVALENT: reproduces delivery checks an adapter understands; partial reproduction is UNKNOWN;
  - BUILD_AND_ARTIFACT, PREVIEW_DEPLOY: NOT_RUN; STABILITY_AND_COST: UNKNOWN (single run).
- Metric deltas with explicit direction (HIGHER/LOWER_IS_BETTER, CONTEXTUAL, INFORMATIONAL); test count is contextual; runtime is directional only when the same invocations ran.

### Native pytest adapter
- Recording plugin loaded from outside the tree; no bytecode or cache is written to the measured directory and stale in-tree bytecode is never loaded.
- Invocation ids, parameter ids, markers, `-k`/`-m`/path filters (deselected recorded), skip / xfail / xpass / fail / error, collection errors, custom collected items (with limitation), declaration → materialization for inherited tests (including cross-module), coverage via coverage.py.
- No tests collected → UNKNOWN; runner unavailable → BLOCKED.

### Report
- One report model (`schemas/assurance-report.schema.json`) for audit (CURRENT + findings + recommendations + unknowns) and improve (BASELINE vs CANDIDATE, then APPLIED only after approval).
- Self-contained HTML: semantic landmarks, keyboard-accessible native controls, light/dark, severity/kind filters, expandable findings and diffs, chart only from measured pairs with the metrics table as its equivalent, Verification Surface, qualification stages, Evidence Delta and "What does green prove?".

### Dogfood
- CI runs the validator and the suite, builds the wheel, smoke-runs the installed CLI from outside the tree, and audits this repository with `--execute`, failing if the working tree changed or the native run is not PASS.

## SPECIFIED (documented contracts, not yet executable)
- Mutation-tool adapters (mutmut, Cosmic Ray, Stryker, PIT, Stryker.NET) feeding the negative-control stage.
- Rejection state-effect/rollback evidence for negative paths.
- Build/package/startup/health qualification and source-tree vs artifact parity.
- Authorized remote CI execution and non-production preview deployment.
- Flake/retry/order-dependence measurement.
- Semantic UI/browser, harness fidelity, fixtures/doubles analysis beyond the documented model.

## PLANNED
See [ROADMAP.md](ROADMAP.md): other runners (Jest/Vitest, Playwright, JUnit, .NET), Azure Pipelines/GitLab CI/Jenkins, impact graph, history, MCP, benchmarks.

## Claim boundary
- Static inventory is not native collection; the GitHub Actions adapter reads declared configuration (E2), not run evidence, and does not evaluate expressions, reusable workflows or branch protection.
- Pipeline-equivalent reproduction covers only checks an adapter understands, in the local environment, not CI matrices.
- Coverage scope follows the project's coverage configuration (or coverage.py defaults).
- Negative controls are provided by the caller; Assertiva does not yet generate mutants.
