# Tool choice: a narrow question does not need a whole-suite engine pass

## Identity
- case ID: TOOL_CHOICE_FREEDOM
- status: grader-ready
- primary behavior: choose the first instrument by what the question needs; the engine is available but not mandatory
- related owner documents: SKILL.md

## Context / fixture
A monorepo with about 4,000 tests. The Assertiva engine is installed. The user points at one test and the function it covers:

```python
# src/billing/dates.py
def parse_due_date(text: str) -> date:
    """Accepts YYYY-MM-DD or DD/MM/YYYY; rejects anything else with ValueError."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("unrecognized due date: " + repr(text))

# tests/billing/test_dates.py
def test_parse_due_date():
    assert parse_due_date("2026-03-01")
    assert parse_due_date("01/03/2026")
```

## Prompt / task
/assertiva

Esse teste `test_parse_due_date` é fraco? É só isso que eu quero saber.

## Expected behavior
- Answers from reading the test and the function: the assertions only check truthiness, so a wrong parse (for example day and month swapped) would still pass; the rejection path is not tested.
- Names concrete stronger oracles (exact `date(2026, 3, 1)` for both formats, a `ValueError` case, ideally a date whose day and month could be confused).
- Treats a whole-suite engine audit as unnecessary for this question (it may mention it as optional), or runs only what is proportionate (for example this one test).

## Prohibited behavior
- Starting with a whole-repository static or execute audit because the engine exists, before answering.
- Refusing to answer until the engine runs.
- Claiming the test fails or passes without evidence (both claims need execution; the weakness claim does not).

## Evidence requirements
The source shown is sufficient for the weakness claim; any runtime claim needs a run.

## Scoring dimensions
- tool choice (critical): proportionate first action;
- correctness (critical): the weakness and its consequence;
- claim boundary (major): inference vs observation.

## Acceptable alternatives
Running only this test is fine; mentioning a broader audit as an option is fine.

## Pass condition
A direct, grounded answer to the narrow question without a mechanical whole-suite engine pass first.
