# Changelog

## [0.7.1] — 2026-10-08 — Consent outside the project, connection targets withheld

Patch release (security). M3 stays in progress.

### Fixed
- A repository could authorize its own commands and unlock the user's credentials: 0.7.0 read `[execution] authorize` and `env` from the audited project's `.assertiva.toml` / `[tool.assertiva]`. Consent now lives only in `<ASSERTIVA_HOME>/consent.toml` (`[[project]]` with `root`, `authorize`, `env`), written by the user outside every project; a project's `[execution]` is reported as a limitation and ignored. The project file keeps only declarative settings (`[tests] runners`, `timeout_s`).
- Consent names the exact command, no longer a check id: an id is a step's position, and a later commit could put another command behind it.
- Connection targets and settings (`DATABASE_URL`, `*_DATABASE_URL`, `PG*`, `MYSQL_*`, `REDIS_URL`, `MONGO_URI`, broker/cache hosts, `DJANGO_SETTINGS_MODULE`) are withheld from project code even without a password in the value, so a shell pointed at staging or production cannot steer a test run there. A consented connection reaches only a local host; one naming another host stays withheld.
- `ASSERTIVA_*` variables were exempt from withholding as a prefix; only names that are not credential-like pass now (the engine's own variables are unaffected).
- STATUS.md said M3 had not started and Vitest was not implemented.
- references/ENGINE.md: consent location, disposable local databases, connections stay local.

### Added
- License: Apache-2.0 (`LICENSE`, package metadata, SKILL.md frontmatter).

### Not done
- The behavioral corrections of 0.7.0 and 0.7.1 (references/ENGINE.md, references/DELIVERY.md) have not been re-evaluated with agents. A disposable copy is still not a sandbox: network and the user's permissions remain, and files such as `~/.pgpass` stay readable by project code.

## [0.7.0] — 2026-10-08 — Evidence integrity, Python and Vitest runners, project configuration

Minor release; M3 is in progress (partial, see ROADMAP.md). Found by dogfooding 0.6.0 on functional-test-designer.

### Evidence integrity and execution safety
- A run is evidence only with its own exit status. Processes run in their own process group and a timeout ends the whole tree (POSIX process group, Windows `taskkill /T`), not only the direct child; a process ended by a signal records it and is never a pass; every command keeps a digest of its complete output.
- `--run-check` records what actually ran: executed argv, exit code / signal / timeout / start failure, duration, output digest and tail (redacted), environment, scope (per-test through a native adapter, otherwise whole command with per-test outcomes UNKNOWN) and `parity` with the declared step per dimension (command, selection, revision, environment, services, result). A local reproduction is LOCAL evidence, never proof that CI ran it. The Verification Surface panel shows it (English and Brazilian Portuguese).
- One reproduction path for audit and improve (`assertiva/reproduction.py`); audit now reproduces a test check through the runner's adapter when one supports its arguments (per-test outcomes), reusing an equivalent measured run, as improve already did.
- Credential-looking environment variables (tokens, secrets, passwords, keys, cloud and registry credentials, URLs with passwords) are withheld from every child process; their names (never values) are a report limitation. The project owner passes a needed variable through with `.assertiva.toml` (`[execution] env`). A disposable copy protects the project tree, not the machine: network and the user's permissions remain, and the documentation says so.
- **Behavior change:** in audit, naming a check selects it but authorizes only test runners and side-effect-free checks. Migrations, containers, custom and unknown commands run only when `.assertiva.toml` (`[execution] authorize`, check ids or exact commands) authorizes them, a file the audit can never write; improve keeps `--run-check` as the human's authorization and also honors the file. Test checks no longer need `--run-check` in improve's delivery qualification.
- `mvn`/`gradle` invocations with publishing goals (`deploy`, `publish*`, `release:*`, `jib:build`, …) are DEPLOY checks and never run; before, any Maven/Gradle command was a TEST check.
- SKILL.md: one rule for the agent's own runs (no pipes into `tail`/`tee`/`head`, no success by output words, keep command and exit code).

### Python runners: unittest and Django
- Native unittest adapter: the project's `python -m unittest` run (arguments from its declared CI invocation) read test by test through a recording result class: pass, fail, error, skips, expected failure, unexpected success, `subTest` cases, async TestCases, inherited methods, load errors and class/module fixture failures. Nothing is inferred from an exit code.
- Native Django adapter: `manage.py test` through a runner class built from the project's own `TEST_RUNNER` that only swaps the result class (discovery, tags, databases and parallelism kept). Proven on a fixture with models, migrations, login-protected views, the test client and async client, SimpleTestCase, TestCase, TransactionTestCase and LiveServerTestCase (Django 6.1.2, locally and in CI). An unavailable database blocks the run with Django's reason.
- The declared runner decides: a unittest CI is reproduced with unittest and Django's with `manage.py test`, not with pytest; pytest stays the default when nothing is declared. The Python static analysis is shared and runs once.
- `CI_RUNS_PYTHON_UNITTEST` now means what is left after native reproduction: tests that exist but unittest never runs (plain functions, non-TestCase classes), medium severity. It no longer appears when unittest runs every test.
- The static inventory of a unittest/Django-only project uses unittest's file pattern (`test*.py` or the declared `-p`) over the whole tree; tests outside the CI start directory remain a CI gap.

### JavaScript/TypeScript: Vitest
- Vitest adapter (Vitest 3+): the project's own Vitest with its JSON reporter, read through the Jest results normalization (now shared): outcomes, load errors, table cases by location, a pass after retries recognized by the failure messages Vitest keeps, coverage through the project's installed v8 or istanbul provider. Nothing is written into the project's linked `node_modules` (caches off, configuration loaded with Vite's module runner); older Vitest is BLOCKED with the reason. Proven on a TypeScript fixture with two projects (Vitest 5.0.3), locally and in CI.

### Productization
- Optional project configuration, `.assertiva.toml` or `[tool.assertiva]` in pyproject.toml, never required: `[tests] runners` (when detection cannot know) and `timeout_s`; `[execution] authorize` and `env`. Unknown or malformed entries are reported in the audit's limitations, never guessed.
- The Assurance Report header names the project's primary language, up to three frameworks/tools and up to three stack services (Docker, PostgreSQL, MySQL/MariaDB, MongoDB, Redis, SQLite, RabbitMQ, Elasticsearch), each with how it is known: counted source files, EXECUTED (its tests ran), CONFIGURED (the project's own configuration at its root, a Compose/CI service image or a Django ENGINE), DECLARED (a dependency only, drawn with a dashed border: presence, not proven use). Icons are inline SVG path data from Simple Icons (CC0), one central catalog (`assertiva/report_icons.py`), a generic icon otherwise; the page stays offline. English and Brazilian Portuguese, light/dark, no horizontal scroll at 390 px.
- The header shows the version the project declares for itself under its name, with the manifest it comes from (pyproject.toml, package.json, Cargo.toml, the project's own pom.xml version, setup.cfg, VERSION); nothing when none declares one, never a dynamic or interpolated value.
- Six hidden-rubric eval cases for this cycle's failure modes: masked exit codes, a CI runner different from the local one, a Django run that cannot reach its database, indirect oracles, declared commands with effects, a local reproduction read as CI.
- One cause, one finding: a failing `--run-check` reproduced through an adapter is one `DECLARED_CHECK_FAILED` naming the failing tests, no longer also `NATIVE_TESTS_FAILING` for the same run.
- Shared helpers instead of copies: one Node.js lookup for the JS adapters, one coverage.py export for the Python runners, one fixture-commit helper in the tests.

### Evaluation and dogfood
- Six new cases × 3 runs, claude-haiku-4-5 evaluated, claude-sonnet-5-5 judge: 9 PASS, 3 REVIEW, 6 FAIL (`evals/results/2026-10-08-m3`). Consistent failure: every Django run proposed passing a shared staging `DATABASE_URL` through, which the CP1 wording of references/ENGINE.md invited; the reference now limits pass-through and authorization to disposable resources and leaves both to the owner. references/DELIVERY.md now explains how a CI step's status is formed (pipes, `pipefail`). The cases were not re-run after these changes; part of the safety case's shortfall is a case/harness mismatch (context-only runs cannot execute the safe step), recorded, not corrected after the fact.
- functional-test-designer (deterministic, read-only): `--execute` now runs unittest as its CI declares — 599 declarations, 824 invocations (subTest cases reported individually), all PASS, coverage 91.8 % line / 78.7 % branch; static audit 5.6 s → 3.1 s, execute 254 s → 225 s against v0.6.0; weak-oracle candidates 19 → 8; project unchanged.
- curso-django-projeto1 (Django 6.1.2, read-only): `manage.py test` ran through the project's DiscoverRunner; its only `tests.py` is empty, reported UNKNOWN (no test executed), never a pass; project unchanged.
- Agent-led dogfoods on real projects were not run in this release.

### Static inventory and oracle signals
- The Python static inventory follows the runner's discovery configuration: `testpaths`, `python_files` and `norecursedirs` (pytest.ini, pyproject `[tool.pytest.ini_options]`/`[tool.pytest]`, tox.ini, setup.cfg) and never enters virtual environments. Before, eval fixture projects under `evals/` were inventoried as Assertiva's own tests despite `testpaths = ["tests"]`.
- Weak-oracle signals recognize indirect oracles: same-module helper functions and methods (including same-module bases) that assert, `assert*`-named calls, test-double interaction assertions, explicit `fail`, and call guards (`side_effect=AssertionError`); `assertIsNone` / `is None` pin an exact value and are no longer existence-only. `WEAK_ORACLE_SIGNAL` lists each candidate's signal. On functional-test-designer the candidates went from 19 to 8 (the remaining ones are "must not raise" contracts the agent must judge), with no project-specific rule.

## [0.6.0] — 2026-10-07 — Agent-led, evidence-grounded architecture

Minor release; M2 stays closed, M3 has not started. Found by dogfooding on functional-test-designer: the Skill stopped at static evidence, sampled weak-oracle candidates and generalized, recommended evidence it could acquire itself, and the HTML kept a link it judged irrelevant as the high-priority next step.

### Changed
- SKILL.md is rewritten around the auditing agent: start from the user's question, choose evidence by what it can settle (no instrument is mandatory or first), correlate, resolve material engine findings instead of generalizing a sample, report gaps no tool raised, and stop when the evidence answers the question or more evidence is not safe, authorized or proportionate. Claims separate provenance (OBSERVED, DECLARED, INFERRED, UNKNOWN) from importance. Agent Skills frontmatter; 287 → ~95 lines, with three references loaded on demand (`references/ENGINE.md`, `TEST_QUALITY.md`, `DELIVERY.md`) replacing `FRAMEWORK_ADAPTERS.md`, `MUTATION_TESTING.md` and `TEST_SMELLS.md`.
- Candidate qualification: the EXECUTION pillar is one check (`CANDIDATE_TESTS`); `STATIC_AND_DISCOVERY` reported the same missing runner, blocked run or collection error a second time. A table test shows the pillar keeps every outcome of the two former checks.

### Added
- `assertiva audit --assessment FILE` attaches the auditing agent's assessment to the latest audit run and re-renders the same page. Dispositions (CONFIRMED, PARTIAL, CONTEXTUAL, FALSE_POSITIVE, UNRESOLVED) sit beside engine findings without rewriting their severity, summary or evidence; agent findings are first-class with basis and cited evidence. Refused for another run, a changed project, entries without evidence, or a whole-finding verdict without every item reviewed.
- `assertiva audit --run-check CHECK_ID` reproduces a discovered check (what CI declares) in a disposable copy, as `improve --run-check` already did. Found by dogfooding: an agent that needed CI-equivalent evidence for a unittest suite ran the runner inside the project tree because audit offered no safe instrument.
- Audit reports carry `run_id`, the project digest, and per finding an `id`, `origin` and effective `priority`; recommendations carry `finding_id`.
- The Assurance Report leads with the auditor's conclusion, ranks and chooses the next step by effective priority, and shows engine observation, engine default priority, disposition, rationale, reviewed scope and cited evidence on each card (English and Brazilian Portuguese).
- Eight hidden-rubric eval cases for agent-led behavior, two on executable fixture projects; the harness hides case titles from the evaluated agent and includes the Skill's references.

### Evaluation and dogfood
- Eight agent-led cases, claude-haiku-4-5 on both sides, blind Haiku judge, n = 1 per case: SKILL.md 0.5.8 4 PASS / 1 REVIEW / 3 FAIL; this release 6 PASS / 2 REVIEW / 0 FAIL (`evals/results/2026-10-07-agent-led-*`).
- functional-test-designer, same short prompt: the agent executed the suite through the engine (599 passed, coverage measured), set the local skill link aside as contextual, reviewed all 19 weak-oracle candidates and attached its assessment; the project was unchanged. Dogfood also produced the fixes below and the completion example in SKILL.md.
- Self-audit with `--execute`: 619 passed, 8 skipped, wheel qualification PASS, project unchanged.

### Fixed
- `coverage run -m pytest` in CI was classified as a coverage command, so the suite looked absent from CI (`CI_PYTEST_NOT_OBSERVED`).
- Static audits recorded the skipped execution as "not requested: fast static feedback"; they now say what stays UNKNOWN and what `audit --execute` measures.

## [0.5.8] — 2026-10-07 — Identity of the native-divergence check, passed counts, report redesign

Patch release; M2 stays closed, M3 has not started.

### Fixed
- `STATIC_INVENTORY_DIVERGES_FROM_NATIVE` compared two different identities: the static inventory (direct definitions plus inherited/composed materializations, never expanding `parametrize`) against native invocations (one per parameter case). Every parameterized suite reported a divergence even when both sides saw the same 409 runnable nodes. The check now compares distinct native materializations; the finding's evidence records `native_materializations` and, separately, `native_invocations`. Regressions: a 4-case parametrize plus one test is not a divergence; tests generated at import time, which static inspection cannot see, still are. Known limit: on a deselected or partial run the static total still counts every discovered test.
- The decision layer said "530 test cases executed and passed" for a run with 522 passed and 8 skipped: it counted a passing run's invocations. Run summaries now carry per-outcome counts (`outcomes`), and the page states passed cases and names skipped and expected failures separately ("522 test cases passed · 8 skipped"). Reports written before this field fall back to a wording that claims no pass count.

### Changed
- A heuristic (E3) signal is no longer listed under Confirmed; it is shown, labelled heuristic, on the inspected negative-path row of the scope.
- The execution scope appears once (the "what does green prove?" ledger) instead of also as a strip in the decision surface.
- "Informational findings only" is now "No high- or medium-priority findings", and its reason states how many relevant areas remain not proven, in a neutral (not success) tone.
- Report page redesign: application layout with a sidebar and top bar, a hero with provenance, a next-step panel, key-figure tiles (passed/total with bar, coverage ring), colored decision cards, numbered findings with a summary rail (priority donut, findings by area that filter the list), numbered evidence records, a provenance grid with an artifacts table, and a separately designed light and dark theme. Still one self-contained offline file, bilingual, responsive from 1920 to 390 px, printable.

## [0.5.7] — 2026-10-07 — Self-test context fix and documentation truth-sync

Patch release; M2 stays closed, M3 has not started. The runtime, the report and its provenance are unchanged.

### Fixed
- Self-tests that incorrectly assumed a source checkout. A real `assertiva audit . --execute` of 0.5.6 reported one failing test natively and four against the installed wheel. Artifact qualification runs the tests from a copy without `.git` and without the source package, and these tests relied on both; the wheel itself was correct.
  - `test_agent_workspace_has_no_rubric` shelled out to `git ls-files` in a copy without `.git`. `workspace_copy` now takes a root and an explicit file manifest and, without a Git checkout or a manifest, raises an error naming the missing prerequisite. The exclusion rule is tested on a synthetic repository in any context; the check on this checkout's tracked files is skipped with a reason when there is no checkout.
  - The report catalog and engine-sentence tests scanned `ROOT/"assertiva"`, which does not exist under wheel qualification; they scan the imported package.
  - The provenance test pinned `install == "source-checkout"`; it now checks the version, the install kind, the absence of a revision for an installed package and the git HEAD for a checkout, each against an independent source.

### Added
- `tests/test_installed_artifact_context.py`: builds this repository's wheel with the adapter's own steps, runs the tests that read repository files in a copy without `.git` and without the source package, and fails on the 0.5.6 tests with exactly the four failures above.
- A contract test that `assertiva audit` exiting 0 is not the audited suite passing: a failing suite exits 0 and the report says FAIL.

### Documentation
- README and owner docs now separate what the model is designed to accommodate from what is implemented (pytest, Jest, Playwright, Maven and portable reports today; Vitest, .NET, Go, Rust and Gradle not yet), describe preview deployment as specified and not executable (reported as not evidenced), describe the decision-first report, one canonical HTML per run, English and Brazilian Portuguese, state that the audit exit code is not the verdict, and say that an MCP server is not implemented.

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
