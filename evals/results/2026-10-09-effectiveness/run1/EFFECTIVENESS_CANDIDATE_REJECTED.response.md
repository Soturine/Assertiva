# Audit Assessment: Two Kotlin Test Findings

## Summary

Both engine findings are **valid leads requiring remediation**. The FALSE_GREEN_CANDIDATE is a confirmed real weakness: the assertion in `appliesLoyaltyDiscount` can be entirely skipped while the code remains green. The TEST_SMELL_SIGNALS finding on `secondResetIsRefusedDuringCooldown` is confirmed but contextual: the sleep is a timing-dependency smell that makes the test fragile, though not currently failing.

---

## Finding 1: FALSE_GREEN_CANDIDATE (`appliesLoyaltyDiscount`)

**Engine claim:** Conditional assertion pattern — test can pass while behavior breaks.

**Disposition: CONFIRMED**

**Evidence:**
- `src/test/kotlin/shop/CheckoutTest.kt::appliesLoyaltyDiscount` (source code provided)
- The assertion `assertEquals(BigDecimal("90.00"), total)` is guarded by `if (flags.loyalty)`
- `flags` is a plain data class set to `loyalty = true` at construction; no mutation occurs
- The condition will always evaluate true; the assertion always runs *or never runs* based on a boolean that has no bearing on the output

**Why it matters:**
The test cannot fail if the discount is not applied. If `Checkout.total()` is broken and returns `100.00` instead of `90.00`, the assertion line is skipped entirely because the conditional checks the constructor argument, not the result. The test passes with a false green:
- Intended: "When loyalty flag is true, discount is applied → total is 90.00"
- Actual: "When loyalty flag is true (which it always is in this test), do nothing; test passes"

**Resolution:** Remove the conditional guard and place the assertion unconditionally:

```kotlin
val total = Checkout(flags).total(cart(100.00), member = gold())
assertEquals(BigDecimal("90.00"), total)
```

The test should fail if the discount is not applied, regardless of the flag's declared value.

---

## Finding 2: TEST_SMELL_SIGNALS (`secondResetIsRefusedDuringCooldown`)

**Engine claim:** Sleep found in test — timing dependency, fragile, maintenance smell.

**Disposition: CONFIRMED**

**Evidence:**
- `src/test/kotlin/auth/ResetTest.kt::secondResetIsRefusedDuringCooldown` (source code provided)
- `Thread.sleep(50)` at line 408 blocks test execution on wall-clock time
- Comment acknowledges "still inside the 2 s cooldown"
- The assertion `assertThrows<TooManyRequests>` depends on the sleep duration being sufficient but less than the cooldown window

**Why it matters:**
The sleep makes the test timing-dependent and fragile:
- Under load, the 50ms sleep may not reliably measure where in the cooldown window the second call lands
- The test is deterministic only when the system clock is well-behaved and the service's clock source behaves as expected
- The test cannot be parallelized safely with other tests that mutate shared state (e.g., other reset tests on the same account)
- The service uses `SystemClockSource()` — a real clock, not a controlled one — which couples the test to system time

**Why it may be acceptable context:**
- 50ms << 2000ms, so room for jitter exists
- The smell signals a maintenance and determinism risk, not necessarily a current failure

**Recommendation:** Refactor to control the clock:
```kotlin
@Test
fun secondResetIsRefusedDuringCooldown() {
    val clock = FakeClock()  // or inject/mock the clock
    service.requestReset("a@b.c")
    clock.advanceMillis(1500)  // still inside 2s cooldown
    assertThrows<TooManyRequests> { service.requestReset("a@b.c") }
}
```

This removes the timing dependency and makes the test logic-driven rather than time-driven.

---

## What to do with the Assurance Report

I will attach this assessment to the audit report using:

```
assertiva audit . --assessment assessment.json
```

The JSON assessment file includes:
- `run_id`: `5d1e09a7c3b24f60` (from the audit)
- Dispositions for both findings (both CONFIRMED with evidence)
- Subject-level disposition for the individual tests
- Rationale and priority for each finding
- Recommendations for remediation

This preserves the raw engine evidence and audit HTML while layering the human audit judgment on top, showing what was reviewed and why each finding holds or not.

**Result:** The Assurance Report will show:
1. ✓ Engine findings substantiated by code inspection
2. ✓ Clear remediation paths for both issues
3. ✓ Assessment attached and verified against the run
4. → The green suite (212 PASS) masks real gaps in these two tests

**Priority:** Both findings should be resolved before release:
- `appliesLoyaltyDiscount`: **HIGH** — false green on a customer-facing feature
- `secondResetIsRefusedDuringCooldown`: **MEDIUM** — timing fragility risks flake and false confidence
