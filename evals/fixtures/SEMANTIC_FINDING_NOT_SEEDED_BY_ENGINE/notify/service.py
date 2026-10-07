"""Overdue-invoice reminders."""

from dataclasses import dataclass, field

from .gateway import GatewayError


@dataclass
class Outcome:
    sent: dict[str, str] = field(default_factory=dict)      # customer -> message id
    retry_later: list[str] = field(default_factory=list)    # provider asked us to slow down
    failed: list[str] = field(default_factory=list)         # permanent failures, never retried


def notify_overdue(customers: list[dict], gateway) -> Outcome:
    outcome = Outcome()
    for customer in customers:
        body = f"Invoice {customer['invoice']} is overdue. Total due: {customer['amount']}."
        try:
            outcome.sent[customer["id"]] = gateway.send(customer["phone"], body)
        except GatewayError as exc:
            if exc.code == "RATE_LIMITED":
                outcome.retry_later.append(customer["id"])
            else:
                outcome.failed.append(customer["id"])
    return outcome
