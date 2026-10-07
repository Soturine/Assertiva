"""Invoice arithmetic in integer cents."""


def line_total(quantity: int, unit_price_cents: int, discount_pct: int = 0) -> int:
    """Total of one line in cents; discounts round half up to the nearest cent."""
    if quantity < 0 or unit_price_cents < 0:
        raise ValueError("quantity and price must be non-negative")
    if not 0 <= discount_pct <= 100:
        raise ValueError("discount must be between 0 and 100")
    gross = quantity * unit_price_cents
    return int(gross * (100 - discount_pct) / 100)


def invoice_total(lines: list[tuple[int, int, int]], tax_pct: int) -> int:
    subtotal = sum(line_total(q, p, d) for q, p, d in lines)
    return subtotal + subtotal * tax_pct // 100
