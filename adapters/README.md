# Adapter Contract

Assertiva adapters translate native project tooling into normalized capabilities and evidence. An adapter may target a test runner, linter, type checker, build/package tool, schema/migration validator, security scanner, hook system, CI/CD provider, deployment environment, artifact format or another verification source.

The core must not ask "is this pytest/GitHub Actions/tool X?" to decide policy. It asks what the adapter can discover, execute, normalize and prove.

## Capability examples

- discover definitions;
- enumerate concrete invocations;
- provide stable IDs;
- filter/run by ID;
- run failed/related tests;
- emit structured result;
- expose retries/attempts;
- emit line/branch/test-specific coverage;
- capture trace/screenshot/log artifacts;
- expose seed/replay data;
- expose concurrency/race diagnostics;
- ingest mutation results.

An adapter returns SUPPORTED, UNSUPPORTED, or UNKNOWN plus version/provenance as appropriate.

Unknown frameworks may still use portable formats such as JUnit XML, TAP, LCOV, Cobertura, JaCoCo-style reports, or project-defined commands. Lack of a first-party adapter must degrade honestly, not disable Assertiva.


## Adapter families

Typical families include:
- test discovery/execution;
- coverage and mutation;
- lint/static/type analysis;
- build/package/artifact;
- schema/migration/generated-code checks;
- localization/i18n validation;
- security/SAST/dependency scanning;
- hook/task runners;
- CI/CD workflow discovery and run evidence;
- container/startup/health/deployment verification;
- portable report formats and custom project commands.

## Runner capabilities (as implemented)

| Adapter | Discovery | Collection | Execution | Per-test outcomes | Coverage | CI parity | Impact selection | Artifact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pytest | static (testpaths, python_files) + native | native, collection errors | yes | yes: parameters, markers, skip/xfail/xpass | coverage.py if installed | reproduces CI pytest arguments | file subset | Python wheel |
| unittest | static (`test*.py` / `-p`) | native discovery, load errors | yes | yes: subTest, expectedFailure, unexpected success, fixture errors | coverage.py if installed | declared CI arguments are the default run | no (full suite, stated) | Python wheel |
| Django | static (`test*.py`) | the project's TEST_RUNNER | yes | yes through the runner's result class; none for runners without one | coverage.py if installed | `manage.py test` arguments | no (full suite, stated) | none |
| Jest | config/dependency | Jest `--json` | yes | yes: skips/todo, retries, table cases | istanbul json-summary | `jest`/`npm test` arguments | no | none |
| Vitest (3+) | dependency/config | JSON reporter (Jest format) | yes, writes nothing into the project | yes: skips/todo, table cases by location, pass after retries | the project's v8/istanbul provider | `vitest` arguments (projects, filters) | no | none |
| Playwright | config | JSON reporter | yes | yes: projects, retries, attachments | no | declared/selected/executed projects | no | none |
| Maven | `pom.xml` | Surefire/Failsafe reports | offline only | yes: reruns, parameterized methods | JaCoCo | goal-level (`test` vs `verify`) | by method | none |
| Gradle (Java, Kotlin/JVM, Android local, KMP JVM targets) | settings and build scripts, version-catalog aliases, convention plugins of included builds, source sets; tasks confirmed by Gradle's own task list | JUnit XML per test task | yes, through a provisioned Gradle (never the wrapper jar); offline unless provisioned | yes; a parameterized case reported by display name only keeps an UNKNOWN declaration | JaCoCo / Kover the build already applies | test-task arguments | no (full suite, stated) | none |

Instrumented Android tests, iOS, JS, Wasm and Native targets are listed per module as NOT_RUN with the host they need; Android local tests without an SDK are BLOCKED; custom test tasks are listed as AVAILABLE and run only when named.

Test effectiveness (every audit) reads tests in Python (syntax tree), JavaScript/TypeScript and Kotlin/Java (lexically) into one shared model; the extractors' limits are stated in each report.

## Mutation tools (run by the engine)

| Tool | Applies when | Needs | Detecting tests |
| --- | --- | --- | --- |
| Cosmic Ray (`adapters/cosmic_ray.py`) | Python tests under a declared pytest, unittest or Django runner | `cosmic-ray` in the project's interpreter | not recorded |
| StrykerJS (`adapters/stryker.py`) | a `package.json` project tested with Jest or Vitest | `@stryker-mutator/core` and its runner plugin in `node_modules` | every one |
| PIT (`adapters/pit.py`) | a Maven build that declares `pitest-maven` | the plugin in the local Maven repository (Maven runs offline) | every one |

A mutation adapter is one module with a `KEY` and `TOOL`, `describe(root, python, origin)` (does it apply, can it run here, with which runner, and why) and `execute(...)` (run on a disposable copy, return a `MutationRun`), listed in `MUTATION_ADAPTERS` in `assertiva/adapters/mutation.py`. Selection, evidence, the protection comparison and the report do not change when one is added; the core modules name no tool (a contract test enforces it). The user picks with `--mutation-tool` when several apply; a missing tool is BLOCKED with the reason, never a pass.

Absent support is a limitation of Assertiva, not a failure of the audited project: it is reported as UNKNOWN or NOT_RUN.

Executable reference adapters today: pytest (native + static), unittest, Django, Jest, Vitest, Playwright, Maven (Surefire/Failsafe, JaCoCo, build surface), Gradle (JUnit XML, JaCoCo/Kover), Python packaging, GitHub Actions, Azure Pipelines, GitLab CI, Jenkins (through one shared CI normalization in `ci_common.py`), pre-commit, package.json scripts, mutation reports (mutation-testing-elements, PIT, mutmut stats, Cosmic Ray dump), JUnit XML, CTRF, Allure, Pact contracts and verifications, axe-core results, and three mutation tools the engine runs (below). See `STATUS.md` for their exact claim boundaries.

First-party support is incremental. The absence of a dedicated adapter does not make a project unsupported: preserve observed commands and declared checks generically, mark unknown capabilities honestly, and avoid guessing semantics.
