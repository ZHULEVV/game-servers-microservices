from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from fastapi import Header

from app.errors import DomainError, forbidden
from app.settings import settings


@dataclass
class Principal:
    user_id: UUID | None = None
    role: str = "user"
    is_service: bool = False

    @property
    def privileged(self) -> bool:
        return self.is_service or self.role == "admin"


def create_token(user_id: UUID, role: str = "user", ttl_minutes: int = 60) -> str:
    payload = {"sub": str(user_id), "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def optional_principal(authorization: str | None = Header(default=None),
                       x_service_token: str | None = Header(default=None)) -> Principal | None:
    if x_service_token is not None:
        if x_service_token != settings.service_token:
            raise DomainError(401, "unauthorized", "Неверный X-Service-Token")
        return Principal(is_service=True)
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise DomainError(401, "unauthorized", "Ожидается заголовок Authorization: Bearer <token>")
    try:
        data = jwt.decode(authorization[7:], settings.jwt_secret, algorithms=["HS256"])
        return Principal(user_id=UUID(data["sub"]), role=data.get("role", "user"))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise DomainError(401, "unauthorized", "Недействительный токен") from None


def get_principal(authorization: str | None = Header(default=None),
                  x_service_token: str | None = Header(default=None)) -> Principal:
    who = optional_principal(authorization, x_service_token)
    if who is None:
        raise DomainError(401, "unauthorized", "Требуется заголовок Authorization: Bearer <token>")
    return who


def require_owner_or_privileged(who: Principal, owner_id: UUID | str, what: str) -> None:
    if not who.privileged and str(who.user_id) != str(owner_id):
        raise forbidden(f"Нет доступа к чужому ресурсу: {what}")
