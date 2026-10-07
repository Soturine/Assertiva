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

Artifact evidence must name what it proved. Tests passing against an installed wheel while the target environment is visible prove compatibility with that environment, not that the wheel declares everything it imports; declared-dependency closure is a separate claim, and so are a clean index install and the sdist.

Assertiva should report exactly what is evidenced and what remains unknown, rather than saying "all tests passed; deployment is safe."

Implemented (M2): GitHub Actions, Azure Pipelines, GitLab CI and Jenkins share one normalization (`adapters/ci_common.py`); each provider adapter only reads its own format. Every check carries a lifecycle — DECLARED, SELECTED (unconditional/conditional), EXECUTED (UNKNOWN without run evidence), DEPLOYS — plus matrix, operating system, runtime and environment. Declared runtimes and targets are compared with what CI selects (MATRIX_GAP / MATRIX_UNVERIFIED / CI_SINGLE_OS), and artifact lineage is reported only as far as evidence goes (PUBLISHED_ARTIFACT_NOT_QUALIFIED, ARTIFACT_LINEAGE_UNKNOWN, TESTED_ARTIFACT_DIFFERS_FROM_DELIVERED). See STATUS for the exact boundary.


## Candidate pipeline and preview qualification

During `improve`, Assertiva runs the candidate against pipeline-equivalent checks in the isolated workspace (implemented). Triggering remote CI is specified, not executable: if a provider adapter can ever do it safely, that action requires appropriate authorization and its cost/external side effects must be explicit.

Specified, not implemented: where a project supports ephemeral/preview environments, candidate qualification could include a non-production preview deployment to verify package, migration, startup, health and selected E2E behavior. Today no adapter does, and the report lists preview/deployment behavior under "not evidenced".

A production deployment is not a default test mechanism. If no safe preview path exists, report deployment evidence as NOT_RUN/UNKNOWN rather than simulating confidence.
