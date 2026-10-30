"""Exchange-rate client."""
import json
import urllib.request


def fetch_rate(currency: str, opener=urllib.request.urlopen) -> float:
    with opener(f"https://rates.example.invalid/{currency}") as response:
        payload = json.loads(response.read())
    if payload.get("currency") != currency:
        raise ValueError("rate for another currency")
    return float(payload["rate"])
