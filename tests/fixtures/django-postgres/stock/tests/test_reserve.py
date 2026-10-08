from django.db import connection
from django.test import TestCase

from stock.models import Item, reserve


class ReserveTests(TestCase):
    def test_the_suite_runs_on_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql")

    def test_reserving_reduces_the_stock(self):
        Item.objects.create(sku="A-1", quantity=5)
        self.assertEqual(reserve("A-1", 3), 2)

    def test_a_shortfall_is_rejected_and_the_stock_is_unchanged(self):
        Item.objects.create(sku="A-2", quantity=1)
        with self.assertRaisesRegex(ValueError, "insufficient stock"):
            reserve("A-2", 2)
        self.assertEqual(Item.objects.get(sku="A-2").quantity, 1)

    def test_json_containment_uses_postgresql_operators(self):
        Item.objects.create(sku="A-3", attributes={"color": "red", "size": "M"})
        self.assertEqual(list(Item.objects.filter(attributes__contains={"color": "red"}).values_list("sku", flat=True)), ["A-3"])
