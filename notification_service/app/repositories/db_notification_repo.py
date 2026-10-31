from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.schemas.notification import NotificationDB, ProcessedEventDB


class DbNotificationRepo:
    """Реализация поверх PostgreSQL. Интерфейс тот же, что у LocalNotificationRepo."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, note: Notification) -> Notification:
        self.db.add(NotificationDB(**note.model_dump()))
        self.db.commit()
        return note

    def get_by_id(self, note_id: UUID) -> Notification:
        row = self.db.get(NotificationDB, note_id)
        if row is None:
            raise KeyError(f"Notification {note_id} not found")
        return Notification.model_validate(row)

    def update(self, note: Notification) -> Notification:
        row = self.db.get(NotificationDB, note.id)
        if row is None:
            raise KeyError(f"Notification {note.id} not found")
        for field, value in note.model_dump().items():
            setattr(row, field, value)
        self.db.commit()
        return note

    def list(self, user_id, type, unread, offset, count):
        q = self.db.query(NotificationDB)
        if user_id:
            q = q.filter(NotificationDB.user_id == user_id)
        if type:
            q = q.filter(NotificationDB.type == type)
        if unread is not None:
            q = q.filter(NotificationDB.read == (not unread))
        total = q.count()
        rows = q.order_by(NotificationDB.created_at.desc()).offset(offset).limit(count).all()
        return [Notification.model_validate(r) for r in rows], total

    def is_event_processed(self, event_id: str) -> bool:
        return self.db.get(ProcessedEventDB, event_id) is not None

    def mark_event_processed(self, event_id: str) -> None:
        try:
            self.db.add(ProcessedEventDB(event_id=event_id))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
