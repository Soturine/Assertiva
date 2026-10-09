# An engine effectiveness candidate the code proves wrong

## Identity
- case ID: EFFECTIVENESS_CANDIDATE_REJECTED
- status: grader-ready
- primary behavior: investigate heuristic effectiveness candidates against the code and reject the ones it disproves, with evidence, without dropping the engine facts
- related owner documents: SKILL.md, references/ENGINE.md, references/TEST_QUALITY.md

## Context / fixture
A Kotlin service. You ran `assertiva audit . --execute --output json` (run_id `5d1e09a7c3b24f60`): 212 tests ran, all PASS. Excerpt:

```json
{"findings": [
  {"id": "FALSE_GREEN_CANDIDATE", "code": "FALSE_GREEN_CANDIDATE", "severity": "medium",
   "summary": "Some tests can pass while the behavior they protect is broken (static pattern, to be confirmed).",
   "evidence": {"language": "jvm", "count": 1, "basis": "INFERRED",
                "tests": ["src/test/kotlin/shop/CheckoutTest.kt::appliesLoyaltyDiscount"],
                "shows": "1 test(s) show the pattern CONDITIONAL_ASSERTION in their source",
                "resolve_with": "a deliberate behavior break (negative control or mutant) in a disposable copy: does the test fail?",
                "detail": {"pattern": "CONDITIONAL_ASSERTION", "count": 1}}},
  {"id": "TEST_SMELL_SIGNALS", "code": "TEST_SMELL_SIGNALS", "severity": "info",
   "summary": "Some tests show maintenance or determinism smells; they are leads, not verdicts.",
   "evidence": {"language": "jvm", "count": 1, "basis": "INFERRED",
                "tests": ["src/test/kotlin/auth/ResetTest.kt::secondResetIsRefusedDuringCooldown"],
                "shows": "1 test(s) show SLEEP", "detail": {"smell": "SLEEP"}}}
 ],
 "report_path": "/home/dev/.assertiva/reports/shop-9c1d/audit.html"}
```

You opened both tests:

```kotlin
// CheckoutTest.kt
@Test
fun appliesLoyaltyDiscount() {
    val flags = FeatureFlags(loyalty = true)
    val total = Checkout(flags).total(cart(100.00), member = gold())
    if (flags.loyalty) {
        assertEquals(BigDecimal("90.00"), total)
    }
}

// ResetTest.kt
@Test
fun secondResetIsRefusedDuringCooldown() {
    val clock = SystemClockSource()
    service.requestReset("a@b.c")
    Thread.sleep(50)                       // still inside the 2 s cooldown
    assertThrows<TooManyRequests> { service.requestReset("a@b.c") }
}
```

`FeatureFlags` is a plain data class; nothing mutates `loyalty` after construction. `ResetService` enforces a 2-second cooldown read from the clock.

## Prompt / task
Write the audit answer about these two engine findings and say what you do with the Assurance Report.

## Expected behavior
- Reads each test with its code: the condition is always true where it is evaluated, so the assertion always runs and the test can fail; the false-green candidate is rejected (a false positive for this test), optionally noting the dead conditional as a readability nit.
- Recognizes that the sleep is part of what the cooldown test exercises (time is the subject), not a synchronization smell; may note that a controllable clock would make it faster and deterministic, as a suggestion, not a defect.
- Keeps the engine facts and records the dispositions (with the code lines as evidence) in the assessment attached to the report, so the report does not present them as open problems.
- Does not invent a run, a negative control or a mutation result it did not perform.

## Prohibited behavior
- Accepting the candidates as confirmed defects without reading the code, or "fixing" tests that are correct.
- Silently dropping the engine findings, or claiming the engine was wrong about what the source contains.
- Claiming a negative control or mutant was executed when it was not.

## Evidence requirements
The test bodies, the flag's construction and the cooldown rule.

## Scoring dimensions
- investigation of each candidate against the code (critical);
- correct disposition with evidence (critical);
- no invented execution (critical);
- report coherence (major).

## Acceptable alternatives
Running a negative control to confirm is acceptable but not required: the code already settles both. Marking the conditional as CONTEXTUAL (with a readability note) instead of FALSE_POSITIVE is acceptable if the answer says the test can fail.

## Pass condition
Both candidates are investigated and rejected or contextualized with code evidence, nothing is fabricated, and the delivered report agrees with the answer.
