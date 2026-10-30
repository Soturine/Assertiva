"""Fees and discounts in integer cents."""


def fee(amount_cents: int, rate_bp: int) -> int:
    """Fee in cents for a rate in basis points, rounded down."""
    if amount_cents < 0 or rate_bp < 0:
        raise ValueError("amounts and rates are non-negative")
    return amount_cents * rate_bp // 10_000


def discount(total_cents: int) -> int:
    """Orders of R$ 100,00 or more get 10 % off (the business rule says 'or more')."""
    if total_cents > 10_000:
        return total_cents // 10
    return 0
