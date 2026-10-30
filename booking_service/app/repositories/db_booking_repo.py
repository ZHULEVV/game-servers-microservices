from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.booking import BUSY_STATUSES, Booking, BookingStatus
from app.schemas.booking import BookingDB, ProcessedEventDB


class DbBookingRepo:
    """Реализация поверх PostgreSQL. Интерфейс тот же, что у LocalBookingRepo."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, booking: Booking) -> Booking:
        self.db.add(BookingDB(**booking.model_dump()))
        self.db.commit()
        return booking

    def get_by_id(self, booking_id: UUID) -> Booking:
        row = self.db.get(BookingDB, booking_id)
        if row is None:
            raise KeyError(f"Booking {booking_id} not found")
        return Booking.model_validate(row)

    def update(self, booking: Booking) -> Booking:
        row = self.db.get(BookingDB, booking.id)
        if row is None:
            raise KeyError(f"Booking {booking.id} not found")
        for field, value in booking.model_dump().items():
            setattr(row, field, value)
        self.db.commit()
        return booking

    def list(self, user_id, status, start_from, start_to, offset, count):
        q = self.db.query(BookingDB)
        if user_id:
            q = q.filter(BookingDB.user_id == user_id)
        if status:
            q = q.filter(BookingDB.status == status)
        if start_from:
            q = q.filter(BookingDB.start >= start_from)
        if start_to:
            q = q.filter(BookingDB.start <= start_to)
        total = q.count()
        rows = q.order_by(BookingDB.created_at).offset(offset).limit(count).all()
        return [Booking.model_validate(r) for r in rows], total

    def find_overlapping(self, server_id, start, end, exclude_id=None):
        q = self.db.query(BookingDB).filter(
            BookingDB.server_id == server_id,
            BookingDB.status.in_(BUSY_STATUSES),
            BookingDB.start < end,
            BookingDB.end > start,
        )
        if exclude_id:
            q = q.filter(BookingDB.id != exclude_id)
        return [Booking.model_validate(r) for r in q.all()]

    def find_expired(self, now: datetime):
        rows = self.db.query(BookingDB).filter(
            BookingDB.status.in_([BookingStatus.CONFIRMED, BookingStatus.ACTIVE]), BookingDB.end <= now).all()
        return [Booking.model_validate(r) for r in rows]

    def is_event_processed(self, event_id: str) -> bool:
        return self.db.get(ProcessedEventDB, event_id) is not None

    def mark_event_processed(self, event_id: str) -> None:
        try:
            self.db.add(ProcessedEventDB(event_id=event_id))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
