# Corrected report

## Answer

**The run does not show 434 product defects.** 434 of the 1157 tests errored. Each one errored with the same infrastructure failure: `PermissionError: [WinError 5] Access denied: '...\Temp\pytest-of-user'`, raised inside pytest's `tmp_path` factory before the test body could run. Those 434 tests are **not executed**. What their behavior would be is UNKNOWN. They are neither passed nor failed on product grounds.

The other 723 tests produced outcomes. What they prove depends on their oracles. One of them, a probability test, cannot detect a wrong result, because its expected value is computed by the function under test. The draft did not mention this.

## Corrections to the draft

| Draft says | Corrected |
| --- | --- |
| "434 product defects" | 434 tests (unit: test invocations as the engine reports them) **errored during setup** with one shared cause: Windows access was denied to pytest's base temp directory. Classification: **environment or infrastructure**, not product. These tests did not run, so their behavior is UNKNOWN. |
| (nothing about the oracle) | Add an agent finding: the probability test's expected value is derived from the function under test, so it is a false-green risk. |

## Engine finding disposition

**`NATIVE_TESTS_FAILING` (high): CONTEXTUAL**
- The fact holds: 434 of 1157 tests errored in this run (OBSERVED, deterministic engine outcome).
- Its meaning differs: all 434 errors share one fingerprint. That fingerprint is a `PermissionError` on `...\Temp\pytest-of-user`, raised in pytest's `tmp_path` factory, which is fixture setup and not product code. This is one environment failure that affects every test using `tmp_path`, not 434 independent defects.
- Priority: **high as an evidence gap**, because 37.5% of the suite gave no evidence. It is not high as a product-quality finding.
- Evidence: the engine's run outcomes, and the identical error message and stack location across all 434. That they are all identical is stated in the context ("every error message is ..."). If the full list was not checked, check it in the JSON before final attachment.

## Agent finding (new, first-class)

**Self-derived oracle in a probability test**
- Claim: the test computes its expected value by calling the function under test, so the assertion compares the function with itself.
- Why it matters: any defect in the probability computation (a wrong formula, an off-by-one, a wrong normalization) produces the same wrong value on both sides, and the test stays green. It protects against exceptions, and at most against nondeterminism, not against wrong results.
- Basis: INFERRED from reading the test and the implementation together (the agent's own reading). It is not yet confirmed by execution. A negative control would settle it: break the formula in a disposable copy and see whether this test still passes.
- Priority: medium to high, depending on how critical the probability computation is. If no other test checks it against an independent value, the behavior is effectively unprotected.
- Recommendation: replace the expected value with one from the contract, such as a hand-computed example, a known closed form, or a property (bounds in [0, 1], sums to 1, symmetry, monotonicity). Do not copy what the code returns today; that would make it a characterization test.

## What green proves and does not prove in this run

- **Protected (within limits):** the behaviors covered by the 723 tests that ran and passed, to the extent their oracles are independent of the code. The probability test is known not to be independent.
- **Not evidenced:** everything only the 434 errored tests cover. Their exists step holds. Their selected step holds. Their executed step did not happen. Their outcome and proven steps are unknown.
- **No aggregate score:** a 723/1157 pass ratio is not a quality measure. Errors are not failures, and they are not passes.

## What stays unknown, and what would settle it

- **Whether the 434 tests pass.** Fix the environment, then rerun through the engine, `assertiva audit <project> --execute`. Fixes include a writable base temp, for example `--basetemp` pointing to a writable directory or a `TEMP`/`TMP` the runner may write to; resolving a stale, locked `pytest-of-user` directory owned by another user or process; or checking antivirus or ACLs. Only that rerun can show whether any of the 434 hide real product failures.
- **Whether the probability test is a false green.** It is inferred and not yet executed. A negative control would settle it.
- **Whether the 434 errors are truly identical.** The context says every message is the same. If only a sample was read, say so.

## Assurance Report

Because the engine wrote an Assurance Report for this run, the corrected conclusion must go into it, not just into the draft. Write an assessment JSON with:
- this summary;
- the `NATIVE_TESTS_FAILING` disposition as `CONTEXTUAL` (priority `high`, with the shared-fingerprint rationale and evidence);
- the self-derived-oracle agent finding (basis `INFERRED`, with its evidence and recommendation);
- the unknowns above.

Attach it with `assertiva audit <project> --assessment <file>` so the report and this answer agree. The `run_id` and `report_path` are not given in this context, so I cannot cite the `Assurance Report:` path here. Take it from the audit JSON.
