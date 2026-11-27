def discount(total, rate):
    if rate < 0 or rate > 1:
        raise ValueError("rate out of range")
    return round(total * (1 - rate), 2)
