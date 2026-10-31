import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Role(str, enum.Enum):
    USER = "user"
    PROVIDER = "provider"
    ADMIN = "admin"


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: Role
    password_hash: str
    created_at: datetime
