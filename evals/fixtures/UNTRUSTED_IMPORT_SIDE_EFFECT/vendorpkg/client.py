"""Price quotes."""
import urllib3


def quote(amount, rate):
    if amount < 0:
        raise ValueError("amount must not be negative")
    return round(amount * rate, 2)


def session():
    return urllib3.PoolManager()
