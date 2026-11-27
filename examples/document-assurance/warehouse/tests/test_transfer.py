from transfer import Store, handle_transfer


def operator(*permissions):
    return {"id": "op-1", "permissions": list(permissions)}


def test_transfer_succeeds():
    store = Store({("A", "bolt"): 500})
    response = handle_transfer({"actor": operator("stock:transfer"), "item": "bolt", "qty": 150, "from": "A", "to": "B",
                                "supervisor_approval": "sup-7"}, store, [])
    assert response.status == 200


def test_transfer_without_permission_is_refused():
    store = Store({("A", "bolt"): 500})
    response = handle_transfer({"actor": operator(), "item": "bolt", "qty": 5, "from": "A", "to": "B"}, store, [])
    assert response.status == 403
