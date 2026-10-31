from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Notification(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: str
    title: str
    body: str
    booking_id: UUID | None = None
    read: bool = False
    created_at: datetime
