import os
from pathlib import Path

import pytest


def test_total_passes():
    assert sum([1, 2]) == 3


def test_discount_fails():
    assert round(15000 * 0.1) == 1400


@pytest.mark.skip(reason="coupons are not decided yet")
def test_coupon_skipped():
    pass


@pytest.mark.parametrize("cents,expected", [(100, 10), (5, 0)])
def test_rounding(cents, expected):
    assert cents // 10 == expected


def test_flaky_then_passes():
    marker = Path(os.environ["FLAKY_MARKER"])
    seen = marker.exists()
    marker.write_text("x")
    assert seen
