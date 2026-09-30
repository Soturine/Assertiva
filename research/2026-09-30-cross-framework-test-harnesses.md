# Cross-Framework Test Harness Research — 2026-09-30

Status: dated research evidence. Canonical policy lives in docs/.

## Django and DRF

Sources:
- https://docs.djangoproject.com/en/6.1/topics/testing/tools/
- https://docs.djangoproject.com/en/6.1/topics/testing/overview/
- https://www.django-rest-framework.org/api-guide/testing/
- https://github.com/luizomf/curso-django-projeto1

Observed patterns:
- unittest.TestCase, Django SimpleTestCase, TestCase, TransactionTestCase and LiveServerTestCase differ in DB permissions, reset/transaction behavior and live-server fidelity;
- Django TestCase transaction wrapping is fast but cannot prove some real commit/rollback/select-for-update semantics that require TransactionTestCase;
- Django-specific assertions expose distinct surfaces: templates, redirects, HTML, JSON, field output;
- DRF has APIClient/RequestsClient and TestCase-family variants for different service boundaries;
- real project tests combine routing resolution, templates, context, rendered content, model validation, GET/POST/PATCH, JWT ownership rules, Selenium and branch coverage.

Transferable rule: test class name is an adapter hint; actual harness dimensions and observation surfaces determine the claim.

## Python fixtures and patching

Sources:
- https://docs.pytest.org/en/stable/explanation/fixtures.html
- https://docs.pytest.org/en/stable/example/parametrize.html
- https://docs.python.org/3.14/library/unittest.mock.html

Observed patterns:
- fixtures compose explicit setup/teardown and have scopes from per-test to session;
- parameterized cases receive stable case IDs useful for replay/selection;
- patch must replace the name where the SUT looks it up, not blindly the definition site;
- autospec/spec can constrain doubles against the real API.

## Spring and ASP.NET Core

Sources:
- https://docs.spring.io/spring-framework/reference/testing/mockmvc/overview.html
- https://docs.spring.io/spring-framework/reference/testing/webtestclient.html
- https://learn.microsoft.com/en-us/aspnet/core/test/integration-tests?view=aspnetcore-10.0

Observed patterns:
- Spring MockMvc runs the MVC request pipeline without a live HTTP server;
- WebTestClient can use mock/in-process bindings or a real live server through a similar assertion API;
- ASP.NET WebApplicationFactory uses a test host/TestServer and can replace infrastructure;
- Microsoft notes that EF Core in-memory testing is limited and SQLite can be a more realistic in-memory relational option.

Transferable rule: the same request/assertion API can sit on harnesses with different fidelity. Record the backing boundary, not only the API used by the test.

## Disposable infrastructure and service virtualization

Sources:
- https://testcontainers.com/getting-started/
- https://wiremock.org/
- https://docs.pact.io/blog/2026/09/14/pact-open-source-update-sept-2026

Observed patterns:
- Testcontainers spans multiple languages and offers disposable real service/database engines;
- service virtualization preserves protocol/client behavior while controlling responses/faults;
- contract testing increasingly covers synchronous and asynchronous/message transports.

Transferable rule: integration fidelity includes protocol and dependency semantics, not merely whether two source modules are called.

## Frontend and browser

Sources:
- https://storybook.js.org/docs/9/writing-tests/integrations/vitest-addon
- https://storybook.js.org/docs/9/writing-tests/interaction-testing
- https://playwright.dev/
- https://docs.cypress.io/app/tooling/ai-skills

Observed patterns:
- component render, interaction, accessibility and visual testing are independent evidence dimensions;
- real-browser component tests occupy a useful middle between DOM simulation and E2E;
- browser matrices create environment-specific invocations;
- traces/retries and live-session tooling make run freshness/attempt identity important.

## Other ecosystems

Sources:
- https://go.dev/wiki/TableDrivenTests
- https://go.dev/doc/security/fuzz/
- https://doc.rust-lang.org/book/ch11-03-test-organization.html
- https://www.nexte.st/
- https://docs.phpunit.de/en/12.5/
- https://rspec.info/features/

Observed patterns:
- Go table-driven tests and native fuzzing reinforce definition-vs-case/corpus identity;
- Rust separates unit, integration and documentation tests, while nextest adds record/replay/JUnit/partitioning but currently handles doctests separately;
- PHPUnit data providers report individual datasets and can flag tests with no assertions/expectations as risky;
- RSpec request specs exercise Rails full-stack request behavior, while system specs use browser automation; verifying doubles protect mock API compatibility.

## Result

Admitted into Assertiva:
- Test Harness and Fidelity Model;
- Assertions/Oracle/Observation Surface model;
- Test Data/Fixture lifecycle model;
- Test Double/Patch/Virtualization model;
- Web/API/UI layered evidence model.

No ecosystem-specific class or library becomes a universal requirement.
