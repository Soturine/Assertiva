import pytest

from ledgerlite.fees import discount, fee


def test_fee_matches_the_formula():
    for amount, rate in [(1000, 150), (999, 1), (123456, 2500)]:
        expected = fee(amount, rate)
        assert fee(amount, rate) == expected


def test_fee_rejects_negative_amounts():
    with pytest.raises(ValueError):
        fee(-1, 10)


def test_discount_for_large_orders():
    assert discount(20_000) == 2_000


def test_no_discount_for_small_orders():
    assert discount(5_000) == 0
