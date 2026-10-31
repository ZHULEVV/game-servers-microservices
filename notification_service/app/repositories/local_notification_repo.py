from uuid import UUID

from app.models.notification import Notification


class LocalNotificationRepo:
    """In-memory реализация (unit- и компонентные тесты)."""

    def __init__(self) -> None:
        self._items: dict[UUID, Notification] = {}
        self._events: set[str] = set()

    def add(self, note: Notification) -> Notification:
        self._items[note.id] = note
        return note

    def get_by_id(self, note_id: UUID) -> Notification:
        try:
            return self._items[note_id]
        except KeyError:
            raise KeyError(f"Notification {note_id} not found") from None

    def update(self, note: Notification) -> Notification:
        self._items[note.id] = note
        return note

    def list(self, user_id, type, unread, offset, count):
        rows = sorted(self._items.values(), key=lambda n: n.created_at, reverse=True)
        rows = [n for n in rows if (user_id is None or n.user_id == user_id) and (type is None or n.type == type)
                and (unread is None or n.read != unread)]
        return rows[offset:offset + count], len(rows)

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self._events

    def mark_event_processed(self, event_id: str) -> None:
        self._events.add(event_id)
