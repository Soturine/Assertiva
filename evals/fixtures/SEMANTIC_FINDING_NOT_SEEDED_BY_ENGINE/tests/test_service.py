from unittest.mock import MagicMock

from notify.gateway import GatewayError, SmsGateway
from notify.service import notify_overdue

ANA = {"id": "c1", "phone": "+5511999990001", "invoice": "INV-7", "amount": "R$ 120,00"}
BIA = {"id": "c2", "phone": "+5511999990002", "invoice": "INV-9", "amount": "R$ 80,00"}


def test_each_overdue_customer_gets_one_message():
    gateway = MagicMock(spec=SmsGateway)
    gateway.send.side_effect = ["m-1", "m-2"]
    outcome = notify_overdue([ANA, BIA], gateway)
    assert outcome.sent == {"c1": "m-1", "c2": "m-2"}
    assert gateway.send.call_count == 2
    gateway.send.assert_any_call("+5511999990001", "Invoice INV-7 is overdue. Total due: R$ 120,00.")


def test_rate_limited_customers_are_retried_later():
    gateway = MagicMock(spec=SmsGateway)
    gateway.send.side_effect = [GatewayError("RATE_LIMITED"), "m-2"]
    outcome = notify_overdue([ANA, BIA], gateway)
    assert outcome.retry_later == ["c1"]
    assert outcome.sent == {"c2": "m-2"}
    assert outcome.failed == []


def test_other_provider_errors_fail_permanently():
    gateway = MagicMock(spec=SmsGateway)
    gateway.send.side_effect = GatewayError("INVALID_NUMBER")
    outcome = notify_overdue([ANA], gateway)
    assert outcome.failed == ["c1"]
    assert outcome.retry_later == []
