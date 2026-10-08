# Indirect oracles and contracts without asserts

## Identity
- case ID: INDIRECT_ORACLE_CONTRACTS
- status: grader-ready
- primary behavior: judge a test by the contract it protects, not by its count of asserts
- related owner documents: SKILL.md, references/TEST_QUALITY.md, references/ENGINE.md

## Context / fixture
`WEAK_ORACLE_SIGNAL` lists 4 candidates (signals in `evidence.signals`):

```python
def test_building_a_client_does_not_connect(self):           # NO_ASSERTION
    with mock.patch("payments.client.socket.create_connection",
                    side_effect=AssertionError("connected at construction")):
        PaymentsClient(settings)

def test_refund_of_a_settled_payment_is_accepted(self):      # NO_ASSERTION
    refund(settled_payment(), amount=10)   # refund() raises RefundRejected on any rule violation

def test_export_returns_rows(self):                           # EXISTENCE_ONLY
    rows = export(month="2026-09")
    self.assertIsNotNone(rows)
    self.assertIsNotNone(rows[0])
    self.assertIsNotNone(rows[0]["total"])

def test_invalid_currency_is_rejected(self):                  # NO_ASSERTION
    try:
        charge(10, "XXX")
    except Exception:
        pass
```

`refund()` is 40 lines; it raises `RefundRejected` for every rule it checks and returns `None`.

## Prompt / task
Disposition each candidate for the assessment.

## Expected behavior
- `test_building_a_client_does_not_connect`: FALSE_POSITIVE; the guard fails the test on a forbidden call, and the contract is "constructing does not connect".
- `test_refund_of_a_settled_payment_is_accepted`: "accepted = does not raise" can be the contract (FALSE_POSITIVE, or UNRESOLVED with the reason), while noting it does not check the refund's effect (balance, ledger) if that matters.
- `test_export_returns_rows`: CONFIRMED weak despite three asserts: existence only, no values.
- `test_invalid_currency_is_rejected`: CONFIRMED and worse than weak: it passes whether or not an error is raised.
- Whole-finding disposition PARTIAL with every subject listed.

## Prohibited behavior
- Confirming all four because they lack plain `assert` or `self.assertEqual`.
- Accepting `test_export_returns_rows` because it has assertions.
- Missing that the `try/except: pass` test can never fail.

## Evidence requirements
The test bodies and `refund()`'s raising behavior.

## Scoring dimensions
- contract reading (critical);
- per-subject precision (major);
- the never-failing test (critical).

## Acceptable alternatives
UNRESOLVED for the refund test with a clear reason (effect not observed, contract ambiguous).

## Pass condition
The guard test is not confirmed weak, the export and try/except tests are, and every subject is dispositioned with evidence.
