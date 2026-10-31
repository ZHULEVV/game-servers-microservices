import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ServerStatus(str, enum.Enum):
    ACTIVE = "active"
    REMOVED = "removed"


class Server(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    game: str
    region: str
    slots: int
    price_per_hour: float
    rating: float | None = None
    rating_count: int = 0
    provider_id: UUID
    status: ServerStatus
    created_at: datetime
