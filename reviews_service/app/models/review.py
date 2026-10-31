from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Review(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    booking_id: UUID
    server_id: UUID
    user_id: UUID
    rating: int
    text: str = ""
    created_at: datetime


class ReviewSlot(BaseModel):
    """Завершённая аренда, по которой можно оставить отзыв (создаётся событием booking.finished)."""
    booking_id: UUID
    user_id: UUID
    server_id: UUID
