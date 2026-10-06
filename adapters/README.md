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

Executable reference adapters today: pytest (native + static), Python packaging, GitHub Actions, pre-commit, mutation reports (mutation-testing-elements, PIT, mutmut stats) and JUnit XML. See `STATUS.md` for their exact claim boundaries.

First-party support is incremental. The absence of a dedicated adapter does not make a project unsupported: preserve observed commands and declared checks generically, mark unknown capabilities honestly, and avoid guessing semantics.
