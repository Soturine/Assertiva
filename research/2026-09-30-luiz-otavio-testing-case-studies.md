# Luiz Otávio Testing Case Studies — 2026-09-30

**Status:** concrete examples from public course repositories. They are useful evidence, not universal standards.

## Repositories reviewed

- https://github.com/luizomf/curso-django-projeto1
- https://github.com/luizomf/tests-nextjs-vitest-playwright
- https://github.com/luizomf/typescript-jest-test
- https://github.com/luizomf/vitest-vite-and-react-boilerplate
- https://github.com/luizomf/python-tests
- https://github.com/luizomf/react-18-vite-storybook-jest-styled-components

## Django course: what the suite demonstrates

The Django project contains several complementary observation surfaces rather than only unit-style return assertions.

### Routing and view ownership

Examples use `reverse()` and `resolve()` to verify that a named URL resolves to the intended class-based view. This is distinct from merely checking HTTP 200.

**Transferable pattern:** route/dispatcher identity is its own contract surface. Equivalent concepts exist in Spring routing, ASP.NET endpoint routing, Rails routes, frontend routers, RPC dispatch and custom command registries.

### Request/response behavior

Tests use the Django test client for GET/POST and DRF API tests for GET/POST/PATCH. They verify:
- status codes;
- authentication/authorization;
- ownership restrictions;
- pagination/filtering;
- accepted/forbidden methods;
- response payload fields.

**Strength:** demonstrates that HTTP method, auth and response contract are separate from direct function testing.

**Risk if copied blindly:** a status-only assertion can be too weak when persistence, events, payload schema or side effects matter.

### Template, content and context

The suite checks:
- template selection;
- response body text;
- `response.context` contents;
- empty-state rendering.

These are deliberately different evidence surfaces.

**Transferable pattern:** renderer/template selection, server-side view-model/context and final rendered content should not be collapsed into one generic “view test.”

### Forms and UX metadata

The registration-form tests parameterize:
- placeholder;
- help text;
- label;
- required/min/max behavior;
- password confirmation;
- e-mail uniqueness.

**Strength:** demonstrates data-driven testing and treats user-facing form behavior as testable.

**Tradeoff:** exact label/help/error copy is appropriate only when wording is a real product/localization contract. If copy is intentionally free to change, exact string assertions create refactor noise. Assertiva should infer the authority before calling such tests good or brittle.

### Structured validation

Model tests deliberately exceed `max_length` and expect `ValidationError`. Form integration tests inspect field-specific errors.

**Transferable pattern:** invalid input is a first-class contract. Modern Assertiva generalizes this into error type/code/path/context/status rather than relying only on exception text.

### Data setup

The project uses a reusable `RecipeMixin` with `make_category`, `make_author`, `make_recipe` and batch helpers instead of relying exclusively on static Django fixture files.

**Strength:** test intent can vary only relevant fields and generate related objects quickly.

**Risk:** permissive helper defaults can hide behavior. In this project `make_recipe` explicitly sets `is_published=True`, so a separate no-default construction is needed to test the model's real default. This is a useful Assertiva rule: factory defaults can mask production defaults and impossible states.

### Patching

Pagination tests patch `PER_PAGE` to make small deterministic datasets exercise multi-page behavior.

**Good seam:** configuration is controlled without replacing the behavior under test.

**General rule:** patching is good when it controls a peripheral dependency/configuration needed for a scenario; it is harmful when it replaces the exact boundary the test claims to integrate.

### Functional/browser tests

`StaticLiveServerTestCase` plus Selenium verifies:
- live local server;
- browser form interactions;
- visible error messages;
- search;
- pagination;
- successful registration.

**Strength:** verifies real browser/server composition beyond Django's in-process client.

**Limitations:** browser E2E is slower and less precise for domain localization. A Chrome-only harness would not prove cross-browser compatibility. Fixed sleeps, if used as synchronization, are weaker than condition/event-based waits.

### Coverage configuration

The course enables branch coverage in `.coveragerc`.

**Strength:** branch coverage is more informative than line-only coverage.

**Limit:** branch coverage still does not prove assertion/oracle adequacy.

## Modern Vitest/Playwright project

The newer `tests-nextjs-vitest-playwright` project adds patterns that reinforce Assertiva's cross-framework model.

### Unit/component assertions

React Testing Library tests use semantic queries, `userEvent`, disabled/read-only/error states, labels and accessibility attributes.

One Button suite explicitly acknowledges that CSS-class assertions are implementation-oriented but justified because visual variant classes are part of the intended behavior.

**Transferable rule:** implementation-detail testing is not automatically wrong. It is wrong when it protects a private representation that should be free to refactor. If CSS classes/design tokens themselves are the contract, exact assertions can be appropriate.

### Mocking application actions

A server/action test mocks `next/cache` and checks `revalidatePath` calls while delegating use-case results.

**Strength:** isolates an application orchestration boundary and verifies contractual side effects.

**Limit:** this cannot prove real Next cache behavior; claim scope must stay at orchestration.

### Repository integration

Drizzle repository tests clean state before/after and verify ordering, uniqueness/conflict behavior, create/remove results and database-facing behavior.

**Transferable rule:** repository integration tests should preserve the actual storage engine/adapter semantics when the claim concerns constraints, ordering, transaction or query behavior.

### Playwright E2E

The project configures Chromium, Firefox and WebKit projects, CI retries and `trace: on-first-retry`. Tests cover rendering, creation, trim behavior, validation, editing, persistence, routing/history and localStorage.

**Strong patterns for Assertiva:**
- environment/browser is an invocation dimension;
- retry attempts must retain first failure;
- trace-on-first-retry exemplifies progressive diagnostics;
- browser-visible state and storage persistence are separate assertions.

### Vitest configuration

The test config distinguishes `.spec` and `.test` conventions for unit/integration, disables file parallelism due to SQLite unique-constraint collision concerns, and configures V8 coverage exclusions.

**Transferable lessons:**
- file suffix is project-declared metadata, not universal truth;
- concurrency configuration is part of test evidence;
- coverage exclusion policy changes the denominator and must be auditable.

## Advantages of these course/project styles

- concrete examples across multiple layers;
- clear test names and behavior-focused cases;
- parameterization reduces repetition;
- helpers make setup readable;
- Django tests show route/view/template/context/content/database distinctions;
- modern TS project separates component, domain, repository and E2E concerns;
- browser projects exercise actual user interactions;
- patch/mocks demonstrate controllable seams;
- coverage and CI concepts are visible rather than hidden.

## Disadvantages / risks if copied mechanically

- course examples can optimize teaching clarity rather than industrial scale;
- exact copy/message/class assertions may over-couple tests when those details are not contractual;
- helper/factory defaults can hide real model defaults;
- test names such as unit/integration do not guarantee fidelity;
- mock-heavy tests can prove orchestration while leaving real integrations untested;
- E2E suites can become slow/flaky if they absorb every edge case;
- retries can hide flakes if the original failure is not preserved;
- coverage percentage can become a vanity metric;
- browser/live-server tests need explicit matrix/environment claims;
- old course dependency versions are not a current framework recommendation.

## Assertiva admission

The case studies directly support these canonical models:
- test definition vs invocation;
- Test Harness/Fidelity;
- Assertions/Oracles/Observation Surfaces;
- Fixture/Factory/Data lifecycle;
- Test Double/Patch/Virtualization;
- Web/API/UI layered testing;
- Progressive Diagnostic Escalation;
- Refactor Confidence.

They do not justify hardcoding Django, Vitest, Playwright, Selenium, parameterized, Drizzle or any specific assertion API into the core.
