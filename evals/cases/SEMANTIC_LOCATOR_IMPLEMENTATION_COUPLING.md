# Semantic locator vs implementation coupling

## Context
A browser test uses a deep positional selector for a control that already exposes a stable user-facing semantic identity. A harmless DOM refactor adds a wrapper and the test fails while the user-visible behavior remains unchanged.

## Expected
- classify the failure as possible test implementation coupling rather than immediate product regression;
- recover the intended product contract before changing the locator;
- prefer semantic role/name, label, stable domain identity, or an explicit test contract when appropriate;
- preserve CSS/structural assertions when structure itself is the behavior under test;
- do not add ARIA solely to manufacture a convenient locator.

## Prohibited
- claim every CSS/XPath locator is bad;
- claim every `data-testid` is inferior to semantic queries;
- report a product regression solely from a positional-selector failure.
