"""HTTP client for the SMS provider."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class GatewayError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SmsGateway:
    def __init__(self, base_url: str, api_key: str):
        self.base_url, self.api_key = base_url.rstrip("/"), api_key

    def send(self, to: str, body: str) -> str:
        """Send one message and return the provider's message id."""
        payload = json.dumps({"to": to, "text": body}).encode()
        request = Request(f"{self.base_url}/messages", data=payload, method="POST",
                          headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read())["id"]
        except HTTPError as exc:
            raise GatewayError(f"HTTP {exc.code}") from exc
