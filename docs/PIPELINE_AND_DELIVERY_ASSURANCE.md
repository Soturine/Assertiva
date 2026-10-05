# Pipeline & Delivery Assurance

A green local suite and a green CI job are evidence about specific commands, environments and artifacts. They do not automatically prove the deployable artifact will build, install, migrate, start or behave correctly.

Assertiva should compare:

```text
source revision
→ test inventory
→ pipeline-selected tests
→ runtime/environment matrix
→ test results
→ built artifact
→ installed-artifact smoke
→ migration/setup
→ container/process startup
→ health/readiness
→ deployment/preview/staging evidence
```

Typical false-green cases include:

- repository has integration/E2E tests but CI runs only `pytest tests/unit`;
- Python/database/browser matrix differs between local, CI and deploy;
- source-tree tests pass while a wheel omits templates/static/package data;
- migrations run only at deploy time;
- mocks replace the integration boundary being claimed;
- Playwright configuration defines several projects while CI executes one;
- Docker image builds but process startup/health fails;
- retries or allow-failure semantics hide first-failure evidence.

Assertiva should report exactly what is evidenced and what remains unknown, rather than saying "all tests passed; deployment is safe."


## Candidate pipeline and preview qualification

During `improve`, Assertiva may run the candidate against pipeline-equivalent checks in the isolated workspace. If a provider adapter can safely trigger remote CI, that action requires appropriate authorization and its cost/external side effects must be explicit.

Where the project already supports ephemeral/preview environments, candidate qualification may include a non-production preview deployment to verify package, migration, startup, health and selected E2E behavior.

A production deployment is not a default test mechanism. If no safe preview path exists, report deployment evidence as NOT_RUN/UNKNOWN rather than simulating confidence.
