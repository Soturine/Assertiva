"""Stock transfer between two locations (synthetic demo for Assertiva's document assurance).

The behavior follows docs/requirements.pdf: RF-01 on page 1 (text) and the exception flow of Figure 1 on page 2,
which exists only as an image.
"""

from __future__ import annotations

from dataclasses import dataclass, field

APPROVAL_THRESHOLD = 100  # Figure 1: a quantity above this needs a supervisor approval


@dataclass
class Response:
    status: int
    body: dict = field(default_factory=dict)


class Store:
    """Stock per (location, item); a transfer either moves everything or nothing."""

    def __init__(self, stock: dict[tuple[str, str], int] | None = None):
        self.stock = dict(stock or {})

    def level(self, location: str, item: str) -> int:
        return self.stock.get((location, item), 0)

    def move(self, item: str, qty: int, source: str, dest: str) -> None:
        if self.level(source, item) < qty:
            raise ValueError("insufficient stock")
        snapshot = dict(self.stock)
        try:
            self.stock[(source, item)] = self.level(source, item) - qty
            self.stock[(dest, item)] = self.level(dest, item) + qty
        except Exception:
            self.stock = snapshot
            raise


def handle_transfer(request: dict, store: Store, events: list) -> Response:
    actor = request.get("actor") or {}
    item, qty = request.get("item"), request.get("qty")
    source, dest = request.get("from"), request.get("to")
    if "stock:transfer" not in (actor.get("permissions") or ()):
        return Response(403, {"code": "FORBIDDEN"})
    if not isinstance(qty, int) or qty <= 0 or not item or not source or not dest or source == dest:
        return Response(422, {"code": "INVALID_REQUEST"})
    if qty > APPROVAL_THRESHOLD and not request.get("supervisor_approval"):
        return Response(409, {"code": "APPROVAL_REQUIRED"})
    if store.level(source, item) < qty:
        return Response(409, {"code": "INSUFFICIENT_STOCK"})
    store.move(item, qty, source, dest)
    events.append({"type": "stock.transferred", "item": item, "qty": qty, "from": source, "to": dest})
    return Response(200, {"moved": qty})
