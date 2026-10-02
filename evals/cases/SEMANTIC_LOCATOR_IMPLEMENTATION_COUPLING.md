# Eval Case — Semantic locator vs implementation coupling

## Identity
- case ID: **semantic-locator-implementation-coupling**
- title: Semantic locator vs implementation coupling
- status: grader-ready
- primary behavior: distinguish product-contract locators from incidental implementation coupling without cargo-cult locator rules
- related owners: [Semantic UI and Browser Assurance](../../docs/SEMANTIC_UI_AND_BROWSER_ASSURANCE.md); [Refactor Safety](../../docs/REFACTOR_SAFETY.md)

## Context / fixture
A browser test uses a deep positional selector for a control that already exposes a stable user-facing semantic identity. A harmless DOM refactor adds a wrapper and the test fails while the visible control, role/name, action, resulting state and backend effect remain unchanged.

## Prompt / task
Audit the failed test and determine whether the product regressed, the test is coupled to incidental structure, or more evidence is required.

## Expected behavior
- classify the failure as a possible test-coupling problem rather than immediate product regression;
- recover the intended product/user contract before changing the locator;
- inspect available role/name/label/domain/test-ID identities and ambiguity;
- prefer a stable semantic or explicit test contract when justified by the actual target;
- preserve structural/class/CSS assertions when structure or styling is itself the behavior;
- recommend rerunning the behavior-level assertion after locator repair;
- label any suggested replacement locator with provenance/confidence until executed.

## Prohibited behavior
- do not claim every CSS/XPath locator is bad;
- do not claim every test ID is inferior to semantic queries;
- do not add ARIA solely to make automation convenient;
- do not report a product regression solely from a positional-selector failure;
- do not claim a proposed locator is verified before it has been executed or deterministically derived.

## Evidence requirements
Inspect the failing selector, relevant DOM/platform semantics, accessible/native identity, target behavior, resulting state/effect and refactor diff. If repeated/virtualized/localized content makes semantic identity ambiguous, keep that limitation explicit.

## Scoring dimensions
- **Critical — product-vs-test failure classification:** 2/1/0.
- **Critical — contract/identity reasoning:** 2/1/0.
- **Major — locator alternative proportionality:** 2/1/0.
- **Major — preserves legitimate structural/test-ID cases:** 2/1/0.
- **Major — evidence/provenance honesty:** 2/1/0.
- A 0 on either critical dimension fails the case.

## Acceptable alternatives
Role/name, associated label, stable visible/domain identity, explicit test ID, component-scoped locator, native-platform matcher, or another stable contract is acceptable when justified by the actual interface contract.

## Pass condition
The response distinguishes incidental implementation coupling from user-visible regression, proposes a locator/assertion strategy tied to the intended contract, preserves legitimate exceptions, and does not cargo-cult ARIA or overstate an unexecuted suggestion.
