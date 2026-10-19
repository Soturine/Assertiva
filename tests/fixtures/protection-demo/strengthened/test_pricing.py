from pricing import discount_cents


def test_member_gets_a_discount():
    assert discount_cents(15000, True) == 1500


def test_non_member_pays_full_price():
    assert discount_cents(15000, False) == 0


def test_the_threshold_is_inclusive():
    assert discount_cents(10000, True) == 1000
    assert discount_cents(9999, True) == 0


def test_the_discount_rounds_down_to_whole_cents():
    assert discount_cents(10005, True) == 1000
