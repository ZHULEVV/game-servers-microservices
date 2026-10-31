import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DeploymentStatus(str, enum.Enum):
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"


class Deployment(BaseModel):
    id: UUID
    booking_id: UUID
    user_id: UUID
    status: DeploymentStatus
    ip: str | None = None
    port: int | None = None
    started_at: datetime
    finished_at: datetime | None = None


class Operation(BaseModel):
    """Долгая операция развёртывания: клиент опрашивает её, пока is_finished не станет true."""
    id: UUID
    deployment_id: UUID
    is_finished: bool = False
    result: dict | None = None
