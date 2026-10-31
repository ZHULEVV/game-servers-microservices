from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.errors import DomainError, not_found
from app.events import make_event
from app.models.server import Server, ServerStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ServerService:
    def __init__(self, repo, publisher, clock=utcnow) -> None:
        self.repo = repo
        self.publisher = publisher
        self.clock = clock

    # ---------- синхронные команды ----------
    def list_servers(self, game=None, region=None, min_slots=None, max_price=None, offset=0, count=20):
        return self.repo.list(game.lower() if game else None, region.lower() if region else None, min_slots, max_price, offset, count)

    def get_server(self, server_id: UUID) -> Server:
        try:
            return self.repo.get_by_id(server_id)
        except KeyError:
            raise not_found(f"Сервер {server_id}") from None

    def availability(self, server_id: UUID, start: datetime, end: datetime) -> tuple[bool, float]:
        """Доступность сервера в каталоге и цена за час. Пересечения с бронями проверяет сам Booking Service."""
        if end <= start:
            raise DomainError(400, "invalid_dates", "Параметр to должен быть позже from")
        server = self.get_server(server_id)
        return server.status == ServerStatus.ACTIVE, server.price_per_hour

    def add_server(self, provider_id: UUID, name: str, game: str, region: str, slots: int, price_per_hour: float) -> Server:
        if slots <= 0 or price_per_hour <= 0:
            raise DomainError(400, "invalid_params", "slots и price_per_hour должны быть больше нуля")
        server = Server(id=uuid4(), name=name.strip(), game=game.lower(), region=region.lower(), slots=slots,
                        price_per_hour=price_per_hour, provider_id=provider_id, status=ServerStatus.ACTIVE, created_at=self.clock())
        return self.repo.add(server)

    def change_price(self, server_id: UUID, new_price: float, who_id: UUID | None, privileged: bool) -> Server:
        server = self.get_server(server_id)
        if not privileged and server.provider_id != who_id:
            raise DomainError(403, "forbidden", "Менять цену может только владелец сервера")
        if new_price <= 0:
            raise DomainError(400, "invalid_price", "Цена должна быть больше нуля")
        old, server.price_per_hour = server.price_per_hour, new_price
        self.repo.update(server)
        self.publisher.publish("catalog.price_changed", make_event(server_id=str(server.id), old_price=str(old), new_price=str(new_price)))
        return server

    # ---------- реакция на сообщение ----------
    def handle_review_published(self, event: dict) -> None:
        """review.published → пересчитать средний рейтинг сервера."""
        if self.repo.is_event_processed(event["event_id"]):
            return
        self.repo.mark_event_processed(event["event_id"])
        server = self.get_server(UUID(event["server_id"]))
        total = (server.rating or 0) * server.rating_count + int(event["rating"])
        server.rating_count += 1
        server.rating = round(total / server.rating_count, 2)
        self.repo.update(server)
