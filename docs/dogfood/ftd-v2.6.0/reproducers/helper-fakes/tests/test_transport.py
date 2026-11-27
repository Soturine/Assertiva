import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shop import publish  # noqa: E402


class FakeTransport:
    """A test double for the outbound transport, not a test class."""

    def __init__(self):
        self.sent = []

    def send(self, item):
        self.sent.append(item)
        return len(self.sent)


class PublishTests(unittest.TestCase):
    def test_unapproved_items_are_refused(self):
        transport = FakeTransport()
        with self.assertRaises(PermissionError):
            publish(transport, {"approved": False})
        self.assertEqual([], transport.sent)
