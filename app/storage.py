from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from app.models import Order, utcnow_iso


class OrderRepository:
    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text('{"orders": []}', encoding="utf-8")
        self._lock = threading.Lock()

    def create_draft(self, user_id: int, peer_id: int) -> Order:
        active_order = self.get_active_order_for_user(user_id)
        if active_order is not None:
            return active_order

        timestamp = utcnow_iso()
        order = Order(
            id=uuid.uuid4().hex,
            user_id=user_id,
            peer_id=peer_id,
            status="draft",
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.save(order)
        return order

    def save(self, order: Order) -> Order:
        with self._lock:
            payload = self._read_payload()
            orders = [Order.from_dict(item) for item in payload["orders"]]
            existing_index = next((index for index, item in enumerate(orders) if item.id == order.id), None)
            order.touch()
            if existing_index is None:
                orders.append(order)
            else:
                orders[existing_index] = order
            self._write_payload({"orders": [item.to_dict() for item in orders]})
        return order

    def get_by_id(self, order_id: str) -> Order | None:
        with self._lock:
            orders = [Order.from_dict(item) for item in self._read_payload()["orders"]]
        return next((item for item in orders if item.id == order_id), None)

    def get_active_order_for_user(self, user_id: int) -> Order | None:
        orders = self.get_orders_for_user(user_id)
        active_statuses = {"draft", "package_selected", "style_selected", "collecting_photos"}
        for order in reversed(orders):
            if order.status in active_statuses:
                return order
        return None

    def get_last_order_for_user(self, user_id: int) -> Order | None:
        orders = self.get_orders_for_user(user_id)
        return orders[-1] if orders else None

    def get_orders_for_user(self, user_id: int) -> list[Order]:
        with self._lock:
            orders = [Order.from_dict(item) for item in self._read_payload()["orders"]]
        return [item for item in orders if item.user_id == user_id]

    def _read_payload(self) -> dict:
        if not self.storage_path.exists():
            return {"orders": []}
        return json.loads(self.storage_path.read_text(encoding="utf-8"))

    def _write_payload(self, payload: dict) -> None:
        self.storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
