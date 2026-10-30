"""Notification Service (:8007): уведомления клиентам по событиям системы."""
import asyncio
import json
import logging
from uuid import UUID, uuid4

from aio_pika import ExchangeType, connect_robust
from fastapi import Depends, FastAPI, Query

from app.common import AMQP_URL, ApiError, Principal, get_principal, install, now_iso, page

log = logging.getLogger("notification")
app = FastAPI(title="Notification Service", version="1.0")
install(app)

NOTIFICATIONS: list[dict] = []
SEEN: set[str] = set()
TEMPLATES = {  # routing key -> (заголовок, текст)
    "user.registered": ("Добро пожаловать!", "Аккаунт создан. Можно выбирать сервер и бронировать."),
    "booking.created": ("Бронь создана", "Бронь ждёт оплаты."),
    "booking.confirmed": ("Бронь подтверждена", "Оплата получена, сервер разворачивается."),
    "booking.cancelled": ("Бронь отменена", "Бронь отменена, оплаченные суммы будут возвращены."),
    "booking.extended": ("Аренда продлена", "Выставлен счёт на доплату."),
    "booking.finished": ("Аренда завершена", "Спасибо! Оставьте отзыв о сервере."),
    "payment.succeeded": ("Оплата прошла", "Квитанция отправлена на почту."),
    "payment.failed": ("Ошибка оплаты", "Платёж отклонён, бронь отменена."),
    "payment.refunded": ("Возврат средств", "Деньги возвращены на карту."),
    "deploy.completed": ("Сервер готов", "Данные для подключения доступны в личном кабинете."),
    "deploy.failed": ("Не удалось развернуть сервер", "Бронь будет отменена."),
    "monitoring.load_exceeded": ("Высокая нагрузка", "Нагрузка на сервер превысила порог."),
}


async def consume():
    conn = await connect_robust(AMQP_URL)
    ch = await conn.channel()
    queue = await ch.declare_queue("notification.all", durable=True)
    for name in ("booking.events", "payment.events", "deploy.events", "monitoring.events", "user.events"):
        ex = await ch.declare_exchange(name, ExchangeType.TOPIC, durable=True)
        await queue.bind(ex, routing_key="#")

    async def on_event(msg):
        async with msg.process():
            ev = json.loads(msg.body)
            if ev["event_id"] in SEEN or msg.routing_key not in TEMPLATES or not ev.get("user_id"):
                return
            SEEN.add(ev["event_id"])
            title, text = TEMPLATES[msg.routing_key]
            NOTIFICATIONS.append({"id": str(uuid4()), "user_id": ev["user_id"], "type": msg.routing_key, "title": title, "body": text,
                                  "booking_id": ev.get("booking_id"), "read": False, "created_at": now_iso()})
            log.info("NOTIFY %s user_id=%s", msg.routing_key, ev["user_id"])

    await queue.consume(on_event)
    return conn


@app.on_event("startup")
async def startup():
    asyncio.ensure_future(consume())


@app.get("/api/notifications", tags=["Notifications"])
def list_notifications(user_id: UUID | None = None, type: str | None = None, unread: bool | None = None,
                       offset: int = Query(default=0, ge=0), count: int = Query(default=20, ge=1, le=100),
                       who: Principal = Depends(get_principal)):
    if not who.privileged:
        if user_id not in (None, who.user_id):
            raise ApiError(403, "forbidden", "Можно запрашивать только свои уведомления")
        user_id = who.user_id
    items = [n for n in NOTIFICATIONS if (user_id is None or n["user_id"] == str(user_id)) and (type is None or n["type"] == type)
             and (unread is None or n["read"] != unread)]
    items.sort(key=lambda n: n["created_at"], reverse=True)
    return page(items, offset, count)


@app.post("/api/notifications/{notification_id}:read", tags=["Notifications"])
def mark_read(notification_id: UUID, who: Principal = Depends(get_principal)):
    note = next((n for n in NOTIFICATIONS if n["id"] == str(notification_id)), None)
    if note is None:
        raise ApiError(404, "not_found", f"Уведомление {notification_id} не найдено")
    if not who.privileged and note["user_id"] != str(who.user_id):
        raise ApiError(403, "forbidden", "Нельзя изменять чужие уведомления")
    note["read"] = True
    return note
