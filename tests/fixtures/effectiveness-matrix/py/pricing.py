def total(prices, discount=0):
    if discount < 0 or discount > 100:
        raise ValueError("discount out of range")
    return round(sum(prices) * (100 - discount) / 100, 2)
