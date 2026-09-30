# Web, API, UI, and Browser Testing

Web testing has several independent observation layers. Do not call all of them 'functional' or 'integration' without describing the harness.

## Request/API surfaces

Exercise applicable methods and protocol behavior:
- GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS and protocol-specific operations;
- path/query/body/form/multipart encoding;
- content negotiation/content type;
- headers/cookies/session/CSRF/CORS;
- authentication, authorization and ownership;
- success, invalid, forbidden, unauthenticated, missing, conflict, rate-limit and server-failure paths;
- pagination/filter/search/sort;
- idempotency/retry/concurrency;
- redirects and canonical URLs;
- schema/serialization and backward compatibility;
- side effects, persistence and emitted events.

HTTP status alone is often only one part of the oracle.

## Server-side rendering

For MVC/template systems distinguish:
- URL/routing resolution;
- controller/view/handler selection;
- template/component selection;
- render context/model/view-data;
- final content/DOM;
- redirects/messages/session state;
- persistence and side effects.

These are different claims and can have different fastest detectors.

## Component/UI testing

Useful surfaces include:
- render/smoke;
- semantic role/name/label;
- props/state variations;
- user interaction and resulting state;
- accessibility semantics and automated rule checks;
- visual/layout regression;
- responsive/theme/font-scale/locale states;
- network/error/loading/empty states.

Simulated DOM environments are fast but do not fully represent browser layout/engine behavior. Real-browser component testing raises fidelity at additional cost.

## Browser/E2E

Browser tests can verify:
- navigation/history/deep links;
- full forms and validation;
- auth/session/storage;
- browser persistence/local storage/indexed DB where applicable;
- cross-page workflows;
- cross-browser/device projects;
- real client-server composition.

Keep E2E focused on composition/user journeys. Use lower layers for exhaustive domain partitions when they provide the same behavioral detector more cheaply.

## Visual vs accessibility vs interaction

These are complementary, not substitutes:
- visual comparison detects appearance differences;
- accessibility checks detect a subset of semantic/WCAG violations;
- interaction tests prove behavior under actions;
- DOM/role assertions prove semantic structure.

A visually identical UI can have broken accessibility; a semantically correct DOM can have a layout regression.

## Matrix evidence

Browser/device/runtime/configuration matrices create distinct invocations. Preserve the matrix dimension in test identity instead of collapsing 'same test passed somewhere' into universal compatibility.
