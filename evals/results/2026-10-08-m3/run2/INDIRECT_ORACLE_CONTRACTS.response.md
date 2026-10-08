# Assessment: Dispositions for WEAK_ORACLE_SIGNAL Candidates

## Summary
Four candidates flagged for weak or missing assertions. After review: one is a false positive (implicit oracle present), one partially holds with an incomplete contract, one confirmed as existence-only, and one confirmed as broken.

## Dispositions

### 1. test_building_a_client_does_not_connect
**Disposition:** FALSE_POSITIVE

**Rationale:** The test does have an implicit assertion. By patching `socket.create_connection` with `side_effect=AssertionError("connected at construction")`, the test ensures that if the constructor calls that function, an exception is raised. If the constructor completes without triggering the patch, the test passes. The oracle is "the constructor does not call socket.create_connection during initialization."

**Basis:** INFERRED (reading the patch mechanism and control flow)

**Evidence:**
- Test code: `mock.patch("payments.client.socket.create_connection", side_effect=AssertionError(...))`
- The side effect is the oracle mechanism; the test implicitly asserts it is not triggered

---

### 2. test_refund_of_a_settled_payment_is_accepted
**Disposition:** PARTIAL

**Rationale:** The test has an implicit oracle (it relies on `refund()` raising `RefundRejected` for violations), so the NO_ASSERTION signal is incomplete. However, the oracle is weak because it only verifies that no rule violation occurred—it does not verify the acceptance contract itself. The test name "is_accepted" suggests the contract should include checking that the refund was processed, recorded, or altered state. With `refund()` returning `None`, there is no return value to assert. State changes (ledger, balance, refund record) are not checked.

**Basis:** INFERRED (from the `refund()` signature and semantics described)

**Evidence:**
- `refund()` raises `RefundRejected` on rule violations
- `refund()` returns `None`
- Test calls `refund(settled_payment(), amount=10)` with no assertion or follow-up state check
- Acceptance contract is unverified

**Priority:** high

---

### 3. test_export_returns_rows
**Disposition:** CONFIRMED

**Rationale:** All three assertions (`assertIsNotNone(rows)`, `assertIsNotNone(rows[0])`, `assertIsNotNone(rows[0]["total"])`) check only for existence, not value. The test verifies that the export returns something, something with at least one row, and that row has a "total" field—but not whether those values are correct, complete, or match the input month. This is a classic existence-only oracle.

**Basis:** OBSERVED (reading the assertion calls directly)

**Evidence:**
- Line 1: `self.assertIsNotNone(rows)` — checks only that rows is not null
- Line 2: `self.assertIsNotNone(rows[0])` — checks only that at least one row exists
- Line 3: `self.assertIsNotNone(rows[0]["total"])` — checks only that the field is present
- No assertions on row count, value correctness, or filtering by month

**Priority:** high

---

### 4. test_invalid_currency_is_rejected
**Disposition:** CONFIRMED

**Rationale:** The test attempts to catch an exception but does not assert one was raised. The `try/except Exception: pass` pattern passes the test whether `charge(10, "XXX")` raises an exception or returns normally. The oracle is inverted: a correct test would call `self.assertRaises(...)` or verify the exception type and details. As written, the test is broken.

**Basis:** OBSERVED (reading the exception handling)

**Evidence:**
- Test code: `try: charge(10, "XXX"); except Exception: pass`
- No assertion that an exception occurred
- Test passes either way (exception or no exception)
- Test name "is_rejected" is not verified by any assertion

**Priority:** high
