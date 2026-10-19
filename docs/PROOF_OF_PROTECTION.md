# Proof of protection: audit, a gap, a stronger test, the gain proven

A reproducible walk-through on `tests/fixtures/protection-demo`, the same flow `tests/test_proof_of_protection.py`
runs through the CLI. It shows what 0.8.0 adds: Assertiva runs a native mutation tool on the states it measures and
reports, for a candidate test change, which deliberate breaks the baseline missed and the candidate now detects —
not a coverage percentage and not a test count.

## The project

`pricing.discount_cents(total_cents, member)` gives members 10 % of orders of 100.00 or more, rounded down to whole
cents. Its test checks only that the result exists:

```python
def test_member_gets_a_discount():
    assert discount_cents(15000, True) is not None
```

## Prerequisites

The project's environment needs pytest and Cosmic Ray (`pip install pytest cosmic-ray` in the interpreter the tests
run with). Assertiva does not install either; without Cosmic Ray, `--mutate` is BLOCKED with that reason.

## 1. Audit: the gap, and what the suite misses

```
assertiva audit protection-demo --execute --python <that interpreter> --mutate pricing.py
```

- the engine reports a weak-oracle signal on `test_member_gets_a_discount` (existence only);
- Cosmic Ray, run on a disposable copy, mutates `pricing.py` 24 times; the suite detects 4 and **20 survive**
  (`total_cents // 10` → `* 10`, `>= 10000` → `> 10000`, `10000` → `10001`, …). The run is tied to the audited state
  by the sources and tests it saw.

## 2. Improve: a stronger test, written only in the candidate workspace

```
assertiva improve protection-demo --python <interpreter>          # baseline measured, workspace created
```

Write `strengthened/test_pricing.py` into the candidate workspace as `tests/test_pricing.py`: exact values, the
inclusive threshold (10000 and 9999) and the rounding (10005 → 1000).

## 3. Qualification: the same breaks on both states

```
assertiva improve protection-demo --python <interpreter> --mutate pricing.py --negative-controls negative-controls.json
```

Observed on 2026-10-19 (Cosmic Ray 8.7.0; Python 3.12 on Windows 11 and on Debian bookworm), commit `5fe2124`:

| | Baseline | Candidate |
| --- | --- | --- |
| Mutants of `pricing.py` | 4 detected, 20 survived | 24 detected |
| Negative control `threshold-exclusive` (`>=` → `>`) | survived | detected by `test_the_threshold_is_inclusive` |

`candidate_qualification.protection` lists 21 gained breaks (20 mutants and the control), 0 lost and 0 still
undetected; the fault-sensitivity check passes with "protection gained", and the improve page shows the
**Protection the candidate adds** panel. Nothing is applied until the change id is approved; the project is unchanged.

A candidate that weakens the tests instead (only the existence check left) fails the same check with
`PROTECTION_LOST`, naming the mutants the baseline detected and the candidate no longer does.

## What this proves, and what it does not

- It proves that, for these 24 mutants of this file and this deliberate break, the candidate's tests fail where the
  baseline's passed, on the same code, both runs executed by Assertiva.
- Cosmic Ray runs the whole test command per mutant and records no killing test, so a gained mutant is attributed to
  "the candidate's tests" and the changed files, not to one test; negative controls do name the detecting test.
  Per-test contribution with complete killer matrices is 0.8.1 work.
- Mutants outside the named files, equivalent mutants and behaviors no operator changes are not covered; a mutant the
  candidate still misses keeps the check from passing.
- An imported mutation report proves no difference: only runs executed and tied on both states are compared.
