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

## Semantic UI contracts and locator strategy

For UI tests, identify the user-observable contract before choosing a locator. Accessibility semantics are product behavior; they are not merely automation hooks.

Prefer, where appropriate:
1. semantic role + accessible name, associated label, or equivalent platform semantics;
2. stable visible/domain identity;
3. explicit test contract such as `data-testid` when product semantics are insufficient or ambiguous;
4. stable domain attributes that are intentionally part of the contract;
5. incidental DOM structure, positional CSS, `nth-child`, or absolute XPath only when structure itself is what the test intends to observe.

This is not a universal ranking score. A CSS/class assertion is valid when styling/class output is itself the behavior. A test ID may be the cleanest contract for repeated/virtualized/otherwise ambiguous elements. Do not add ARIA solely to manufacture a convenient test locator.

Useful semantic evidence includes:
- role and accessible name;
- selected/expanded/checked/pressed/disabled/invalid/busy state;
- keyboard activation and navigation;
- focus entry/order/containment/restore;
- status/error announcements;
- landmarks and reading structure where relevant.

Browser frameworks may expose role/label locators, accessibility/ARIA snapshots, accessibility-tree inspection, traces, screenshots/video, network events and storage state. Keep those evidence surfaces distinct.

### Structural robustness

Where proportionate, test whether a UI test survives a non-behavioral refactor such as wrapper insertion, class renaming, or internal layout composition while the same product contract remains. Failure under such a change is evidence of possible implementation coupling, not automatically a product regression.

The inverse is also important: a material role/name/state/keyboard/focus/user-visible behavior change should be detectable even when screenshots remain unchanged.

### Automated accessibility scanners

Rule engines such as axe-style scanners are valuable detectors. A scan with zero violations is **not** proof of complete accessibility conformance or successful use with representative assistive technology. Preserve the exact ruleset/version/scope and combine with semantic, keyboard/focus, and manual evidence when the claim requires it.

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

## Snapshot and golden evidence

Snapshots are change detectors, not self-authorizing oracles. Preserve why the baseline is authoritative, what changed, and who/what accepted the update.

A bulk/automatic snapshot refresh after failure must not be reported as a fix without evidence that the new output is intended. Broad snapshots that mix unrelated state can have poor review signal; narrower semantic, visual-region, or domain assertions may be stronger.

## Retry, timeout, and browser flake evidence

Preserve attempt identity and first-failure evidence. A passing retry does not erase the original failure.

Timeout increases may be valid when an authoritative latency/performance envelope changed, but are not a default repair for races, missing synchronization, asynchronous completion, environment instability, or slow regressions.

## Visual vs accessibility vs interaction

These are complementary, not substitutes:
- visual comparison detects appearance differences;
- accessibility checks detect a subset of semantic/WCAG violations;
- interaction tests prove behavior under actions;
- DOM/role assertions prove semantic structure.

A visually identical UI can have broken accessibility; a semantically correct DOM can have a layout regression.

## Matrix evidence

Browser/device/runtime/configuration matrices create distinct invocations. Preserve the matrix dimension in test identity instead of collapsing 'same test passed somewhere' into universal compatibility.
