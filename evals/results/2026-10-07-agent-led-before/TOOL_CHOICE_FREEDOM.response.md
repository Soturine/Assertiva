# Assertiva Evaluation: Is `test_parse_due_date` Weak?

## Answer
Yes, the test is weak. Multiple failure modes exist that the test would not detect.

## Evidence Classification
**HEURISTIC SIGNAL** (E3) — static inspection of test assertions and oracle strength, not runtime execution.

## Findings

### Critical: Weak Oracle — Assertion Roulette
The test assertions do not verify actual behavior:

```python
assert parse_due_date("2026-03-01")
assert parse_due_date("01/03/2026")
```

These assertions only check truthiness (that a date object is returned). They do not verify:
- The **value** of the returned date
- Whether the date was parsed correctly in the intended format

**Risk:** A function that always returns today's date, or returns an arbitrary fixed date, or swaps month/day logic, or ignores the format parameter entirely would pass these assertions.

### Critical: No Negative Path Coverage
The function's contract explicitly states: "rejects anything else with ValueError". The test does not verify this behavior at all.

**Missing test cases:**
- Invalid format: `"invalid"`
- Partial format: `"2026-03"`
- Wrong delimiter: `"2026/03/01"`
- Null or empty string: `""`
- Boundary dates: `"2026-13-01"` (invalid month)

**Risk:** The function could be silently altered to accept invalid dates, and the test would not catch it.

### Moderate: No Boundary Case Coverage
Date parsing is vulnerable to off-by-one errors in day/month extraction, and year rollover edge cases.

**Missing coverage:**
- Day boundaries: `"2026-02-28"`, `"2026-03-01"` (leap-year boundary)
- Month boundaries: `"2026-12-31"`, `"2026-01-01"`
- Format-specific: `"31/12/2026"` (DD/MM/YYYY with day > 12)

## Classification
This test exhibits **assertion roulette** and **no assertion / effectively no observable verification** (from TEST_SMELLS.md section of the Skill). The oracle is insufficient to detect material changes to the function under test.

## Recommendation
Before deploying `parse_due_date`, add tests that:
1. Assert the exact returned date values, not just truthiness
2. Verify ValueError is raised for invalid inputs
3. Cover boundary dates and format-specific edge cases
