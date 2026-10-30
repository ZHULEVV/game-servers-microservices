import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


class Payment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    booking_id: UUID
    user_id: UUID
    amount: Decimal
    status: PaymentStatus
    card_token: str | None = None
    fail_reason: str | None = None
    refund_reason: str | None = None
    created_at: datetime
