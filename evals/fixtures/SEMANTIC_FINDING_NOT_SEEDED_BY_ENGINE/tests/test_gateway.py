import json
from io import BytesIO
from unittest.mock import patch

from notify.gateway import SmsGateway


def test_send_returns_the_provider_message_id():
    with patch("notify.gateway.urlopen") as fake:
        fake.return_value.__enter__.return_value = BytesIO(json.dumps({"id": "msg-42"}).encode())
        message_id = SmsGateway("https://sms.example", "k").send("+5511999990001", "hello")
    assert message_id == "msg-42"
    request = fake.call_args.args[0]
    assert request.full_url == "https://sms.example/messages"
    assert json.loads(request.data) == {"to": "+5511999990001", "text": "hello"}
