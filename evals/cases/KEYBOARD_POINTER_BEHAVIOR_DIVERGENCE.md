# Keyboard and pointer behavior diverge

## Context
A custom control works when clicked with a mouse but cannot be reached or activated correctly from the keyboard. Pointer E2E tests pass.

## Expected
- distinguish pointer-interaction evidence from keyboard/focus evidence;
- identify the user-visible interaction contract and the platform semantics expected for the control;
- require the smallest suitable keyboard/focus reproducer plus composition-level verification where needed.

## Prohibited
- claim interaction correctness from pointer success alone;
- add ARIA without fixing the actual keyboard/focus behavior.
