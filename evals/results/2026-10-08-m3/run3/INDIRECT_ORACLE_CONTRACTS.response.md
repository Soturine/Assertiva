# WEAK_ORACLE_SIGNAL Disposition

## 1. `test_building_a_client_does_not_connect` — Signal: NO_ASSERTION

**Disposition: FALSE_POSITIVE**

**Rationale:** The test has a real, strong oracle via the mock's `side_effect=AssertionError`. According to TEST_QUALITY.md, "a double whose side effect fails the test on a forbidden call is a real oracle." The contract is "building a client does not connect," and the side effect ensures that if `PaymentsClient` constructor calls `socket.create_connection`, the test fails with `AssertionError`. This is an explicit guard on the seam; the absence of an `assert` statement in the test body does not weaken it.

**Evidence:** Mock configured with `side_effect=AssertionError("connected at construction")`; TEST_QUALITY.md confirms side-effect guards are real oracles.

---

## 2. `test_refund_of_a_settled_payment_is_accepted` — Signal: NO_ASSERTION

**Disposition: PARTIAL**

**Rationale:** The test has a functional but implicit oracle: the test passes only if `refund()` does not raise `RefundRejected`. This satisfies the "must not raise" contract from TEST_QUALITY.md. However, the test is incomplete: it verifies only the exception contract, not the return value or state changes that "accepted" might require. Since `refund()` returns `None`, a complete test should assert the return value or verify side effects (persisted state, etc.) in addition to catching the absence of an exception.

**Evidence:** Test body has no explicit assertions; oracle is entirely implicit and exception-based. The function is documented to raise `RefundRejected` on rule violation, but the test does not verify what happens after acceptance (e.g., confirmation, timestamp, idempotency).

---

## 3. `test_export_returns_rows` — Signal: EXISTENCE_ONLY

**Disposition: CONFIRMED**

**Rationale:** All three assertions check only existence via `assertIsNotNone`: `rows is not None`, `rows[0] is not None`, `rows[0]["total"] is not None`. These truthiness checks do not verify the actual values, data types, counts, column names, or relationships. According to TEST_QUALITY.md, "Truthiness, `is not None`... usually let wrong values pass." The test would pass if `rows` contains arbitrary or corrupted data as long as it is not None.

**Evidence:** Test assertions: three `assertIsNotNone` calls with no value assertions, schema checks, or expected-value comparisons.

---

## 4. `test_invalid_currency_is_rejected` — Signal: NO_ASSERTION

**Disposition: CONFIRMED**

**Rationale:** The test has no oracle at all. The `try/except/pass` structure ensures the test passes regardless of whether `charge()` raises an exception. If the call succeeds, no exception is caught, the except block does not run, and the test passes. If the call raises an exception, the except block catches it and does nothing (`pass`), and the test still passes. The contract "invalid currency is rejected" is not checked; the test cannot fail.

**Evidence:** The except block contains only `pass`; no assertion precedes or follows the try/except block.

