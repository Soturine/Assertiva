# Disposition: WEAK_ORACLE_SIGNAL candidates

## test_building_a_client_does_not_connect
**Signal:** NO_ASSERTION  
**Disposition:** FALSE_POSITIVE  
**Rationale:** The test uses `side_effect=AssertionError("connected at construction")` as an oracle. This is a real assertion mechanism (per TEST_QUALITY.md: "a double whose side effect fails the test on a forbidden call is a real oracle"). If the constructor calls `socket.create_connection`, the AssertionError is raised and the test fails. The contract "must not connect" is enforced through the double's side effect. The test is valid.

---

## test_refund_of_a_settled_payment_is_accepted
**Signal:** NO_ASSERTION  
**Disposition:** CONFIRMED  
**Rationale:** The test has only an implicit "no exception raised" assertion. While this verifies that all rule violations in `refund()` did not trigger (since it raises `RefundRejected` on violation), the test does not verify state changes or side effects. The assertion surface is incomplete: the contract "is_accepted" suggests verification of acceptance state, but the test only verifies no exception occurred. It does not assert that the refund was actually applied, recorded, or affected any persistent state. Weak oracle for the stated contract.

---

## test_export_returns_rows
**Signal:** EXISTENCE_ONLY  
**Disposition:** CONFIRMED  
**Rationale:** The test asserts only that values exist (not None). Three levels of nested existence are checked (`rows`, `rows[0]`, `rows[0]["total"]`), but no assertions verify correctness, content, structure, or actual values. The oracle checks only presence, not shape or semantics. This is weak for any contract beyond "function returns something."

---

## test_invalid_currency_is_rejected
**Signal:** NO_ASSERTION  
**Disposition:** CONFIRMED  
**Rationale:** The test has no effective assertion. It calls `charge(10, "XXX")` inside a try-except that catches `Exception` and performs no action (`pass`). Whether `charge()` raises an exception or returns normally, the test passes. There is no way for this test to fail. No contract is enforced.

---

## Summary
- **FALSE_POSITIVE:** 1 (side_effect oracle is valid)
- **CONFIRMED:** 3 (implicit/incomplete/absent assertions)
