import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_transport import FakeTransport  # noqa: E402


class HistoryTransport(FakeTransport):
    """The same double, able to report a (fake) test case history: a transport API method, not a test."""

    def test_case_history(self, case_id):
        return [item for item in self.sent if item.get("case") == case_id]


class HistoryTests(unittest.TestCase):
    def test_history_lists_only_that_case(self):
        transport = HistoryTransport()
        transport.send({"case": 1})
        transport.send({"case": 2})
        self.assertEqual([{"case": 1}], transport.test_case_history(1))
