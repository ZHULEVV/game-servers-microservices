from sqlalchemy import Column, DateTime, Enum, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.booking import BookingStatus
from app.schemas.base_schema import Base


class BookingDB(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    server_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    start = Column(DateTime(timezone=True), nullable=False)
    end = Column(DateTime(timezone=True), nullable=False)
    status = Column(Enum(BookingStatus, name="booking_status", values_callable=lambda e: [x.value for x in e]),
                    nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    cancel_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ProcessedEventDB(Base):
    __tablename__ = "processed_events"

    event_id = Column(String, primary_key=True)
