from sqlalchemy import Column, DateTime, Enum, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.payment import PaymentStatus
from app.schemas.base_schema import Base


class PaymentDB(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True)
    booking_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(Enum(PaymentStatus, name="payment_status", values_callable=lambda e: [x.value for x in e]),
                    nullable=False)
    card_token = Column(String, nullable=True)
    fail_reason = Column(String, nullable=True)
    refund_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ProcessedEventDB(Base):
    __tablename__ = "processed_events"

    event_id = Column(String, primary_key=True)
