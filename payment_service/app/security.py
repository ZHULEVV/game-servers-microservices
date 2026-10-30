from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Header

from app.errors import DomainError
from app.settings import settings


class Unauthorized(DomainError):
    status, code = 401, "unauthorized"


@dataclass
class Principal:
    user_id: UUID | None = None
    role: str = "user"
    is_service: bool = False

    @property
    def privileged(self) -> bool:
        return self.is_service or self.role == "admin"


def create_token(user_id: UUID, role: str = "user", ttl_minutes: int = 60) -> str:
    """Токен, который в системе выдаёт Users Service (POST /users:login); здесь — для демо и тестов."""
    payload = {"sub": str(user_id), "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def get_principal(authorization: str | None = Header(default=None),
                  x_service_token: str | None = Header(default=None)) -> Principal:
    if x_service_token is not None:
        if x_service_token != settings.service_token:
            raise Unauthorized("Неверный X-Service-Token")
        return Principal(is_service=True)
    if not authorization or not authorization.startswith("Bearer "):
        raise Unauthorized("Требуется заголовок Authorization: Bearer <token>")
    try:
        data = jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"])
        return Principal(user_id=UUID(data["sub"]), role=data.get("role", "user"))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise Unauthorized("Недействительный токен") from None
