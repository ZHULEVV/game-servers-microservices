from uuid import UUID

from app.models.payment import Payment


class LocalPaymentRepo:
    """In-memory реализация (unit- и компонентные тесты)."""

    def __init__(self) -> None:
        self._items: dict[UUID, Payment] = {}
        self._events: set[str] = set()

    def add(self, payment: Payment) -> Payment:
        self._items[payment.id] = payment
        return payment

    def get_by_id(self, payment_id: UUID) -> Payment:
        try:
            return self._items[payment_id]
        except KeyError:
            raise KeyError(f"Payment {payment_id} not found") from None

    def update(self, payment: Payment) -> Payment:
        self._items[payment.id] = payment
        return payment

    def list(self, booking_id, user_id, status, offset, count):
        rows = sorted(self._items.values(), key=lambda p: p.created_at)
        if booking_id:
            rows = [p for p in rows if p.booking_id == booking_id]
        if user_id:
            rows = [p for p in rows if p.user_id == user_id]
        if status:
            rows = [p for p in rows if p.status == status]
        return rows[offset:offset + count], len(rows)

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self._events

    def mark_event_processed(self, event_id: str) -> None:
        self._events.add(event_id)
