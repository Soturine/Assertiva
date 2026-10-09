# Assessment: Would your tests catch a wrong discount amount?

## Answer: Unknown — current evidence is insufficient to answer this question with confidence.

### What the static evidence shows:

**The three direct discount tests are weak on amount verification:**
- `test_member_discount`, `test_bulk_discount`, and `test_stacked_discounts` are flagged by the engine as WEAK_ORACLE_SIGNAL with TRUTHY_ONLY signals.
- They call `apply_discount(...)` and `assert result` — meaning they check only that a result exists (truthiness), not that the discount amount is *correct*.
- A test that only asserts truthiness would **not catch** a wrong discount amount; it would pass as long as the result is not None, empty, or falsy, regardless of the numeric value.

**The 61 indirect tests are unknown:**
- Checkout, invoices, and refunds tests call `apply_discount` indirectly through `checkout()`.
- Some assert totals, but you haven't reviewed which ones exercise which discount branch or what exactly they verify.
- We cannot conclude whether these tests check the actual discount amounts or only that totals are computed.

**100% line coverage does not prove amount checks:**
- Line coverage of `pricing/discounts.py` means the code executes, not that the behavior is verified.
- A discount calculation could be broken (wrong formula, wrong multiplier, wrong rounding) and 100% coverage would remain green if the tests only check for the presence of a result.

**No mutation evidence:**
- Without mutation testing, we cannot confirm that tests would detect a broken calculation.
- A mutation that changes a discount formula (e.g., `0.1` to `0.15`) would go undetected if the test only asserts truthiness.

### What to do next:

To definitively answer whether your tests catch a wrong discount amount, use a **negative control** — a deliberate behavior-breaking edit in a disposable copy:

1. Run `assertiva improve .` to measure the baseline in isolation and prepare a candidate workspace.
2. Create a negative control: deliberately break the discount amount (e.g., change `amount * 0.1` to `amount * 0.2` or `amount * 0.05`).
3. Run the suite against this broken code and observe whether tests fail.
4. If tests pass despite the broken discount, the suite does not catch the defect.
5. If tests fail, identify which tests caught it — those are your actual guards.

This approach is safe (runs in a disposable copy), direct (answers the exact question), and will give you concrete evidence: which tests (if any) would catch a wrong discount amount, and which defects would slip through.

The engine references show this is exactly what negative controls are designed for: "a deliberate behavior-breaking edit in a disposable copy [that the tests claiming a contract] must detect."

Without this evidence, a claim that "100% coverage and all green" means your discount calculations are safe would rest on the weak tests you've already identified. Run the negative control.
