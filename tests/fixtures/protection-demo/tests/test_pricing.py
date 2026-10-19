from pricing import discount_cents


def test_member_gets_a_discount():
    assert discount_cents(15000, True) is not None


def test_non_member_pays_full_price():
    assert discount_cents(15000, False) == 0
