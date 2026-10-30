import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BookingStatus(str, enum.Enum):
    CREATED = "created"
    AWAITING_PAYMENT = "awaiting_payment"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"


# статусы, в которых бронь занимает слот сервера
BUSY_STATUSES = (
    BookingStatus.CREATED,
    BookingStatus.AWAITING_PAYMENT,
    BookingStatus.CONFIRMED,
    BookingStatus.ACTIVE,
)


class Booking(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    server_id: UUID
    start: datetime
    end: datetime
    status: BookingStatus
    amount: Decimal
    cancel_reason: str | None = None
    created_at: datetime
