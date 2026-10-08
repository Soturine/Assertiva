import json
from urllib.request import ProxyHandler, build_opener

from django.test import LiveServerTestCase


class LiveHealthTests(LiveServerTestCase):
    def test_the_live_server_answers(self):
        opener = build_opener(ProxyHandler({}))  # the local server only: never a configured proxy
        with opener.open(f"{self.live_server_url}/health/", timeout=10) as response:
            self.assertEqual(json.loads(response.read()), {"status": "ok"})
