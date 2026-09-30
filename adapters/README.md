# Adapter Contract

Assertiva adapters translate a native runner/framework into normalized capabilities and evidence.

The core must not ask "is this pytest?" to decide policy. It asks what the adapter can prove.

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
