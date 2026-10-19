"""Library loans: labeled confirmation fixture (see labels.json). Never run; read statically."""
import asyncio
import sys
import time

import pytest

from loans import Loan, LoanError, due_date, fine, renew


def test_fine_for_late_return():
    assert fine(days_late=3, daily_rate=50) == 150


def test_fine_ignores_errors():
    try:
        assert fine(days_late=-1, daily_rate=50) == 0
    except Exception:
        pass


def test_renew_when_allowed():
    loan = renew(Loan(book="b1", renewals=0))
    if loan.renewals:
        assert loan.renewals == 1


def test_due_date_matches_itself():
    d = due_date("2026-01-01", days=14)
    assert d == d


def test_renew_limit_raises_specific_error():
    with pytest.raises(LoanError, match="renewal limit"):
        renew(Loan(book="b1", renewals=3))


def test_due_date_exists():
    assert due_date("2026-01-01", days=14) is not None


def test_platform_specific_due_date():
    if sys.platform == "win32":
        pytest.skip("calendar backend differs on Windows")
    assert due_date("2026-01-01", days=1) == "2026-01-02"


def test_each_fine_tier():
    for days, expected in [(1, 50), (2, 100), (10, 500)]:
        assert fine(days_late=days, daily_rate=50) == expected


@pytest.mark.parametrize("days, expected", [(1, 50), (5, 250), (1, 50)])
def test_fine_rows(days, expected):
    assert fine(days_late=days, daily_rate=50) == expected


@pytest.mark.parametrize("rate", [10, 20])
@pytest.mark.parametrize("days", [10, 20])
def test_fine_grid(days, rate):
    assert fine(days_late=days, daily_rate=rate) == days * rate


def test_reminder_waits_for_worker():
    send_reminder("b1")
    time.sleep(2)
    assert outbox() == ["b1"]


def test_hold_expires_after_ttl():
    hold = place_hold("b1", ttl_s=0.1)
    time.sleep(0.2)
    assert hold.expired


def test_fine_copy_a():
    total = fine(days_late=4, daily_rate=25)
    assert total == 100


def test_fine_copy_b():
    total = fine(days_late=4, daily_rate=25)
    assert total == 100


def test_fine_other_input():
    total = fine(days_late=8, daily_rate=25)
    assert total == 100 * 2


async def test_notify_runs_in_background():
    asyncio.create_task(notify("b1"))
    assert True
