# Audit Answer: Two Engine Findings

## Summary

Both findings are contextual and do not indicate test weakness. The false-green candidate is a false positive (the condition is always true, so the assertion always runs); the sleep smell is not a defect (elapsed time is the contract being tested, not a substitute for waiting on a condition).

## Engine Findings

### 1. FALSE_GREEN_CANDIDATE: `appliesLoyaltyDiscount` (CONDITIONAL_ASSERTION)

**Evidence**: The test asserts inside an `if (flags.loyalty)` block. The engine flags this pattern as a conditional assertion that could silently pass if the condition is false.

**Disposition**: FALSE_POSITIVE

**Rationale**: `FeatureFlags` is a plain immutable data class. The `loyalty` field is set once at construction to the value passed to the constructor. In this test, `loyalty` is explicitly set to `true` when the object is created (`FeatureFlags(loyalty = true)`). The condition `if (flags.loyalty)` is therefore *always true* at the assertion site. The assertion always runs; nothing ever skips it.

The engine's heuristic correctly identified the syntactic pattern of a conditional assertion, but the pattern is harmless here because the condition cannot be false at runtime. The test cannot pass while the behavior breaks.

### 2. TEST_SMELL_SIGNALS: `secondResetIsRefusedDuringCooldown` (SLEEP)

**Evidence**: The test calls `Thread.sleep(50)` to wait for a state change, which the engine flags as a smell (often a sign that the test waits instead of checking a condition).

**Disposition**: CONTEXTUAL

**Rationale**: According to Assertiva's TEST_QUALITY.md, "a sleep is a smell when it stands in for waiting on a condition; when elapsed time is the behavior (cooldowns, expiry, rate limits, debounce, timeouts) it is the stimulus."

Here, elapsed time *is* the behavior: the service enforces a 2-second cooldown, and the test verifies that a second reset within that window is rejected. The sleep is the stimulus that places the second request inside the cooldown period. This is not waiting for a condition to become true (which would hide a race); it is exercising the behavior of time-dependent rejection.

Additionally, the test uses `SystemClockSource()`, which is typically an injectable clock. If this allows deterministic time control in tests (stepping the clock rather than sleeping), it would be an efficiency suggestion, not a defect. As written, the test is correct.

## Assurance Report

The audit produced one run (run_id `5d1e09a7c3b24f60`). I will attach an assessment disposition to the latest audit output via the engine:

```
assertiva audit . --assessment <assessment-file>
```

where the assessment file will name both findings and record:
- `FALSE_GREEN_CANDIDATE` / `appliesLoyaltyDiscount` → `FALSE_POSITIVE`
- `TEST_SMELL_SIGNALS` / `secondResetIsRefusedDuringCooldown` → `CONTEXTUAL` (priority: info)

This preserves the raw evidence (the engine's static analysis) while recording the human judgment that neither finding represents a real test weakness in this context.

## What is protected

- The loyalty discount calculation (if loyalty is true, total is discounted) is asserted directly and cannot be false while the test passes.
- The 2-second reset cooldown is exercised and verified; the test will fail if the service allows a second reset within the window.

## Unknowns

None material. The full suite (212 tests, all PASS) shows the happy path is covered. Candidates for deeper inspection would be whether the tests exercise all paths through checkout (partial discounts, zero balances, refunds) and whether reset recovery after cooldown is tested; the engine's findings do not raise those.
