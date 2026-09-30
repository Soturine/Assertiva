# Framework Adapter Guidance

Adapters translate framework capabilities; they do not redefine Assertiva policy.

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

## Rule
Never map Assertiva diagnostic levels to one universal flag such as -vvv. Adapter capability discovery is required.
