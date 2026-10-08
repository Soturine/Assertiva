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

Absent support is a limitation of Assertiva, not a failure of the audited project: it is reported as UNKNOWN or NOT_RUN.

Executable reference adapters today: pytest (native + static), unittest, Django, Jest, Vitest, Playwright, Maven (Surefire/Failsafe, JaCoCo, build surface), Python packaging, GitHub Actions, Azure Pipelines, GitLab CI, Jenkins (through one shared CI normalization in `ci_common.py`), pre-commit, package.json scripts, mutation reports (mutation-testing-elements, PIT, mutmut stats) and JUnit XML. See `STATUS.md` for their exact claim boundaries.

First-party support is incremental. The absence of a dedicated adapter does not make a project unsupported: preserve observed commands and declared checks generically, mark unknown capabilities honestly, and avoid guessing semantics.
