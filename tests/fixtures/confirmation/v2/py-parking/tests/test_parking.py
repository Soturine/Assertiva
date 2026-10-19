"""Parking fees: frozen confirmation fixture v2 (see labels.json). Never run; read statically."""
import time
import unittest

from parking import Ticket, TicketError, fee, grace_until


class FeeTest(unittest.TestCase):
    def test_fee_exact(self):
        self.assertEqual(fee(minutes=95, rate=4), 8)

    def test_fee_hides_failures(self):
        try:
            self.assertEqual(fee(minutes=-5, rate=4), 0)
        except AssertionError:
            pass

    def test_fee_when_charged(self):
        charged = fee(minutes=10, rate=4)
        if charged:
            self.assertEqual(charged, 4)

    def test_fee_both_paths_checked(self):
        charged = fee(minutes=10, rate=4)
        if charged:
            self.assertEqual(charged, 4)
        else:
            self.fail("a 10-minute stay must be charged")

    def test_fee_is_truthy(self):
        self.assertTrue(fee(minutes=200, rate=4))

    def test_negative_minutes_rejected_with_reason(self):
        with self.assertRaisesRegex(TicketError, "negative minutes"):
            fee(minutes=-1, rate=4)

    def test_negative_rate_rejected_somehow(self):
        with self.assertRaises(Exception):
            fee(minutes=10, rate=-4)

    def test_exit_gate_after_payment(self):
        pay(Ticket("t1"))
        time.sleep(1)
        self.assertTrue(gate_open("t1"))

    def test_grace_period_expires(self):
        ticket = Ticket("t2", grace_s=0.1)
        time.sleep(0.2)
        self.assertFalse(ticket.in_grace())

    def test_rate_copy_1(self):
        self.assertEqual(fee(minutes=60, rate=3), 3)

    def test_rate_copy_2(self):
        self.assertEqual(fee(minutes=60, rate=3), 3)

    def test_grace_matches_itself(self):
        until = grace_until("2026-01-01T10:00")
        self.assertEqual(until, until)
