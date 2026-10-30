"""Monitoring Service (:8005): метрики арендованных серверов и оповещения о превышении нагрузки."""
import asyncio
import json
import logging
from uuid import UUID, uuid4

from aio_pika import ExchangeType, connect_robust
from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel

from app.common import AMQP_URL, ApiError, Principal, get_principal, install, new_event, now_iso, page, publish

log = logging.getLogger("monitoring")
app = FastAPI(title="Monitoring Service", version="1.0")
install(app)

MONITORS: dict[str, dict] = {}   # booking_id -> монитор
ALERTS: dict[str, list] = {}     # booking_id -> оповещения
SEEN: set[str] = set()


class Thresholds(BaseModel):
    cpu: int
    ram: int


class Sample(BaseModel):
    cpu: float
    ram: float


async def consume():
    conn = await connect_robust(AMQP_URL)
    ch = await conn.channel()
    await ch.set_qos(prefetch_count=1)
    for ex_name, key, queue_name in (("deploy.events", "deploy.completed", "monitoring.deploy.completed"),
                                     ("booking.events", "booking.finished", "monitoring.booking.finished")):
        ex = await ch.declare_exchange(ex_name, ExchangeType.TOPIC, durable=True)
        q = await ch.declare_queue(queue_name, durable=True)
        await q.bind(ex, routing_key=key)

        async def handler(msg, key=key):
            async with msg.process():
                ev = json.loads(msg.body)
                if ev["event_id"] in SEEN:
                    return
                SEEN.add(ev["event_id"])
                bid = ev["booking_id"]
                if key == "deploy.completed":
                    MONITORS[bid] = {"booking_id": bid, "user_id": ev["user_id"], "status": "active", "cpu": 0.0, "ram": 0.0,
                                     "thresholds": {"cpu": 90, "ram": 90}, "started_at": now_iso()}
                    ALERTS.setdefault(bid, [])
                    log.info("RECEIVED deploy.completed booking_id=%s -> мониторинг запущен", bid)
                elif bid in MONITORS:
                    MONITORS[bid]["status"] = "stopped"
                    log.info("RECEIVED booking.finished booking_id=%s -> мониторинг остановлен", bid)

        await q.consume(handler)
    return conn


@app.on_event("startup")
async def startup():
    asyncio.ensure_future(consume())


def get_monitor(booking_id: UUID, who: Principal) -> dict:
    mon = MONITORS.get(str(booking_id))
    if mon is None:
        raise ApiError(404, "not_found", f"Мониторинг брони {booking_id} не найден")
    if not who.privileged and str(who.user_id) != mon["user_id"]:
        raise ApiError(403, "forbidden", "Нет доступа к мониторингу чужой брони")
    return mon


@app.get("/api/monitors/{booking_id}", tags=["Monitoring"])
def monitor_state(booking_id: UUID, who: Principal = Depends(get_principal)):
    return get_monitor(booking_id, who)


@app.get("/api/monitors/{booking_id}/alerts", tags=["Monitoring"])
def monitor_alerts(booking_id: UUID, offset: int = Query(default=0, ge=0), count: int = Query(default=20, ge=1, le=100),
                   who: Principal = Depends(get_principal)):
    get_monitor(booking_id, who)
    return page(list(reversed(ALERTS.get(str(booking_id), []))), offset, count)


@app.put("/api/monitors/{booking_id}/thresholds", tags=["Monitoring"])
def set_thresholds(booking_id: UUID, body: Thresholds, who: Principal = Depends(get_principal)):
    mon = get_monitor(booking_id, who)
    if not (1 <= body.cpu <= 100 and 1 <= body.ram <= 100):
        raise ApiError(400, "invalid_threshold", "Пороги должны быть в диапазоне 1–100 %")
    mon["thresholds"] = {"cpu": body.cpu, "ram": body.ram}
    return mon


@app.post("/api/monitors/{booking_id}/samples", status_code=202, tags=["Monitoring"])
def add_sample(booking_id: UUID, body: Sample, who: Principal = Depends(get_principal)):
    """Приём метрик от агента на игровом сервере (только межсервисный вызов)."""
    if not who.privileged:
        raise ApiError(403, "forbidden", "Метрики принимаются только от агента сервера")
    mon = get_monitor(booking_id, who)
    if mon["status"] != "active":
        raise ApiError(409, "monitor_stopped", "Мониторинг остановлен")
    mon["cpu"], mon["ram"] = body.cpu, body.ram
    alerts = []
    for metric, value in (("cpu", body.cpu), ("ram", body.ram)):
        limit = mon["thresholds"][metric]
        if value > limit:
            alert = {"id": str(uuid4()), "metric": metric, "value": value, "threshold": limit, "occurred_at": now_iso()}
            ALERTS[str(booking_id)].append(alert)
            alerts.append(alert)
            publish("monitoring.events", "monitoring.load_exceeded", new_event(
                booking_id=str(booking_id), user_id=mon["user_id"], metric=metric, value=value, threshold=limit))
    return {"accepted": True, "alerts": len(alerts)}
