import pytest

from vendorpkg.client import quote


def test_quote_rounds_to_cents():
    assert quote(10, 0.333) == 3.33


def test_negative_amount_is_rejected():
    with pytest.raises(ValueError):
        quote(-1, 1.0)
