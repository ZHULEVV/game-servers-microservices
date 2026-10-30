from datetime import datetime
from uuid import UUID

from app.models.booking import BUSY_STATUSES, Booking, BookingStatus


class LocalBookingRepo:
    """In-memory реализация (unit- и компонентные тесты)."""

    def __init__(self) -> None:
        self._items: dict[UUID, Booking] = {}
        self._events: set[str] = set()

    def add(self, booking: Booking) -> Booking:
        if booking.id in self._items:
            raise KeyError(f"Booking {booking.id} already exists")
        self._items[booking.id] = booking
        return booking

    def get_by_id(self, booking_id: UUID) -> Booking:
        try:
            return self._items[booking_id]
        except KeyError:
            raise KeyError(f"Booking {booking_id} not found") from None

    def update(self, booking: Booking) -> Booking:
        self._items[booking.id] = booking
        return booking

    def list(self, user_id, status, start_from, start_to, offset, count):
        rows = sorted(self._items.values(), key=lambda b: b.created_at)
        if user_id:
            rows = [b for b in rows if b.user_id == user_id]
        if status:
            rows = [b for b in rows if b.status == status]
        if start_from:
            rows = [b for b in rows if b.start >= start_from]
        if start_to:
            rows = [b for b in rows if b.start <= start_to]
        return rows[offset:offset + count], len(rows)

    def find_overlapping(self, server_id, start, end, exclude_id=None):
        return [b for b in self._items.values()
                if b.server_id == server_id and b.status in BUSY_STATUSES and b.id != exclude_id
                and b.start < end and start < b.end]

    def find_expired(self, now: datetime):
        return [b for b in self._items.values()
                if b.status in (BookingStatus.CONFIRMED, BookingStatus.ACTIVE) and b.end <= now]

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self._events

    def mark_event_processed(self, event_id: str) -> None:
        self._events.add(event_id)
