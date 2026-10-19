# Would the tests catch a wrong discount amount?

**Answer: not shown.** The evidence in hand does not show that a wrong discount amount would fail the suite. The three tests that call `apply_discount` directly would stay green for a wrong amount. Whether the 61 indirect tests catch one is unknown until their assertions are read and tied to the discount branches.

## What the green run proves

- **Observed:** `assertiva audit . --execute` (run_id `0be2d4c19f7a6e31`) ran 340 tests and all passed. This is the outcome at the audited revision only.
- **Observed:** line coverage of `pricing/discounts.py` is 100%.
- **What this does not prove:** line coverage shows that lines executed, not that the amounts were checked. A line can run with a wrong formula and still pass.

## Findings, ranked by consequence

1. **The three direct discount tests cannot detect a wrong amount.** `test_member_discount`, `test_bulk_discount` and `test_stacked_discounts` only `assert result`. Any truthy value passes, including a wrong amount.
   - Basis: the engine's `WEAK_ORACLE_SIGNAL` (`TRUTHY_ONLY`, 3 of 3) and the description of the three tests in the request. I did not read the test bodies in this session, so a helper that might assert the amount is not ruled out. Within the stated excerpt the finding holds.
   - Disposition for the engine finding: **CONFIRMED**, scope 3 of 3, against the described bodies. Priority: high, because these are the only tests named for these discount branches.

2. **The 61 indirect tests (checkout, invoices, refunds) are the only possible detectors of a wrong amount.** Some of them assert totals. Which discount branch each one exercises is unknown. Until that is mapped, the claim "the discount amount is protected" cannot be made for any branch.
   - Basis: UNKNOWN. Nothing read settles it.

3. **No mutation evidence exists.** `mutation_sensitivity` is unavailable because no mutation report names the killing tests. So there is no per-test evidence of which tests detect a mutant in `discounts.py`.

4. **Line coverage gives false comfort here.** At 100% line coverage with truthy-only oracles on the direct tests, the coverage number is a diagnostic and says nothing about amount correctness.

## What I did and did not do

- I did not run anything, read any file or run a negative control. The instructions for this task limit me to the provided context.
- The three findings above rest on the engine excerpt and the description of the tests. The engine's `WEAK_ORACLE_SIGNAL` is heuristic; the description is the only evidence about the test bodies.

## What would settle it (next steps)

1. **Map the 61 indirect tests to discount branches.** Read which ones assert totals, and for each, which discount branch (member, bulk, stacked, and any others) its inputs reach. This is cheap and should be done before any change.
2. **Negative controls in a disposable copy.** Use `assertiva improve` with `--negative-controls`. Each control is a named, behavior-breaking edit, for example:
   - change the member discount rate;
   - move the bulk threshold by one unit;
   - reverse the stacking order or apply the second discount to the wrong base.
   
   Run them against the suite. If the suite stays green for a control, that is a confirmed false green for that behavior. If it fails, the control is detected.
3. **Mutation report, if the user wants per-test evidence.** Configure a mutation tool, run it in a copy, and ingest the report with `--mutation-report`. This would also fill `mutation_sensitivity`.
4. **Strengthen the three direct tests** (exact expected amounts, with expected values derived by hand, not from the code under test). This is a change to the project and goes through `assertiva improve`: the candidate is written only in the candidate workspace, and applying it requires the user's explicit approval of named change ids. I have not done this.

## Unknowns

- Which of the 61 indirect tests assert exact discount amounts, and which branches they reach.
- Whether any negative control would be detected. No control has been run.
- Whether the three direct tests' helpers assert the amount (not read).

## Assurance Report

Not produced. The context gives no `report_path` for the run and I was not permitted to run the engine or read files. Once the report exists, the assessment above (finding WEAK_ORACLE_SIGNAL: CONFIRMED, scope 3 of 3; unknowns as listed) should be attached with `assertiva audit <project> --assessment <file>` and must not contradict this answer. The end line is `Assurance Report: <report_path>` when that path is known.
