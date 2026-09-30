# Framework Adapter Guidance

Adapters translate framework capabilities; they do not redefine Assertiva policy.

Each adapter should expose a capability descriptor instead of relying on framework-name conditionals in core logic. Candidate capabilities include discovery, invocation enumeration, stable IDs, filtering, structured results, retries, line/branch/test-specific coverage, traces/artifacts, seed/replay, concurrency diagnostics and mutation integration.

Unsupported or unknown capability must be reported explicitly, never replaced by an invented command.

## pytest
Potential capabilities include node IDs, last-failed, failed-first, stepwise, traceback controls, JUnit XML, duration reporting and collection-only discovery.

Use locals output cautiously because locals may expose secrets.

## Jest / Vitest
Discover native related/changed test selection, JSON/JUnit reporting, test-name/path filters, retries and coverage per installed version.

## Playwright
Prefer traces/screenshots/video on failure or retry according to project debugging need instead of maximum artifacts on every green run.

## JUnit / Maven / Gradle
Use native filtering, structured reports, failure rerun tooling and build dependency information where available.

## .NET
Use runner-native filters, structured reports, diagnostics and project dependency information.

## Parameterized/data-driven portability

pytest parametrization, JUnit parameterized invocations, Jest/Vitest table cases, xUnit theories and analogous mechanisms map to the same core model: test definition + concrete invocation(s).

## Error portability

Pydantic ValidationError is only one structured error surface. Validation libraries, HTTP problem documents, GraphQL errors, typed Result/Error values and domain exceptions map to the same core error-contract model when possible.

## Rule
Never map Assertiva diagnostic levels to one universal flag such as -vvv. Adapter capability discovery is required.
