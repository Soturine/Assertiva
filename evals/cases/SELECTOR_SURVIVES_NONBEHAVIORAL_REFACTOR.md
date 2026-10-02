# Eval Case — Selector survives non-behavioral refactor

## Identity
- case ID: **selector-survives-nonbehavioral-refactor**
- title: Selector survives non-behavioral refactor
- status: grader-ready
- primary behavior: use structural mutation as a bounded challenge to UI test implementation coupling
- related owners: [Semantic UI and Browser Assurance](../../docs/SEMANTIC_UI_AND_BROWSER_ASSURANCE.md); [Refactor Safety](../../docs/REFACTOR_SAFETY.md)

## Context / fixture
A test suite is being evaluated before refactoring. A controlled mutation inserts harmless wrappers and renames internal classes while preserving the accessible/native semantic identity, visible/domain identity, action, resulting state, required appearance and persistence/network effect.

## Prompt / task
Interpret which failing tests reveal implementation coupling and which failures may represent legitimate structural or visual contracts.

## Expected behavior
- verify that the mutation actually preserves the relevant product contract before interpreting failures;
- use the mutation as evidence about test coupling, not as an automatic pass/fail criterion;
- identify tests that fail only because incidental structure changed;
- keep structural/visual-contract tests separate from behavior-contract tests;
- preserve uncertainty when the mutation may have changed a material behavior;
- treat a surviving locator as positive evidence, not proof of universal robustness.

## Prohibited behavior
- do not require every UI test to survive structural change;
- do not treat every failure as a product regression;
- do not call the mutation non-behavioral without evidence that material behavior was preserved;
- do not assign an arbitrary global selector-resilience score from one mutation.

## Evidence requirements
Mutation diff, pre/post semantic identity, visible/domain identity, interaction outcome, relevant visual contract, persistence/network effects, failing/passing locator identities and harness/runtime.

## Scoring dimensions
- **Critical — mutation validity/contract preservation:** 2/1/0.
- **Critical — coupling-vs-legitimate-contract classification:** 2/1/0.
- **Major — uncertainty/claim discipline:** 2/1/0.
- **Major — proportional use of mutation evidence:** 2/1/0.
- A 0 on either critical dimension fails the case.

## Acceptable alternatives
Manual controlled refactor, AST/DOM mutation tooling, component-boundary substitution, synthetic fixture variants, or another challenge is acceptable if it preserves the same claimed user behavior.

## Pass condition
The response uses the refactor challenge to identify likely implementation coupling while proving or explicitly questioning the assumption that the product contract remained unchanged.
