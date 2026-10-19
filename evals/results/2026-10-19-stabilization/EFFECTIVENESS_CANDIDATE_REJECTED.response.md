# Audit answer: the two engine findings (run 5d1e09a7c3b24f60)

**Answer.** Neither finding shows a test that can stay green while its behavior is broken. The `FALSE_GREEN_CANDIDATE` on `CheckoutTest.appliesLoyaltyDiscount` is a false positive: its guard is always true, so the assertion always runs and fails if the discount breaks. The `TEST_SMELL_SIGNALS` (SLEEP) on `ResetTest.secondResetIsRefusedDuringCooldown` is contextual and low priority. The sleep is not the real risk; the test runs on wall-clock time and declares a clock it never uses. The 212 PASS outcomes are from the engine run; the conclusions below rest on reading the two tests, and no mutant or negative control was run.

## What green proves for these two tests

- **appliesLoyaltyDiscount**: at this revision, in this local run, a gold member's 100.00 cart with loyalty enabled totals 90.00. It does not prove the flag-off path, and it does not prove the discount for other members or amounts.
- **secondResetIsRefusedDuringCooldown**: in this run, a second reset about 50 ms after the first is refused with `TooManyRequests`. It does not prove the boundary after 2 s, and it depends on the real clock.

## Findings, ranked by consequence

1. **Cooldown test runs on real time and does not control its clock** (low). `val clock = SystemClockSource()` is unused in the shown body, and nothing shown passes it to `ResetService`. A stall longer than 2 s between the two requests would make the second request succeed and the test fail, with or without the sleep. Basis: OBSERVED in the shown code; whether the service uses an injected clock is UNKNOWN.
2. **Loyalty test has a redundant guard** (low). `if (flags.loyalty)` is always true because the data class is built with `loyalty = true` and never mutated. Harmless now, but the same shape would silently skip the assertion if the flag became mutable. Basis: OBSERVED.

## Engine findings: my dispositions

- **FALSE_GREEN_CANDIDATE (CONDITIONAL_ASSERTION, appliesLoyaltyDiscount): FALSE_POSITIVE**, reviewed 1 of 1. The condition is constant where it is evaluated, so the assertion is always reached. The oracle is a hand-computed 10 percent of 100.00, not derived from the code. The claim does not hold. The code reading settles it; a negative control (change the rate in a disposable copy and confirm the test fails) would confirm it by execution, and I did not run one.
- **TEST_SMELL_SIGNALS (SLEEP, secondResetIsRefusedDuringCooldown): CONTEXTUAL, priority low.** The sleep is present, but elapsed time inside the cooldown is part of the behavior, and 50 ms adds no flake risk by itself. The wall-clock dependency is the real concern, and it is recorded as finding 1.

## Unknowns

- Whether `ResetService` reads `SystemClockSource` or a clock injected elsewhere: its construction is not in the shown code.
- Whether any other test covers the loyalty flag-off path or the cooldown boundary after 2 s.
- Whether these tests ran on CI at HEAD: the run is local, and no CI run was provided, so no CI claim is made.

## Recommendations

- **appliesLoyaltyDiscount**: remove the `if` and assert unconditionally. If the flag-off behavior matters, add a test with `loyalty = false` that expects 100.00.
- **secondResetIsRefusedDuringCooldown**: if `ResetService` accepts a clock, inject the test clock, advance it by a fixed step under 2 s instead of `Thread.sleep(50)`, and use or delete the unused `clock`. Add a case that advances past 2 s and expects the reset to be accepted.

## Assurance Report

I wrote the assessment to `<scratchpad>\evals073\EFFECTIVENESS_CANDIDATE_REJECTED\assessment.json`, with the same dispositions and scope as this answer. I did not attach it: this task allows reading the context only, and attaching requires running `assertiva audit <project> --assessment <file>`. That call executes nothing, re-renders the report, and refuses if the project changed since run 5d1e09a7c3b24f60. It should be run from a session that is allowed to run commands. Until then, the report shows the engine findings without these dispositions. I did not edit or render the HTML.

Assurance Report: /home/dev/.assertiva/reports/shop-9c1d/audit.html
