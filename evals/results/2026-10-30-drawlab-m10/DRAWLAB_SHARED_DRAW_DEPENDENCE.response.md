# What the `p_union` test proves

**It proves only that `p_union` computes `1 - (1 - p1)(1 - p2)` from the module's own single-ticket probabilities. It does not prove that this is the probability that at least one of the two tickets wins. It is not a strong oracle.** The expected value is the implementation's formula restated, and that formula is wrong in general for tickets on the same draw.

What this rests on: only the context I was given. I have the implementation formula, the test's assertion, the 100 % coverage figure, and the fact that the two test tickets share 3 of their 6 numbers. I read no source and ran nothing.

## Findings

### 1. The oracle is derived from the code under test (high, OBSERVED from the assertion)
- The expected value `1 - (1 - p1) * (1 - p2)` is the same expression `p_union` evaluates.
- `p1` and `p2` come from the same module's single-ticket function.
- So the test can only fail if the implementation stops matching its own formula, for example through a refactor slip. It cannot fail if the formula itself is wrong. Any error in the modelling assumption is shared by the code and the test.
- The test is an implementation-consistency check, not a check of the probability.

### 2. The formula assumes independence, which does not hold on one draw (high, INFERRED from probability)
- `1 - ∏(1 - p_i)` is P(at least one) **only when the win events are independent**.
- Tickets evaluated against **the same draw** are dependent:
  - **Overlapping tickets** (like the test's pair, 3 of 6 numbers shared) are positively correlated. A draw that hits the shared numbers helps both. The true P(both win) is above `p1·p2`, so the true union is **below** what the formula returns: the formula overstates the chance.
  - **Disjoint or different tickets on an exact-match tier** (for example, the jackpot: all 6 numbers) are mutually exclusive, because only one combination is drawn. Then P(both) = 0 and the true union is `p1 + p2`, slightly **above** the formula. The error is tiny in that case, but it is still an error.
- The exact quantity is `p1 + p2 - P(both win)`, or inclusion–exclusion / direct counting over the draw space for n tickets.
- Which prize tier "win" means is not stated in the context. The size and direction of the error depend on it, but the dependence holds for every tier.

### 3. The test's own data is the case where the formula is most wrong (high, INFERRED)
- The two tickets share 3 numbers, which makes the dependence material, especially for lower tiers that a 3-number overlap feeds into directly.
- An independent oracle would very likely give a different value from the one asserted. The test does not detect this, because it asserts the formula instead of the probability.

### 4. 100 % coverage adds nothing here (medium, OBSERVED + INFERRED)
- Coverage shows that every line of `odds.py` executed. It does not show that any result was checked against an independent value.
- A wrong model at full line coverage is the classic false green.

## What it does protect
- Arithmetic regressions in the product expression, for example `1 - p1 * p2` written by mistake. The test catches those, but only for this one formula.
- Nothing about whether the result is correct for real tickets.

## Evidence that would settle it

1. **An independent oracle by enumeration.**
   - On a small lottery (for example, pick 3 of 8 numbers, or 6 of 15), enumerate every possible draw.
   - Count the draws in which at least one ticket wins, and divide by the number of draws. This is cheap and exact, and it does not use the module's formula.
   - Do it for overlapping tickets, disjoint tickets and identical tickets. For identical tickets the union must equal `p1`. The current formula gives `2p1 - p1²`, which makes a clear witness of the bug.
2. **Hand-computed contract values** for the real game. Use combinatorial counting of the joint win event for a specific pair with 3 shared numbers, and assert `p_union` against that number with a tolerance justified by floating point only.
3. **A negative control or mutant in a disposable copy.** Replace the body with the exact inclusion–exclusion count. The current test would then *fail*, even though the code became correct. That shows the test pins the formula, not the behavior.
4. **Optional property checks**, all of which fail under the current formula:
   - `p_union([b, b]) == p(b)`
   - `max(p_i) ≤ p_union ≤ min(1, Σp_i)`
   - for mutually exclusive tickets, `p_union == Σp_i`.

Until an independent oracle like this exists, whether `p_union` is correct for same-draw tickets is **UNKNOWN as tested**. From the reasoning above, I would expect it to be **incorrect** whenever the tickets' win events are dependent, which is every case on a single draw. This is an inference, and the enumeration in step 1 would confirm or refute it.
