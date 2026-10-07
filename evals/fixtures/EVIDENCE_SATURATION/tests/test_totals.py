import pytest

from invoicing.totals import invoice_total, line_total


def test_line_without_discount():
    assert line_total(3, 250) == 750


def test_full_discount_is_free():
    assert line_total(2, 999, 100) == 0


def test_discount_rounds_half_up_to_the_cent():
    # 1 x 0.15 with 50% off is 7.5 cents: half up gives 8
    assert line_total(1, 15, 50) == 8


@pytest.mark.parametrize("quantity, price", [(-1, 100), (1, -100)])
def test_negative_inputs_are_rejected(quantity, price):
    with pytest.raises(ValueError, match="non-negative"):
        line_total(quantity, price)


def test_discount_out_of_range_is_rejected():
    with pytest.raises(ValueError, match="between 0 and 100"):
        line_total(1, 100, 101)


def test_invoice_total_adds_tax_on_the_subtotal():
    assert invoice_total([(2, 500, 0), (1, 1000, 10)], 10) == 2090
