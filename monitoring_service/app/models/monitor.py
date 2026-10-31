from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Thresholds(BaseModel):
    cpu: int = 90
    ram: int = 90


class Monitor(BaseModel):
    booking_id: UUID
    user_id: UUID
    status: str = "active"          # active | stopped
    cpu: float = 0.0
    ram: float = 0.0
    thresholds: Thresholds = Thresholds()
    started_at: datetime


class Alert(BaseModel):
    id: UUID
    metric: str
    value: float
    threshold: int
    occurred_at: datetime
