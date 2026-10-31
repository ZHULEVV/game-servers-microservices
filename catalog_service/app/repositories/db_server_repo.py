from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.server import Server, ServerStatus
from app.schemas.server import ProcessedEventDB, ServerDB


class DbServerRepo:
    """Реализация поверх PostgreSQL. Интерфейс тот же, что у LocalServerRepo."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, server: Server) -> Server:
        self.db.add(ServerDB(**server.model_dump()))
        self.db.commit()
        return server

    def get_by_id(self, server_id: UUID) -> Server:
        row = self.db.get(ServerDB, server_id)
        if row is None:
            raise KeyError(f"Server {server_id} not found")
        return Server.model_validate(row)

    def update(self, server: Server) -> Server:
        row = self.db.get(ServerDB, server.id)
        if row is None:
            raise KeyError(f"Server {server.id} not found")
        for field, value in server.model_dump().items():
            setattr(row, field, value)
        self.db.commit()
        return server

    def list(self, game, region, min_slots, max_price, offset, count):
        q = self.db.query(ServerDB).filter(ServerDB.status == ServerStatus.ACTIVE)
        if game:
            q = q.filter(ServerDB.game == game)
        if region:
            q = q.filter(ServerDB.region == region)
        if min_slots is not None:
            q = q.filter(ServerDB.slots >= min_slots)
        if max_price is not None:
            q = q.filter(ServerDB.price_per_hour <= max_price)
        total = q.count()
        rows = q.order_by(ServerDB.price_per_hour, ServerDB.name).offset(offset).limit(count).all()
        return [Server.model_validate(r) for r in rows], total

    def is_event_processed(self, event_id: str) -> bool:
        return self.db.get(ProcessedEventDB, event_id) is not None

    def mark_event_processed(self, event_id: str) -> None:
        try:
            self.db.add(ProcessedEventDB(event_id=event_id))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
