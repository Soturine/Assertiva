import os

import pytest

from invoicing.storage import connect, load_total, save_invoice

pytestmark = pytest.mark.skipif(not os.environ.get("INVOICING_DB_URL"), reason="needs INVOICING_DB_URL")


@pytest.fixture
def conn():
    connection = connect(os.environ["INVOICING_DB_URL"])
    yield connection
    connection.close()


def test_saved_invoice_total_round_trips(conn):
    save_invoice(conn, "INV-1", 2090)
    assert load_total(conn, "INV-1") == 2090


def test_duplicate_invoice_number_is_rejected(conn):
    save_invoice(conn, "INV-2", 100)
    with pytest.raises(Exception):
        save_invoice(conn, "INV-2", 200)
    assert load_total(conn, "INV-2") == 100
