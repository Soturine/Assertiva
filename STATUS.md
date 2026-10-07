# Status

## Current milestone: M2 — Scale & Cross-Stack Intelligence: DONE (2026-10-06)

M0 (foundation and contracts), M1 (executable audit + improve vertical slice) and M2 (scale, cross-stack, impact & selection, history, delivery; closed 2026-10-06, version 0.5.0) are complete. M3 has not started. ROADMAP.md lists exactly what exists and what was explicitly not required (.NET, Go, Rust, Vitest, Gradle).

Python/pytest, packaging, GitHub Actions and pre-commit are the first reference adapters, **not the architecture**. The core works on capabilities, normalized records, stages, provenance and limitations. Contract tests drive measurement, qualification and the report with fake adapters (a runner with non-pytest ids, a non-wheel artifact, coverage from another source), and fail if a core module names a tool or parses a runner's id syntax.

## Architecture since 0.6.0: agent-led, evidence-grounded

The auditing agent leads (SKILL.md and three references): it starts from the user's question, chooses evidence by what it can settle, correlates and resolves engine findings, reports what no tool raised, and decides completion by whether the evidence answers the question. The engine is its instrument (measurement, execution in disposable copies, parsing, identity, provenance, guards, report). `assertiva audit --assessment FILE` joins the agent's conclusion, dispositions of engine findings and own findings to the run's report, so the page and the answer agree. The public surface is still `assertiva audit` and `assertiva improve`.

## IMPLEMENTED (executable, tested)

### Audit — `assertiva audit`
- Runtime read-only guard: every project file (including caches and ignored files) is fingerprinted before and after; any change exits with code 3.
- Static (AST) pytest inventory and oracle/negative-path signals; tests execute only with `--execute`, always in a disposable copy.
- With `--execute`: native pytest evidence plus built/installed artifact qualification.
- `--mutation-report PATH`, `--junit-xml PATH` and `--coverage-report PATH` (coverage.py JSON, istanbul json-summary, LCOV, Cobertura XML, JaCoCo XML; `--coverage-json` is an alias) ingest existing tool output as portable evidence.
- Verification Surface from GitHub Actions, Azure Pipelines, GitLab CI, Jenkins (declarative, literal steps), pre-commit, package.json scripts and Maven builds, with local-vs-CI parity findings; unknown commands/actions/tasks/libraries stay UNKNOWN. Python `unittest` in CI (including `python -X … -m unittest discover`) counts as the declared test runner and `self.assert*` calls as oracles; `unittest.TestCase` subclasses are inventoried whatever their name (bases resolved through `unittest` imports/aliases and same-module inheritance; other bases are reported as TEST_CLASS_COLLECTION_UNKNOWN); there is no native unittest adapter, so equivalence between Assertiva's pytest execution and the CI unittest run stays UNKNOWN.
- Reports, state, traces and history live in `ASSERTIVA_HOME` (default `~/.assertiva`), which must be outside the project (`--report-dir` may choose another directory outside it). One run writes one canonical `audit.html` + `audit.json`.
- `--run-check CHECK_ID` (repeatable): reproduces a discovered check (CI step, hook, script) in a disposable copy under the read-only guard and records pass/fail of the whole command (`declared_checks`, a high `DECLARED_CHECK_FAILED` finding when a gating check fails). Naming the check authorizes it; deploy/publish, compound shell steps and steps without a command never run. It is the safe route for runners without a native adapter (unittest, `manage.py test`).
- `--assessment FILE` (no measurement): validates the auditing agent's assessment against the latest audit of the project and re-renders the same `audit.html` + `audit.json`. Refused (exit 2) for another run (`run_id`), a project changed since the run (content digest), malformed entries, findings or dispositions without evidence, or a whole-finding CONFIRMED / FALSE_POSITIVE without every item reviewed. Dispositions: CONFIRMED, PARTIAL, CONTEXTUAL, FALSE_POSITIVE, UNRESOLVED. Engine severity, summary and evidence are never rewritten; the effective priority follows the disposition; a false positive's recommendation is WITHDRAWN. Agent findings carry a basis (OBSERVED / DECLARED / INFERRED) and cited evidence.
- Exit code: 0 the command ran and reported (including a failing audited suite), 2 refusal or misuse, 3 read-only violation. The audited tests' verdict is in the report, never in the exit code.

### Improve — `assertiva improve`
- One command with internal phases: start (baseline measured in an isolated copy + candidate workspace) → qualify → `--approve <change ids>` → apply → post-apply verification; `--discard` drops the session.
- Candidate workspace: detached Git worktree for a clean repository root, otherwise a copy; verified against the baseline fingerprint, including uncommitted work.
- Change set ADD / MODIFY / RETIRE_CANDIDATE with fingerprints and diffs; originals are never commented out or deleted without approval; apply refuses atomically when the project file or the candidate changed since qualification.
- Qualification: five pillars — EXECUTION, BEHAVIORAL_ASSURANCE, FAULT_SENSITIVITY, DELIVERY_FIDELITY, STABILITY_AND_COST — each aggregating its checks (FAIL > BLOCKED > UNKNOWN > PASS; a check that did not run never passes a pillar on its own and stays listed under remaining unknowns). Checks (PASS / FAIL / BLOCKED / NOT_RUN / UNKNOWN; unavailable is never PASS):
  - EXECUTION: CANDIDATE_TESTS — native collection of the whole candidate (any collection error fails) and execution of the added/modified tests (one check since 0.6.0; it replaced STATIC_AND_DISCOVERY + CANDIDATE_TESTS, which reported the same missing runner or blocked run twice);
  - BEHAVIORAL_ASSURANCE:
    ORIGINAL_REGRESSION: unchanged original tests rerun against the candidate;
    COVERAGE_AND_ORACLES: line/branch coverage (measured, or ingested with `--coverage-report baseline=…|candidate=…`) and weak-oracle deltas; covered and total are compared as counts, and a percentage over a changed denominator is UNKNOWN with the note shown in the report (80/100 → 90/120: covered up, total changed, percent down), never a pass or a fail by percentage alone;
    NEGATIVE_PATHS: static failure-contract dimensions (E3) combined with runtime outcomes; fails when the candidate weakens negative-path evidence;
  - FAULT_SENSITIVITY: MUTATION_OR_NEGATIVE_CONTROLS: deliberate negative controls (run on baseline and candidate) and ingested mutation reports (`--mutation-report baseline=…|candidate=…`), side by side; any surviving or uncovered mutant fails the stage whatever the score; reports produced for other source are not used;
  - DELIVERY_FIDELITY: PIPELINE_EQUIVALENT: DISCOVERED → AUTHORIZED → EXECUTED. Native runner checks and recognized side-effect-free checks (lint, format, typecheck, static analysis, package/build) run in the disposable copy; migration/container/unknown commands only with `--run-check CHECK_ID`; deploy/publish never; compound shell steps are not reproduced; allowed-failure keeps its meaning; a matrix reproduced in one environment is partial;
    BUILD_AND_ARTIFACT: wheel built from a copy, installed with `--no-deps` into a fresh environment, imports checked to resolve to the artifact, tests run against it with the source packages removed; reports the exact wheel and sha256;
  - STABILITY_AND_COST: bounded reruns (≤2) of touched and failing invocations (≤50); first outcome kept; NO_INSTABILITY_OBSERVED / OBSERVED_UNSTABLE_CURRENT_RUN / CONSISTENT_FAILURE / INSUFFICIENT_EVIDENCE (the same vocabulary as history) plus the runtime delta.
- Preview/deployment behavior is not a stage: with no authorized non-production adapter it appears only under "not evidenced" (production is never used).
- Metric deltas with explicit direction; test count is contextual; runtime and mutation counts are directional only when comparable (same invocations / same number of evaluated mutants).

### Adapters
- **pytest (native + static):** invocation and parameter ids, markers, `-k`/`-m`/path filters (deselection recorded), skip / xfail / xpass / fail / error, collection errors, custom items, inherited and cross-module materialization, coverage, failure-contract dimensions (error type, message, machine code, field/path, structured context, protocol status, state after rejection, awaited async failure), unobserved async tasks. No bytecode or cache written into measured trees; stale in-tree bytecode never loaded.
- **Python packaging:** wheel build (local backend without isolation when importable, otherwise isolated), install, import origin, tests against the artifact, files in packaged directories missing from the wheel.
- **Mutation reports:** mutation-testing-elements JSON (Stryker family), PIT `mutations.xml`, mutmut CI stats (aggregate only). Native statuses preserved.
- **JUnit XML:** nested suites, duplicates, failures/errors/skips, properties, timestamps, bounded output; declared format limits.
- **GitHub Actions, pre-commit, command classification** with reproduction plans.

### Report
- One model (`schemas/assurance-report.schema.json`): audit = CURRENT + findings + recommendations + remaining unknowns; improve = BASELINE vs CANDIDATE (+ APPLIED only after approval).
- One canonical, self-contained, offline HTML per run: `audit.html` for audit, `improve.html` for improve (baseline, candidate and applied are states inside it, never separate pages); several pages exist only for several independent runs.
- Auditor's assessment (when attached): the auditor's conclusion leads the decision layer in the language it was written in; ranking, counts, verdict and next step use the effective priority; each dispositioned card shows the engine observation, the engine default priority, the disposition, rationale, reviewed scope and items, and cited evidence, with the raw engine evidence unchanged; agent findings render as findings marked as found by the auditing agent with their basis.
- Decision layer: conclusion and why, execution scope, an integrated next step (only when the evidence ranks one; a tie is listed as a tie), Confirmed / Needs attention / Not proven (heuristic E3 positives are shown as signals, never as confirmed), "What does green prove?" as an audit scope with distinct evidence kinds (executed, measured, inspected, declared, not proven), and for improve candidate readiness plus a lifecycle (baseline → candidate → review → approval → applied → post-apply check) that shows a step done only with its evidence. Auditability layer behind disclosure: findings with raw evidence, an evidence snapshot by domain and every metric, run, declared check, negative path, mutation report, artifact, delivery, selection and history panel, the evidence delta (regressions first, unchanged collapsed), the complete claim boundary grouped by domain, remaining unknowns, the execution budget and the canonical JSON. No aggregate score.
- English and Brazilian Portuguese: presentation text is localized by stable key; the engine's own narrative (claim boundary, limitations, qualification summaries, change reasons) is localized by exact sentence templates, with a contract test over every sentence the engine writes into a report; raw technical or external evidence and sentences without a template stay original, in technical detail.
- Provenance: `assertiva_version` and `runtime` (install kind; for a source checkout its git revision and local changes) identify the code that produced the evidence, and the page names the Assertiva that rendered it and says so when that differs. Accessible: landmarks, skip link, keyboard, focus-visible, status never by colour alone, light/dark, reduced motion, print styles; checked from 1920 px to 390 px.

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

### JavaScript: Jest (M2)
- Runs the project's own installed Jest with `--json` in a disposable copy and normalizes its official results: outcomes (pending/todo/disabled are skips, never passes), test files that fail to run as collection errors, `test.each` cases grouped into one declaration by Jest-reported location, retried tests flagged with their invocation count, istanbul json-summary coverage.
- Never installs dependencies or uses `npx`: missing Node or Jest is BLOCKED. The project's installed `node_modules` (ignored, so never copied) is linked into each disposable copy, never copied or followed on cleanup; reports state that it is not isolated and that dependency changes made by a candidate are not installed. No static oracle or negative-path analysis exists for JavaScript yet (UNKNOWN).
- `package.json` scripts join the Verification Surface as local checks. Proven against a real Jest 30.5.2 fixture locally and in CI (installed once with `npm ci --ignore-scripts`; CI fails instead of skipping when the fixture is missing). Vitest is not supported yet.

### Browser: Playwright (M2)
- Runs the project's own installed Playwright Test with the official JSON reporter in a disposable copy: per-project materializations, outcomes (`test.fail` is an expected failure, `fixme`/`skip` are skips), retries (a flaky pass keeps its attempt count and a run limitation), durations, attachments (screenshot/trace/video references by name, attempt and relative path), files that fail to load as collection errors.
- Execution matrix: projects DECLARED (config), SELECTED (in the run), EXECUTED (an attempt ran); engines chromium/firefox/webkit inferred from project names (stated as inferred), NOT_CONFIGURED when no project targets them. A project whose browser is not installed is NOT_RUN with a limitation, never a test failure. Non-executed matrix entries appear under "not evidenced".
- Locator evidence: static (E3) counts of ROLE, LABEL, PLACEHOLDER, TEXT, TEST_ID, CSS, XPATH, OTHER, UNKNOWN locators; informational, never a score.
- Never installs browsers or dependencies; a literal non-local `baseURL` blocks execution. No coverage, no visual comparison. Proven against a real Playwright 1.63.0 fixture: locally with an installed Chromium-based browser (`channel`), and in CI in a dedicated job that installs only Chromium's headless shell.

### Delivery intelligence (M2)
- CI configuration from GitHub Actions, Azure Pipelines, GitLab CI and Jenkins goes through one normalization: each command step is a classified check with gate, matrix, operating system, runtime (matrix, setup version or container image), environment and condition. Lifecycle: DECLARED by the file, SELECTED UNCONDITIONAL or CONDITIONAL, EXECUTED always UNKNOWN (remote CI is never queried), DEPLOYS when a deploy command or deployment environment is declared. Includes, templates, extends, shared libraries and interpolated commands are kept as UNKNOWN, not followed.
- Matrix visibility: what the project declares (`requires-python` minimum, `engines.node`, Maven compiler release, Playwright projects) versus what CI configuration selects: MATRIX_GAP (declared but no job selects it), MATRIX_UNVERIFIED (CI never states the dimension), CI_SINGLE_OS (info). No score.
- Artifact lineage: source revision → isolated build → artifact name and sha256 → tested status → declared publish/deploy steps, only as far as evidence goes. Findings: PUBLISHED_ARTIFACT_NOT_QUALIFIED (a job builds and publishes without tests), ARTIFACT_LINEAGE_UNKNOWN (deliveries declared, no evidence ties the delivered bytes to a tested artifact), TESTED_ARTIFACT_DIFFERS_FROM_DELIVERED (an artifact with the tested name in `dist/` has different bytes). Nothing is ever published or deployed.
- Review candidates (static, Python, never findings or gates, nothing removed): shared assertion helpers, central test doubles, integration tests that replace a dependency, snapshot-assertion concentration, declarations materialized in several classes, ranked by the number of tests involved.

### History (M2)
- `audit --execute` and `improve` (baseline, candidate with its reruns, applied) record evidence in a local, schema-versioned SQLite store under `ASSERTIVA_HOME` (never in the project): revision (content digest) and VCS revision, environment identity (platform + runner executable), adapter, invocation outcomes, durations, runner-reported attempts, selection reasons, failure fingerprints, artifact identity, coverage and qualification summaries. No stdout, attachments, traces, raw reports or secrets; failure text is kept only as a bounded, redacted, normalized signature. `ASSERTIVA_HISTORY=off` disables it; an unusable store never fails audit/improve.
- One stability vocabulary for reruns and history: OBSERVED_UNSTABLE_CURRENT_RUN (failed and passed in this run, including a pass after runner retries), HISTORICALLY_FLAKY (same revision and environment: at least two failures and a pass; one failure is never flaky), CONSISTENT_FAILURE, ENVIRONMENT_SPECIFIC, NO_INSTABILITY_OBSERVED (not proof), INSUFFICIENT_EVIDENCE.
- Durations: p50 with at least 5 samples, p95 with at least 20 (nearest rank); otherwise none. Failure fingerprints are deterministic (stage, exception/assertion type, first source location, first message line with timestamps, ids, addresses, temporary paths and durations normalized) and grouped only when identical. Reports show history signals per invocation.

### Impact graph (M2)
- Revision-scoped impact graph (content digest) with tiered, provenanced edges; Python slice: imports, fixtures/conftest scope, configuration, declarations, base tests, helpers and naming (E4, never a fact); runtime coverage mapping (E0) is not wired (a report cannot prove its revision). Computed dynamic imports and unparseable files are unknowns. See `docs/IMPACT_AND_SELECTION.md`.
- Conservative test selection: `audit --changed-since REV` selects tests with a proven path to each change and widens for shared fixtures (scope), configuration, unmapped changes, no proven path, stale graphs, unreadable changes or no changes (full suite); tests reaching an unknown relation are always added and confidence is then never complete. With `--execute` only the selected set runs, reported as a selected-set claim. Runner subset execution: pytest.
- Minimal monorepo affected set: components and declared dependencies from npm `package.json` workspaces and `pyproject.toml` subprojects; a change affects its component and dependents; workspace configuration, files outside components and unresolvable local dependencies widen. Affected components appear in the selection report.

### Java: Maven, Surefire/Failsafe, JaCoCo (M2)
- Runs the project's Maven offline (`-o`, failures recorded) in a disposable copy and reads only the reports that run wrote. Each Surefire/Failsafe report goes through the generic JUnit XML parser; the adapter adds the build phase (Surefire `test`, Failsafe `integration-test`: the build's classification, not proof of scope), reruns and flaky passes, parameterized invocations of one method, the test's source file and the project's own JaCoCo report (counts per kind). JVM system properties in the reports are never copied.
- Selection by invocation id runs each test in its own phase (Failsafe's default include patterns); selection is per method, so every parameterized case of a selected method runs.
- Never downloads dependencies or Maven and never runs `mvnw`: missing Maven or missing local dependencies are BLOCKED. Malformed or missing reports are not evidence.
- Build Verification Surface from `pom.xml`: Surefire, Failsafe (an integration-test failure only fails the build with the `verify` goal) and JaCoCo (a `check` goal enforces a threshold, otherwise it only reports). Profiles and parent POMs are not resolved. Gradle is not supported yet.
- Proven against a real Maven 3.10 / JUnit 6.1.3 / Surefire+Failsafe 3.6.0 / JaCoCo 0.8.15 fixture locally (Temurin 21) and in CI in a dedicated job.

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

### Three kinds of evidence (never interchangeable)
- **Ordinary CI** (every commit): validator, fast/core suite, integration and artifact suites, wheel build, installed-CLI smoke and the read-only invariant through the installed CLI on a generated package; dedicated `browser` and `java` jobs for real Playwright and Maven runs.
- **Runtime self-qualification** (`runtime-self-qualification`, on demand / `v*` tags): deep deterministic qualification of the runtime. The installed wheel audits this repository with `--execute` and qualifies its own wheel; it runs the fast/core suite natively and against the installed wheel, because the source suites already ran in ordinary CI (new execution must buy new evidence). Tests deselected this way are declared in the report. Qualification runs the tests from a copy without `.git` and without the source package, so a self-test that reads repository files must not assume either; `tests/test_installed_artifact_context.py` builds that context (wheel, venv, no `.git`, no source package) and runs the tests that read repository files in it. The full-suite design last ran on 2026-10-06 (`e462547`): 419 invocations PASS, wheel PASS, declared dependency closure PASS, 24m45s; the current design on the same tree: 310 invocations PASS, identical artifact fidelity, 102 s.
- **Semantic Skill evaluation** (`evals/`): an agent using `SKILL.md` is graded by a separate judge against a private rubric. It evaluates reasoning and evidence discipline, not the runtime.

| | M1 close | M2 close |
| --- | --- | --- |
| Tests | 174 | 420 |
| Fast/core suite, official sequential command | ~5 s | 310 tests, 22–38 s |
| Full suite, local parallel, all ecosystems real | 141 s | 304 s |
| Per-commit CI (validate job) | 1m51s | ~2m14s, browser and java jobs in parallel |

Tests are marked by what they run (unmarked = fast/core, `integration`, `artifact`, `browser`, `jvm`); the fast suite reports unmarked tests slower than 2 s instead of failing them.

## SPECIFIED (documented, not executable)
- Running mutation tools (Assertiva only ingests their reports); Cosmic Ray ingestion (its `cr-xml` cannot distinguish pending from killed).
- sdist verification; startup/health/migration checks beyond explicitly authorized declared commands.
- Rollback / forbidden side-effect / idempotency evidence beyond static post-rejection assertions.
- JUnit XML and mutation reports as *improve* candidate-state evidence for non-native runners (audit only today).
- Authorized remote CI execution and non-production preview deployment.
- Order dependence; failure clustering beyond identical deterministic fingerprints; runtime coverage mapping (E0) into the impact graph (a coverage report cannot prove its revision); impact graphs for languages other than Python (their changes widen to the full suite); subset execution for runners other than pytest.

## PLANNED
See [ROADMAP.md](ROADMAP.md): M3 (productization and empirical validation) has not started. Explicitly not required for M2 and not implemented: .NET, Go, Rust, Vitest, Gradle.

## Claim boundary
- Static inventory and negative-path dimensions are E3 signals, not runtime proof; a post-rejection assertion is not rollback proof.
- `assertiva audit` finishing is not the audited suite passing: the command exits 0 after reporting a failing suite or a failed artifact qualification. The verdict is the report's status, findings and run outcomes.
- CI configuration is declared evidence (E2): Assertiva does not evaluate expressions, reusable workflows or branch protection, and reproduces only checks it understands, in the local environment.
- Ingested reports (mutation, JUnit) are tied to the measured state only when they carry source content; otherwise the limitation is stated.
- Stability verdicts mean "no instability observed in N executions", not "not flaky"; history covers only runs recorded on this machine.
- A green selected set proves only that the selected tests passed at that revision; widening never makes a selection complete, and E4 heuristics never narrow a run. The matched experiment (0 misses in 12 controlled defects) is evidence for those cases, not a universal claim.
- Delivery findings come from configuration: whether a CI job was selected or executed, and which bytes were published or deployed, stay UNKNOWN without run evidence.
- Semantic Skill evaluation (first baseline, 2026-10-06, `b053fb3`): four cases (high coverage with weak oracle, heuristic selector overreach, retry until green, and an open self-audit of this repository) were answered by an agent given only `SKILL.md`, the scenario and tools, then judged in one separate context against private rubrics: 4 PASS. It is a mechanism proof on one model family with a same-family judge, not a benchmark; five other prepared cases were not run. The self-audit's gaps are recorded below.
- Known gaps from that self-audit and from M2: CI runs on Linux only (the Windows boundary/link/long-path code has no Windows CI job); branch protection on `main` is an owner setting, so green CI is advisory; the safety-critical logic (read-only guard, transactional apply, aggregation) has no mutation or negative-control evidence of its own.
- A one-off fast-suite failure during M2 (a parallel run, output lost) did not recur in 14 reruns, the full suite or CI; its cause is unknown and it is not called flaky. The fast suite now reports slow tests instead of failing on time.
- A ~55-minute local execution seen on 2026-10-05 was not reproduced; the per-command trace exists so a recurrence can be diagnosed rather than guessed.
