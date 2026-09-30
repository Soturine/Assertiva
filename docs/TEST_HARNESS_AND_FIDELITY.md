# Test Harness and Fidelity Model

Test level, framework class, file name, and harness are different concepts.

A test called integration may still replace the database and HTTP boundary with mocks. A unit-named test may exercise a real filesystem. Assertiva should classify what the test actually crosses and observes rather than trusting labels.

## Harness dimensions

Record the relevant subset of these independent dimensions:

- execution boundary: direct function/object call, framework in-process dispatcher, in-memory test host, live local server, external deployed service;
- process boundary: same process, child process, separate service/container, remote environment;
- transport: direct call, framework dispatch, loopback HTTP/RPC, real socket/network, browser protocol, message broker;
- persistence: none, mock/stub, fake/in-memory abstraction, same database engine in memory, disposable real engine/container, remote test database;
- transaction semantics: framework-wrapped rollback, commit/rollback observable, truncation/reset, migration/upgrade path;
- external dependencies: mock, fake, service virtualizer, emulator, disposable container, sandbox, live dependency;
- UI runtime: no UI, simulated DOM, browser engine, emulator/simulator, physical device;
- platform matrix: runtime/OS/browser/device/locale/timezone/theme/accessibility settings;
- concurrency/time: deterministic scheduler/fake clock, real threads/tasks, race detector, real clock/network timing;
- isolation scope: per invocation, test, class/file, worker, suite/session, shared environment;
- lifecycle: setup/teardown/reset strategy and failure cleanup;
- artifact capability: structured result, trace, screenshot, video, network log, DB/log/metric evidence.

## Fidelity claim

Fidelity is always relative to a claim.

Examples:
- a framework test client can strongly test routing, middleware, view/controller behavior, templates or serializers without proving real TCP/network behavior;
- an in-memory database can strongly test repository logic while failing to prove production-engine SQL, locking, constraints, collation or transaction behavior;
- a browser test can strongly prove user-visible composition while being a poor localizer for a domain-rule defect;
- a mock can strongly prove an interaction contract while providing no evidence that the real dependency accepts the request.

Do not collapse fidelity to low/medium/high without explaining the boundary being claimed.

## Django mapping example

Django illustrates why harness and test type must be separate:

- unittest.TestCase: normal Python harness; Django DB isolation is not provided;
- SimpleTestCase: Django utilities/client but database queries are disallowed by default;
- TestCase: database-backed test harness with transaction wrapping/rollback for speed;
- TransactionTestCase: allows observing commit/rollback semantics and resets database differently;
- LiveServerTestCase / StaticLiveServerTestCase: launches a real local Django server and can be paired with Selenium/browser clients;
- DRF APITestCase/APITransactionTestCase/APILiveServerTestCase: similar lifecycle families with APIClient-oriented HTTP assertions;
- RequestsClient: service-interface style and can be pointed at a live/staging URL.

Those names are adapter facts, not Assertiva core policy.

## Cross-framework analogues

Equivalent fidelity choices appear elsewhere:

- Spring: direct controller unit test vs MockMvc/WebTestClient bound in-process vs WebTestClient against a live server;
- ASP.NET Core: direct unit test vs WebApplicationFactory/TestServer vs deployed/browser test;
- Android: local JVM, Robolectric, instrumented emulator/device, screenshot, UI Automator/E2E;
- frontend: jsdom/happy-dom, real browser component test, live browser E2E;
- databases/services: fake/in-memory implementation vs Testcontainers/disposable real infrastructure vs remote sandbox.

## Mismatch findings

Raise a fidelity mismatch when the evidence claim is stronger than the harness, for example:
- 'real DB integration' while repository is mocked;
- 'transaction correctness' under a harness that wraps the whole test and prevents observing real commit behavior;
- 'browser compatibility' from a DOM simulator only;
- 'external API compatibility' from a hand-written stub without contract verification;
- 'E2E' while a central application boundary is replaced by a fake and the claim depends on that boundary.

Do not penalize lower-fidelity tests merely for being lower fidelity. They can be the correct, cheapest detector for the claim.
