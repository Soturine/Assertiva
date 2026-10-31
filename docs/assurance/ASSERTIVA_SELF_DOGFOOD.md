# Self-dogfood — Assertiva on Assertiva (0.10.0 development line)

A run in which Assertiva measures Assertiva is not independent: the engine, the fixtures and the rules were changed by
the same author in the same work. What this page records is what the instruments showed, and what they found that
the author had not looked for.

## Findings the self-assurance work produced

| Found by | What | Disposition |
| --- | --- | --- |
| Benchmarking 0.9.0 against the candidate | the main checkout's editable install served modules missing from the 0.9.0 worktree from the candidate tree; the first "0.9.0" numbers were mixed code | discarded; re-run from a clean venv; **ENG-02** fixed (identity checks every loaded module, `171c9ad`) |
| Final hardening review (2026-10-31) | identity check capped at 500 modules (ENG-03); registry lost every concurrent update (ENG-04); dependency usage overclaimed (ENG-05); guard: bare-word links (SEC-EVAL-04) | fixed, each with a reproducer that failed first |
| Measuring cost on this repository | static audit 16.8 s → 36–50 s after the imported-helper rule | fixed in `54cb130` (19.7 s, same findings) |
| The same profiling | imported helpers were followed into product modules, so a product function that asserts would count as a test oracle | fixed with a precision control test |
| Dead-code and duplicate scans (vulture, ruff, an AST body-hash scan) | six unreferenced definitions, a duplicated constant assignment, a copied helper, three copies of one regex | removed or shared (`54cb130`); two standalone plugin constants kept on purpose |
| The F07 fixture (DrawLab) re-read for AG-13 | git exiting 128 in the engine's own copy was labelled PRODUCT even with the frame fix | INFRASTRUCTURE rule with a control (`4acb036`) |
| Running `node --test` for real | Node ≥ 22 treats `node --test test/` as a file and fails; JUnit class names are the literal `test` | adapter reports the project's command faithfully; ids rebuilt from the file |

## Static audit of this repository (candidate, 2026-10-30)

`assertiva audit . --dependencies`: status FINDINGS with three info findings (`STATE_AFTER_REJECTION_NOT_EVIDENCED`,
`TEST_SMELL_SIGNALS` for one EXCESSIVE_MOCKING test, `UNCLASSIFIED_VERIFICATION` for CI steps no adapter classifies),
the same codes 0.9.0 reports on this tree. Dependencies: one (`PyYAML>=6.0`), not locked (the project ships no
lockfile; CI pins through `constraints.txt`, which is not a lockfile format the inventory reads), used by 5 product
modules that 3 test files reach: READY_WITH_GAPS.

## Engine-run mutation of Assertiva's own `failures.py` (2026-10-31)

Cosmic Ray 8.7.0 through the engine's mutation orchestrator (`run_mutation_tool`, the code `audit --mutate FILE
--mutate-tests PATH` calls), ENGINE_EXECUTED, on `assertiva/failures.py` with the named tests `tests/test_failures.py`
and `tests/test_failure_headline.py` (baseline of those tests green, `whole_suite: NOT_RUN`). Budget set before
running: at most 300 mutants, 60 s per mutant, 1200 s wall clock. The CLI path was not used: `audit --execute` first
runs the whole suite natively (and again against the wheel), which stopped the first attempt after 30 minutes; this
evidence covers the mutation step, not the full CLI flow.

| Run | Mutants | Killed | Survived | Wall clock | Evidence |
| --- | --- | --- | --- | --- | --- |
| before (`10a900b` tests) | 209 | 110 | 99 | 111 s | [evidence/self-mutation-failures-before.json](evidence/self-mutation-failures-before.json) |
| after three pinned tests (`b98386d`) | 209 | 121 | 88 | 106 s | [evidence/self-mutation-failures-after.json](evidence/self-mutation-failures-after.json) |

Of the 99 first survivors, 55 mutate type annotations (`str | None`), which are never evaluated under
`from __future__ import annotations`: equivalent, unkillable by any test. Of the 44 behavioral candidates, three groups
were real untested behavior (explicit test paths matched on whole components, TEST vs UNKNOWN for errors in test code,
the largest cluster first) and are now pinned by tests; 11 more mutants are killed. The remaining 33 mostly change
message wording or slice lengths of explanatory text; they are recorded, not chased. No score is claimed from this run:
it covers one module and two test files.

## Not done

- The executed self-audit (`--execute` over the whole suite in a disposable copy) was not part of this record; the
  suites ran directly (see [RELEASE_READINESS.md](RELEASE_READINESS.md)).
- Independent labeling and blind holdout: not available (single author).
