# Semantic UI and Browser Test Assurance Research — 2026-10-02

**Status:** dated external evidence.  
**Purpose:** record current ecosystem evidence behind Assertiva's semantic UI/browser assurance model without turning one tool's conventions into universal policy.

## Sources reviewed

### Playwright — locators
https://playwright.dev/docs/locators

Observed:
- current Playwright documentation recommends built-in user-facing locators such as role, text and label;
- `getByTestId` is explicitly supported as a resilient test contract;
- the documentation warns that long CSS/XPath chains can be tied to DOM implementation and become unstable;
- therefore Assertiva should not simplify the rule to "semantic locator always good, test ID always bad". Both are valid under different contracts.

### Playwright — ARIA snapshots
https://playwright.dev/docs/aria-snapshots

Observed:
- Playwright can serialize accessibility-tree-oriented role/name/state structure into ARIA snapshots;
- these snapshots create a semantic regression surface distinct from pixel screenshots;
- snapshot authority/update provenance remains a separate concern.

### Playwright — accessibility testing
https://playwright.dev/docs/accessibility-testing

Observed:
- Playwright documents integration with `@axe-core/playwright`;
- its documentation explicitly states that automated checks catch only some accessibility problems and recommends combining automation with manual assessment and inclusive user testing;
- therefore "zero violations" must remain a scoped result, not a full-accessibility or conformance verdict.

### Playwright — tracing
https://playwright.dev/docs/trace-viewer

Observed:
- Playwright recommends trace capture on first retry in CI as a useful cost/evidence tradeoff;
- retries and traces are diagnostic mechanisms, not proof that nondeterminism is fixed.

### Testing Library — query priority
https://testing-library.com/docs/queries/about/
https://testing-library.com/docs/queries/byrole/

Observed:
- Testing Library prioritizes queries that resemble user interaction, with `getByRole` strongly preferred in many cases;
- it recognizes implicit roles from native HTML;
- performance and special-case tradeoffs exist;
- this supports a user-contract-first heuristic, not a mandatory universal locator ranking.

### W3C WAI-ARIA APG
https://www.w3.org/WAI/ARIA/apg/practices/read-me-first/
https://www.w3.org/WAI/ARIA/apg/practices/
https://www.w3.org/WAI/ARIA/apg/practices/structural-roles/

Observed:
- incorrect ARIA can misrepresent the interface;
- a role implies expected behavior, including keyboard interaction for custom widgets;
- native HTML semantics should be used where they already provide equivalent semantics;
- therefore Assertiva must reject cargo-cult ARIA added only to satisfy automation.

### W3C WCAG / conformance
https://www.w3.org/WAI/standards-guidelines/wcag/
https://www.w3.org/WAI/WCAG22/Understanding/conformance

Observed:
- WCAG conformance is tied to success criteria and requires a combination of automated testing and human evaluation;
- W3C encourages use of the latest WCAG 2 version for current work;
- automated rule-engine output must not be promoted into a broader conformance claim.

### Android Jetpack Compose semantics
https://developer.android.com/develop/ui/compose/accessibility/semantics

Observed:
- Compose semantics provide meaning/role/state to accessibility services;
- the same semantics tree is also used by Compose testing APIs to find nodes, interact and assert state;
- therefore the underlying Assertiva concept is cross-platform: semantic interface contracts are not inherently ARIA or browser-specific.

## Reusable conclusions promoted

1. **User-contract locators are generally more refactor-resilient when the product exposes a stable semantic identity.**
2. **Explicit test IDs are legitimate contracts**, particularly when semantic identity is ambiguous, localized, intentionally unstable, or not what the test owns.
3. **Long positional CSS/XPath chains are implementation-coupling signals**, not automatic defects.
4. **Accessibility semantics are product behavior**, not test-only metadata.
5. **Visual, semantic, keyboard/focus, interaction, storage/network and persistence evidence are independent surfaces.**
6. **Semantic/ARIA snapshots are useful but inherit ordinary snapshot authority/update risks.**
7. **Automated accessibility scanners provide scoped evidence, not complete accessibility or WCAG proof.**
8. **Retries/timeouts must preserve first-failure evidence and cannot silently redefine "fixed".**
9. **The core model must be portable beyond web**, with framework adapters translating semantic role/name/state/test identity into the normalized evidence model.

## Non-promotions

Assertiva does not adopt:
- Playwright as a mandatory runner;
- `getByRole` as a universal locator requirement;
- test IDs as either universally preferred or universally discouraged;
- axe as an accessibility certification mechanism;
- one mutation score or selector-resilience score;
- ARIA as the generic name for semantic UI testing;
- a requirement to structurally mutate every UI test.

## Revalidation triggers

Revisit this record when:
- Playwright materially changes locator/ARIA snapshot behavior;
- W3C accessibility guidance materially changes;
- Compose semantics/testing APIs materially change;
- a first-party Assertiva browser adapter is implemented;
- empirical dogfood shows the current locator/structural-mutation heuristics create material false positives.
