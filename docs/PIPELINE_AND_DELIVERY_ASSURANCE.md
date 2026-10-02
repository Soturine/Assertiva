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
