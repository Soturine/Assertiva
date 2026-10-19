"""Member discount: 10% of orders of 100.00 or more, in whole cents (rounded down)."""


def discount_cents(total_cents, member):
    if member and total_cents >= 10000:
        return total_cents // 10
    return 0
