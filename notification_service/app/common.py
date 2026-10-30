"""Общие соглашения API (ПР6): префикс /api, ошибки {code, message}, пагинация offset/count, авторизация Bearer JWT и X-Service-Token."""
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

JWT_SECRET = os.getenv("JWT_SECRET", "game-servers-jwt-secret-key-32-bytes")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "service-secret")
AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/")
log = logging.getLogger("service")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message or code


@dataclass
class Principal:
    user_id: UUID | None = None
    role: str = "user"
    is_service: bool = False

    @property
    def privileged(self) -> bool:
        return self.is_service or self.role == "admin"


def make_token(user_id: UUID, role: str = "user", ttl_minutes: int = 60) -> str:
    payload = {"sub": str(user_id), "role": role, "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def optional_principal(authorization: str | None = Header(default=None),
                       x_service_token: str | None = Header(default=None)) -> Principal | None:
    if x_service_token is not None:
        if x_service_token != SERVICE_TOKEN:
            raise ApiError(401, "unauthorized", "Неверный X-Service-Token")
        return Principal(is_service=True)
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise ApiError(401, "unauthorized", "Ожидается заголовок Authorization: Bearer <token>")
    try:
        data = jwt.decode(authorization[7:], JWT_SECRET, algorithms=["HS256"])
        return Principal(user_id=UUID(data["sub"]), role=data.get("role", "user"))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise ApiError(401, "unauthorized", "Недействительный токен") from None


def get_principal(authorization: str | None = Header(default=None),
                  x_service_token: str | None = Header(default=None)) -> Principal:
    who = optional_principal(authorization, x_service_token)
    if who is None:
        raise ApiError(401, "unauthorized", "Требуется заголовок Authorization: Bearer <token>")
    return who


def page(items: list, offset: int, count: int, **extra) -> dict:
    return {"items": items[offset:offset + count], "offset": offset, "count": count, "total": len(items), **extra}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_event(**fields) -> dict:
    return {"event_id": str(uuid4()), "occurred_at": now_iso(), **fields}


def publish(exchange: str, routing_key: str, payload: dict) -> None:
    """Публикация события в RabbitMQ (topic, durable). Недоступность брокера не ломает запрос."""
    try:
        import pika
        conn = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        try:
            ch = conn.channel()
            ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
            ch.basic_publish(exchange=exchange, routing_key=routing_key, body=json.dumps(payload, default=str, ensure_ascii=False),
                             properties=pika.BasicProperties(content_type="application/json", delivery_mode=2))
            log.info("PUBLISHED %s %s", routing_key, payload.get("event_id"))
        finally:
            conn.close()
    except Exception:
        log.exception("Не удалось опубликовать %s", routing_key)


def install(app: FastAPI) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content={"code": exc.code, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        err = exc.errors()[0]
        return JSONResponse(status_code=400, content={"code": "validation_error",
                            "message": f"{err['msg']} ({'.'.join(str(x) for x in err['loc'])})"})

    @app.get("/health", include_in_schema=False)
    def _health():
        return {"status": "ok"}
