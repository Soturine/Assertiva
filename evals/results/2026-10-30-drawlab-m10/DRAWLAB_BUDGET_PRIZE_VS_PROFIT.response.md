# Does the green suite support "maximizes your chance of coming out ahead"?

**No.** The green suite proves something narrower and different: for one R$ 10 budget, the recommended portfolio has a probability above 0.4 of winning *any* prize. "Coming out ahead" means total prizes greater than the R$ 10.00 spent. Nothing in the suite checks that, and nothing checks that the recommendation is the *maximum* of anything. Whether the README claim is true is **UNKNOWN**. The test does not make it false, and it does not support it.

What this rests on: only the context I was given. The suite is green on HEAD (run observed, same SHA, clean tree). I have the assertion in `test_best_portfolio_wins_often`, the README wording, the R$ 2.50 cheapest tier, the R$ 10.00 cost, and the statement that no test computes P(prizes > spend). I read no files and ran nothing.

## What the green proves and what it does not

| Step | Status | Basis |
| --- | --- | --- |
| Exists: a test of the budget recommendation | yes, one test: `test_budget.py::test_best_portfolio_wins_often` | OBSERVED (context) |
| Selected and executed | yes, in the suite run on HEAD | OBSERVED (run, same SHA, clean tree) |
| Outcome | passed: `p_any_prize` observed at 0.41, threshold 0.4 | OBSERVED |
| Proven: P(any prize) > 0.4 for a R$ 10 budget | yes, as far as `p_any_prize` is computed correctly | OBSERVED / INFERRED |
| Proven: the recommendation maximizes anything | no: the test has no comparison against other portfolios | INFERRED from the assertion |
| Proven: P(total prizes > R$ 10) is high, or is maximized | no: no test computes it | OBSERVED (context) |

## Findings, ranked by consequence

### 1. The test checks a different quantity from the one the README promises (high, INFERRED from cited facts)
- `p_any_prize` is P(total prize > 0). The README promises P(total prize > cost), with cost = R$ 10.00.
- The cheapest tier pays R$ 2.50. A ticket that wins only that tier still leaves the buyer R$ 7.50 down, and so do up to three such wins. Many outcomes that count as "won a prize" are net losses.
- So P(come out ahead) ≤ P(any prize), and it can be much lower. The 0.41 is an upper bound on the claimed quantity, not an estimate of it.
- A portfolio tuned for `p_any_prize` tends to spread the budget over many cheap tickets to collect small prizes. That can *lower* the chance of net profit. Optimizing one metric can work against the other.
- Consequence: the README could be false while this test stays green forever. This is a false green for the claim, though the test may be correct for what it actually asserts.

### 2. Nothing tests the "maximizes" part (high, INFERRED)
- A threshold (`> 0.4`) on one portfolio says nothing about optimality. A recommender that returns a mediocre portfolio scoring 0.41 passes. So does a better one at 0.6.
- No test compares the recommendation against other portfolios with the same budget.

### 3. The objective the optimizer actually uses is unknown (medium, UNKNOWN)
- From the context alone I cannot tell whether the code maximizes `p_any_prize`, P(profit), expected value or something else.
- If it maximizes `p_any_prize`, the README is mis-describing the feature. That would be a product or documentation defect, not a test defect.

### 4. The threshold leaves almost no margin (low to medium, INFERRED)
- The observed 0.41 is only 0.01 above the 0.4 threshold.
- If `p_any_prize` is estimated by simulation, the test needs a fixed seed and enough draws to be reliable. Whether it is exact or simulated is UNKNOWN.
- This matters less than findings 1 and 2. Even a perfectly stable 0.41 would not support the claim.

### What is protected
- One budget value (R$ 10) is protected against `p_any_prize` falling to 0.4 or below.
- No other budgets are tested.

## Evidence that would settle it

1. **Read the recommender's objective** (static, cheap). Which quantity does it maximize? If it is `p_any_prize`, the README claim is unsupported by design. Correct either the README or the objective.
2. **Compute the true quantity.** For the recommended R$ 10 portfolio:
   - Work out the distribution of total prize money from the tier probabilities and payouts: exact enumeration, or simulation with a fixed seed and a stated number of draws.
   - From it, compute P(total prizes > 10.00) and the expected net result.
   - Use expected values that come from the official odds and payout table (the contract), not from the code under test.
3. **Test "maximizes" directly.**
   - With a R$ 10 budget, the set of possible portfolios is small enough to enumerate. Brute-force P(profit) for every affordable portfolio.
   - Assert that the recommendation reaches the maximum, or is within a stated tolerance of it.
   - Repeat for a few other budgets, including edge cases: below one ticket's price, and exactly one ticket.
4. **Run a negative control in a disposable copy.** Change the objective from P(profit) to P(any prize), or the reverse, and confirm the new test fails while the current one stays green. Seeing that difference is what shows the new test protects the claim.
5. **Check what "coming out ahead" means.** "Ahead" means prizes > spend, strictly. Breaking even (prizes = spend) is not ahead. The test should fix this boundary explicitly.

Until steps 1 and 2 are done, I would report the README claim as **unverified**. The suite is green on HEAD, but that green says nothing about profit.
