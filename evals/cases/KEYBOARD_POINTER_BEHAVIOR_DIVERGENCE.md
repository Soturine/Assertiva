# Eval Case — Keyboard and pointer behavior diverge

## Identity
- case ID: **keyboard-pointer-behavior-divergence**
- title: Keyboard and pointer behavior diverge
- status: grader-ready
- primary behavior: treat input modalities and focus behavior as distinct observation surfaces
- related owners: [Semantic UI and Browser Assurance](../../docs/SEMANTIC_UI_AND_BROWSER_ASSURANCE.md); [Test Harness and Fidelity](../../docs/TEST_HARNESS_AND_FIDELITY.md)

## Context / fixture
A custom interactive control works when clicked with a mouse and pointer-based E2E tests pass. The control cannot be reached correctly by keyboard, activation keys do not trigger the same action, and focus becomes lost after an overlay closes.

## Prompt / task
Assess the adequacy of the current tests and define the smallest useful evidence needed to verify the interaction contract.

## Expected behavior
- distinguish pointer interaction from keyboard/focus evidence;
- inspect the intended platform semantics and required input modalities;
- identify reachability, activation, focus transition and resulting state/effect as separately observable;
- recommend the smallest keyboard/focus reproducer plus composition-level verification where the claim depends on the full journey;
- preserve pointer tests as valid evidence for the pointer path;
- verify equivalent required effects rather than assuming identical event sequences.

## Prohibited behavior
- do not claim interaction correctness from pointer success alone;
- do not add only a role/ARIA attribute while leaving keyboard behavior broken;
- do not require identical low-level events between pointer and keyboard if the user-visible contract is equivalent;
- do not claim a screen-reader defect unless evidence supports that claim.

## Evidence requirements
Control semantics, focusability/order, keyboard actions, pointer actions, state/effect outcomes, overlay/dialog focus transitions and the actual platform/browser harness.

## Scoring dimensions
- **Critical — modality evidence separation:** 2/1/0.
- **Critical — focus/keyboard contract recognition:** 2/1/0.
- **Major — preserves valid pointer evidence:** 2/1/0.
- **Major — proportionate reproducer/composition strategy:** 2/1/0.
- A 0 on either critical dimension fails the case.

## Acceptable alternatives
Browser keyboard automation, native UI automation, focus instrumentation, accessibility-tree action checks, component-level interaction tests, or representative manual evidence are acceptable if they observe the same contract.

## Pass condition
The response identifies the keyboard/focus gap without discarding the valid pointer evidence and defines a proportionate way to prove the required interaction outcome.
