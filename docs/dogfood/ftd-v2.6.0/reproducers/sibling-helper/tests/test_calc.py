import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from calc import discount  # noqa: E402
from helper import make_order  # noqa: E402  (found only when tests/ is on sys.path, as under discover -s tests)


class DiscountTests(unittest.TestCase):
    def test_ten_percent(self):
        self.assertEqual(90.0, discount(make_order(100)["total"], 0.1))

    def test_rate_above_one_is_refused(self):
        with self.assertRaises(ValueError):
            discount(100, 1.5)
