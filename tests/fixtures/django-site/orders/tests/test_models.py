from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase

from orders.models import Order, create_paid_pair


class OrderPaymentTests(TestCase):
    def test_paying_marks_the_order_paid(self):
        order = Order.objects.create(code="A1", total=Decimal("10.00"))
        order.pay()
        order.refresh_from_db()
        self.assertTrue(order.paid)

    def test_an_order_without_total_is_rejected_and_stays_unpaid(self):
        order = Order.objects.create(code="A2", total=Decimal("0"))
        with self.assertRaises(ValueError):
            order.pay()
        order.refresh_from_db()
        self.assertFalse(order.paid)


class PairCreationTests(TransactionTestCase):
    def test_a_duplicate_code_rolls_back_the_whole_pair(self):
        Order.objects.create(code="DUP", total=Decimal("1"))
        with self.assertRaises(IntegrityError):
            create_paid_pair("NEW", "DUP", Decimal("5"))
        self.assertFalse(Order.objects.filter(code="NEW").exists())
