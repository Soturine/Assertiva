# Assertiva Audit Findings: Payments Library

## Summary

Engine reported: 812 tests passed, 0 failed; line coverage 91%. Two engine findings (one medium). However, semantic audit of the refund subsystem reveals a critical gap in test oracle strength and integration fidelity that line coverage does not detect.

## Deterministic Evidence (E0/E1)

- **Run result**: 812 passed, 0 failed (deterministic fact from engine execution)
- **Line coverage**: 91% (deterministic metric, with caveat below)
- **Test count for `refund()` subsystem**: 14 tests (deterministic count)
- **Mock usage pattern**: 100% of refund tests use mocks for both `gateway` and `ledger` (deterministic static observation)

## Declared/Configuration Evidence (E2)

- **CI environment**: ubuntu only (CI single OS; declared in configuration)
- **Artifact exclusion**: `src/payments/README.md` and `src/payments/py.typed.bak` not in wheel (medium severity; deterministic omission)

## Critical Semantic Findings (E4)

### 1. **Oracle Weakness: Ledger Entry Not Verified** [HIGH PRIORITY]

**Evidence**:
- `refund(charge, amount)` is documented to record a ledger entry as part of its contract.
- All 14 refund tests mock `ledger` and assert **only** `gateway.refund.assert_called_once()`.
- **No test verifies the ledger entry was created, updated, or contains the correct remaining balance.**
- Partial refund behavior (remaining balance requirement) is **not observable in any test**.

**Risk**:
- A refund that calls gateway but fails to record ledger, or records incorrect remaining balance, would pass all 14 tests.
- Bugs in ledger logic (off-by-one, sign error, wrong account) are undetected by current suite.
- The ledger behavior is integration-critical for financial correctness and audit trails.

**Classification**: This is weak oracle strength (E4 inference) hidden by high line coverage. Coverage does not prove oracle adequacy; ledger code may be exercised but its effects never validated.

### 2. **Integration Fidelity Gap: No Real Ledger Under Test** [HIGH PRIORITY]

**Evidence**:
- Both `gateway` and `ledger` are mocked uniformly across all 14 tests.
- No test uses a real/in-memory ledger to verify state transitions.
- The claim "partial refunds must keep the remaining balance" cannot be verified by code inspection alone—it requires observing ledger state after refund.

**Risk**:
- Integration bugs between refund logic and ledger contract are not detectable without at least one in-memory/real ledger invocation.
- A refund that passes the mocked `gateway.refund.assert_called_once()` but mutates ledger in an unintended way (e.g., deduplicates entries, resets balance instead of decrementing) would remain hidden.

**Classification**: This is a test-harness-fidelity issue (reference: Assertiva skill docstring "Never infer test strength from a framework class, file suffix, or label alone. When integration/UI/database fidelity matters…"). Excessive mocking is a test smell when the boundary under test (ledger state change) is not integrated.

### 3. **Test-Specific Evidence Gaps**

**Negative/Boundary Cases**:
- No observable test for partial refund with remaining balance verification (e.g., refund 50 of 100, assert balance now 50).
- No test for edge cases: refund amount = 0, refund amount > charge amount, refund of already-refunded charge.

**Parametrized Invocations**:
- No evidence of parametrized test cases exercising the full domain of refund amounts and charge states.

## Unknowns (E4)

- Whether the ledger-entry omission is intentional (e.g., ledger is tested elsewhere as a unit and refund tests intentionally isolate gateway logic) or accidental.
- Whether a separate integration test file or E2E suite covers the ledger-refund interaction.

## Recommendations

### 1. **Add Real Ledger State Verification [CRITICAL]**
Add at least one refund test (or a parametrized case) that uses a real/in-memory ledger and asserts:
- Ledger entry exists after refund.
- Remaining balance is correct (charge_amount - refund_amount).
- Partial refunds preserve prior ledger history.

### 2. **Strengthen Oracle for Partial Refunds [CRITICAL]**
Parametrize refund tests to cover:
- Refund partial amounts (e.g., 50 of 100, 1 of 100).
- Assert remaining balance equals charge_amount - refund_amount.
- Assert ledger does not corrupt or re-initialize prior entries.

### 3. **Boundary Cases [MEDIUM]**
Add explicit test cases (not just coverage):
- Refund amount = 0 (should this fail, or succeed with no state change?).
- Refund amount > charge amount (invalid, should raise; verify exception and no ledger change).
- Refund of already-fully-refunded charge (double refund safety).

### 4. **Artifact Inclusion [MEDIUM]**
Include `src/payments/py.typed` (if intentional) or remove `py.typed.bak` from the source tree. (This is housekeeping, not functional.)

### 5. **Cross-Platform CI [LOW]**
Expand CI to test on Windows/macOS if the library targets Windows or macOS environments. (ubuntu-only is acceptable for server-side-only libraries; clarify the delivery model.)

## Conclusion

91% line coverage and 812 passing tests provide confidence that the happy path and gateway integration work as coded. However, the **ledger-entry behavior and partial-refund balance invariant are not proven by the current test suite**. The test oracle is strong for gateway calls but weak/absent for ledger effects. Add integration-level ledger verification before production release.
