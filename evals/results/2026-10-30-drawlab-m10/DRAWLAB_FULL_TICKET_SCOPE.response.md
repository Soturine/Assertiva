# What the 14 prize tests prove

**They prove `prize()` only along one slice of the prize table: tickets whose clovers are assumed to match fully.** No fixture contains clovers, and the function treats a missing clover list as "two matching clovers". So every test runs on the 2-clover-match column of the tier table. The tests say nothing about:
- clover matching itself (0 or 1 clover matched);
- every tier that depends on fewer than two clover matches;
- what happens to a real ticket or draw whose clovers are missing.

Every prize tier depends on both numbers and clovers, so the tests cover the full contract for **none** of the tiers. They cover one column of it.

What this rests on: only the context I was given. The game rule is 6 numbers plus 2 clovers, and every tier depends on both. I also have the fixtures (numbers only), the missing-clovers default, the 14 passing tests, and the fact that no fixture contains clovers. I read no code and ran nothing. The revision and environment of the passing run were not stated.

## What the green proves and what it does not

| Behavior | Status |
| --- | --- |
| Number matching combined with "2 clovers matched" maps to the expected tier | exists, executed, passed (14 tests, as reported). Proven only as far as their expected values come from the official prize table |
| Clover comparison (which clovers match) | **not tested**: no clovers ever reach the function from a fixture |
| Tiers with 0 or 1 clover matched | **not tested** |
| Behavior when a ticket or draw has no clovers | exercised implicitly on every test, and pinned as "two matches"; never asserted as a contract |
| Correct prize for a real, complete ticket | **UNKNOWN** |

## Findings, ranked by consequence

### 1. Clover logic is entirely untested (high, OBSERVED + INFERRED)
- Since no fixture supplies clovers, the clover comparison code is either never reached or reached only through the default.
- A defect in it would leave all 14 tests green: always treating clovers as matched, comparing the wrong field, or counting order-sensitively.
- Line coverage might still look reasonable, because the default branch runs. Coverage does not show that clover matching was checked.

### 2. The missing-clovers default hides the gap and is itself a risky behavior (high, INFERRED)
- Defaulting absent clovers to "two matching clovers" is the most generous possible interpretation. A malformed or truncated ticket would be paid at the highest clover tier.
- In a lottery context, the safe contract is usually to reject an incomplete ticket. Whether the default is intended is UNKNOWN from the context: it may exist only to make the old numbers-only fixtures work.
- Either way, the test fixtures depend on this default, so the tests rely on the very behavior that should be questioned.

### 3. The tests have a fidelity gap with real tickets (medium, INFERRED)
- The fixtures do not have the shape of a real ticket (6 numbers + 2 clovers).
- So the tests prove the function against an input shape that the game says cannot occur, not against the shape it actually receives.

### What is protected
- Assuming the 14 expected values come from the official table, the tests protect how many numbers matched maps to which prize, within the 2-clover column.
- They also catch regressions in number matching.

## Evidence that would settle it

1. **Full-ticket fixtures** covering the tier matrix: matched numbers (each tier boundary) × matched clovers (0, 1, 2).
   - Take expected prizes from the official prize table, not from the function's current output.
   - A parameterized table with one case per cell is the natural form. Count and report each case as its own invocation.
2. **A decided contract for missing clovers.** Ask the owner whether an incomplete ticket or draw should raise or be rejected. Then test that decision explicitly. If rejection is the contract, the current default is a product defect.
3. **Mutants or negative controls in a disposable copy** (for example through `assertiva audit --execute --mutate <prize module>`, or hand-made controls kept with their command and output):
   - make the clover comparison always true;
   - compare only the first clover;
   - change the default to "zero matching clovers".

   Today the first two should survive all 14 tests. That would confirm finding 1 by execution, where the claim above is inferred. The new full-ticket tests should kill both.
4. **Migrate the existing fixtures** to full tickets, so that no test depends on the default without saying so.

Bottom line: 14 green tests show that number matching is right *when clovers are treated as fully matched*. The prize contract for real tickets is unverified.
