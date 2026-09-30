# Assertions, Oracles, and Observation Surfaces

An assertion is useful only relative to the behavior or contract it is meant to observe.

## Observation surfaces

Normalize assertions by what they observe, not by framework method name:

- return/value and deep structure;
- exception/error/warning contract;
- state transition and invariant;
- persistence/readback/transaction effect;
- collaborator interaction or side-effect call;
- emitted event/message/job/notification;
- HTTP/RPC status, headers, content type, cookies, body and schema;
- routing/URL resolution/redirect/history;
- template/view/component selection;
- render context/model/view-data;
- rendered content/DOM/accessibility tree;
- visual pixels/layout/reference image;
- browser/storage/session/cache state;
- filesystem/network/device state;
- logs/metrics/traces/telemetry;
- timing/resource/performance distribution;
- authorization/security control and forbidden/no-op outcome.

## Claim-to-observation mapping

A strong audit asks: what defective behavior would still satisfy this exact assertion?

Examples:
- status 200 can be a valid smoke assertion, but does not prove persistence or business invariants;
- assertTemplateUsed proves which template rendered, not that the context contains the correct objects;
- response context proves server-side render inputs, not necessarily final visible DOM;
- rendered HTML/DOM proves output but may not prove persistence or emitted events;
- mock call verification proves a collaborator interaction, not that the real collaborator works;
- visual snapshot proves appearance at a state, not interaction semantics or accessibility;
- exact exception message may be brittle when stable error type/code/path is the real contract.

## Django example as a portable mapping

Patterns from real Django suites map cleanly to generic observation surfaces:

- reverse + resolve -> routing identity;
- test client GET/POST/PATCH -> request/transport behavior through the framework dispatcher;
- status_code -> protocol status;
- assertTemplateUsed -> renderer/template selection;
- response.context -> render-context/model data;
- response.content / assertContains -> rendered body/content;
- form.errors / ValidationError -> structured validation contract;
- ORM query/readback -> persistence effect;
- login/session state -> authentication state;
- LiveServer + Selenium -> browser-visible composition.

The same categories apply to Spring model/view assertions, ASP.NET Razor/view data, Rails request/system specs, React Testing Library, Playwright, Cypress, native mobile UI tests, or custom protocols.

## Assertion quality

Do not score quality by raw assertion count or variety alone.

Prefer:
- independent expected values/oracles;
- exact semantics where exactness matters;
- subset/semantic matching where unrelated fields legitimately vary;
- negative assertions for forbidden/no-op outcomes;
- state/effect assertions when a method's contract is side-effectful;
- structural assertions that expose meaningful differences;
- parameterized cases for independent boundary/equivalence classes.

Watch for:
- tautological/self-referential assertions;
- expected values calculated by the same logic under test;
- only-presence/truthiness checks where exact behavior matters;
- assertions against implementation details that should be free to change during refactor;
- giant snapshots with weak review signal;
- assertions never reached due to async/exception control-flow mistakes.

## Warnings and non-fatal signals

Warnings, deprecations, expected-failure/xfail states, skips and incomplete accessibility findings are evidence states, not noise to erase. Preserve policy and counts because a green exit code may coexist with accumulating future-breakage signals.
