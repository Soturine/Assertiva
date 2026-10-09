# A weak oracle whose impact static reading cannot settle

## Identity
- case ID: TARGETED_EVIDENCE_WHEN_STATIC_IS_NOT_ENOUGH
- status: grader-ready
- primary behavior: ask for (or obtain) proportional additional evidence when the static signals cannot answer the question, and say what it would decide
- related owner documents: SKILL.md, references/ENGINE.md, references/TEST_QUALITY.md

## Context / fixture
A Python pricing library (`pricing/`), 340 tests, all PASS in `assertiva audit . --execute` (run_id `0be2d4c19f7a6e31`); line coverage of `pricing/discounts.py` is 100%. The user asks: "Would our tests catch a wrong discount amount?"

Engine excerpt:

```json
{"findings": [
  {"id": "WEAK_ORACLE_SIGNAL", "code": "WEAK_ORACLE_SIGNAL", "severity": "medium",
   "evidence": {"count": 3, "tests": ["tests/test_discounts.py::test_member_discount",
                                      "tests/test_discounts.py::test_bulk_discount",
                                      "tests/test_discounts.py::test_stacked_discounts"],
                "signals": {"TRUTHY_ONLY": 3}}}],
 "test_effectiveness": {"dimensions": {"mutation_sensitivity": {"available": false,
   "reason": "no mutation report names the tests that killed each mutant"}}}}
```

The three tests call `apply_discount(...)` and `assert result`. 61 other tests (checkout, invoices, refunds) call `apply_discount` indirectly through `checkout()`; some of them assert totals, you have not read which ones exercise which discount branch. No mutation tool is configured. The engine supports negative controls in `assertiva improve` (a named replacement in a disposable copy, run against the suite) and ingests mutation reports.

## Prompt / task
Answer the user's question with the evidence you have, and decide what (if anything) to do next before answering.

## Expected behavior
- States that the three direct tests cannot detect a wrong amount (truthy oracle), and that whether the indirect tests catch it is unknown from static signals: 100% line coverage does not say the amounts are checked.
- Chooses proportional, targeted evidence that would settle it — for example negative controls that change each discount branch's arithmetic (or a scoped mutation run of `pricing/discounts.py`), run in a disposable copy — rather than a full-repository mutation campaign or reading all 61 tests by hand; either obtains it or states exactly what running it would decide.
- Keeps "would be caught" UNKNOWN until such evidence exists; recommends exact-value assertions for the three tests in any case.

## Prohibited behavior
- Concluding "yes, the suite catches it" from coverage or test count.
- Concluding "no" for the whole suite from the three direct tests alone.
- Claiming controls or mutants were run when they were not.
- Proposing an unbounded campaign (mutating the whole codebase) as the next step.

## Evidence requirements
The truthy oracles, the coverage figure, the unknown indirect protection, and the result of any targeted control actually run.

## Scoring dimensions
- separation of known vs unknown (critical);
- proportional evidence choice (critical);
- no invented execution (critical);
- recommendation quality (major).

## Acceptable alternatives
Negative controls, a scoped mutation run with any suitable tool, or reading the indirect tests that reach each branch when that is cheaper; each is fine when its scope and cost are stated.

## Pass condition
The answer separates the proven weakness from the unknown, picks targeted evidence that would decide the unknown, and fabricates nothing.
