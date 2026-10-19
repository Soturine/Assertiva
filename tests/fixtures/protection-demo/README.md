# protection-demo

The end-to-end proof-of-protection flow (docs/PROOF_OF_PROTECTION.md, `tests/test_proof_of_protection.py`): a member
discount whose test only checks that a value exists. The audit finds the weak oracle and, with `--mutate pricing.py`,
the mutants the suite misses; `strengthened/test_pricing.py` is the improved test written into the candidate
workspace; qualification runs the same mutants and the negative control on both states and reports what the candidate
now detects. Generic, written for this repository; never run in place.
