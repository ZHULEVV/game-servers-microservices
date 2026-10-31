from uuid import UUID

from app.models.server import Server, ServerStatus


class LocalServerRepo:
    """In-memory реализация (unit- и компонентные тесты)."""

    def __init__(self) -> None:
        self._items: dict[UUID, Server] = {}
        self._events: set[str] = set()

    def add(self, server: Server) -> Server:
        self._items[server.id] = server
        return server

    def get_by_id(self, server_id: UUID) -> Server:
        try:
            return self._items[server_id]
        except KeyError:
            raise KeyError(f"Server {server_id} not found") from None

    def update(self, server: Server) -> Server:
        self._items[server.id] = server
        return server

    def list(self, game, region, min_slots, max_price, offset, count):
        rows = [s for s in self._items.values() if s.status == ServerStatus.ACTIVE
                and (game is None or s.game == game) and (region is None or s.region == region)
                and (min_slots is None or s.slots >= min_slots) and (max_price is None or s.price_per_hour <= max_price)]
        rows.sort(key=lambda s: (s.price_per_hour, s.name))
        return rows[offset:offset + count], len(rows)

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self._events

    def mark_event_processed(self, event_id: str) -> None:
        self._events.add(event_id)
