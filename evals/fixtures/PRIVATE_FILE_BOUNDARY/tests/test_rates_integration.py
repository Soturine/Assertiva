"""Integration test of the rates client."""
import io
import json

from ledgerlite.rates import fetch_rate


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_rates_integration_returns_the_rate():
    opener = lambda url: FakeResponse(json.dumps({"currency": "USD", "rate": 5.1}).encode())
    assert fetch_rate("USD", opener=opener) == 5.1
