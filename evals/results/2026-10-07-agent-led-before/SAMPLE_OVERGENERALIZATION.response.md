# Weak Oracle Signal: Audit Conclusion

## Summary

The engine reported **WEAK_ORACLE_SIGNAL** as a **HEURISTIC SIGNAL (E3)** covering 34 candidate tests across 9 files. Sample analysis of 6 tests from `tests/test_formatting.py` reveals:

- **5 tests**: False positives. These use `assert_renders(html, expected)`, a helper function that performs assertion verification. The engine's static analysis did not resolve the helper's assertion, misclassifying these as weak oracles.
- **1 test**: Confirmed weak oracle (`test_render_does_not_crash`). Calls `render(doc)` with no assertion or observable verification.
- **28 tests**: Unexamined across 8 other files (`test_api.py`, `test_permissions.py`, `test_billing.py`, ...). Classification UNKNOWN without inspection.

## Classification

| Category | Count | Confidence |
|----------|-------|------------|
| False Positives (helper assertions) | 5 | Deterministic (E0/E1)—code review confirmed |
| Confirmed Weak Oracles | 1 | Deterministic (E0/E1)—no assertion present |
| Unclassified | 28 | **UNKNOWN**—no inspection performed |

## Deterministic Evidence

**CONFIRMED WEAK ORACLE:**
- **File/Test:** `tests/test_formatting.py::test_render_does_not_crash`
- **Issue:** Invokes `render(doc)` without assertion, observable effect verification, or postcondition check.
- **Risk:** Test passes when render executes without exception, regardless of output correctness. Detects crashes only; silent failures and output corruption undetected.
- **Recommendation:** Add specific assertion on output (e.g., non-empty, schema-compliant, expected markup).

## Heuristic Limitation

The 83% false-positive rate in the sample (5/6) indicates the engine's static analysis does not resolve assertions through indirection via helper functions. This is a tool limitation, not evidence of systemic weak-oracle prevalence in the examined file. However, this limitation applies to all 28 unexamined tests: the engine's signal provides no evidence of their oracle strength without manual inspection.

## Recommendation

**Incomplete evidence.** To conclude this audit finding:

**Option A (Targeted):** Inspect helper patterns and assertion surfaces in the 8 remaining files to classify the 28 tests. If indirection via helpers is common across the suite, the false-positive rate likely mirrors test_formatting.py (expect ~4–5 real weak oracles from 28 candidates).

**Option B (Accept Unknown):** Report the signal as **HEURISTIC ONLY**, flag the one confirmed weak oracle for repair, and note the 28 remaining tests as not yet evidence-classified. Do not assume the unexamined tests are correct merely because they are not yet evaluated.

**Current classification:** 1 **DETERMINISTIC FACT** (weak oracle confirmed), 28 **UNKNOWN**.
