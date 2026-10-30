"""Deploy Service (:8006): развёртывание игровых серверов (долгая операция). Реализация контракта ПР6 + потребитель booking.confirmed."""
import asyncio
import json
import logging
import os
import random
from uuid import UUID, uuid4

import httpx
from aio_pika import ExchangeType, connect_robust
from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.common import AMQP_URL, SERVICE_TOKEN, ApiError, Principal, get_principal, install, new_event, now_iso, publish

log = logging.getLogger("deploy")
BOOKING_URL = os.getenv("BOOKING_URL", "http://localhost:8003")
DEPLOY_SECONDS = float(os.getenv("DEPLOY_SECONDS", "3"))
AUTO_DEPLOY = os.getenv("AUTO_DEPLOY", "true").lower() == "true"

app = FastAPI(title="Deploy Service", version="1.0")
install(app)

DEPLOYMENTS: dict[str, dict] = {}
OPERATIONS: dict[str, dict] = {}
SEEN: set[str] = set()


class StartDeployment(BaseModel):
    booking_id: UUID


async def run_deployment(dep: dict, op: dict) -> None:
    await asyncio.sleep(DEPLOY_SECONDS)
    dep.update(status="running", ip=f"10.0.0.{random.randint(10, 250)}", port=random.choice([25565, 27015, 7777]), finished_at=now_iso())
    op.update(is_finished=True, result={"deployment_id": dep["id"], "status": "running", "ip": dep["ip"], "port": dep["port"]})
    await asyncio.to_thread(publish, "deploy.events", "deploy.completed", new_event(
        booking_id=dep["booking_id"], user_id=dep["user_id"], ip=dep["ip"], port=dep["port"]))
    log.info("deployment %s finished", dep["id"])


def start(booking_id: str, user_id: str) -> tuple[dict, dict]:
    dep = {"id": str(uuid4()), "booking_id": booking_id, "user_id": user_id, "status": "provisioning", "ip": None, "port": None,
           "started_at": now_iso(), "finished_at": None}
    op = {"id": str(uuid4()), "deployment_id": dep["id"], "is_finished": False, "result": None}
    DEPLOYMENTS[dep["id"]] = dep
    OPERATIONS[op["id"]] = op
    asyncio.ensure_future(run_deployment(dep, op))
    return dep, op


async def consume():
    conn = await connect_robust(AMQP_URL)
    ch = await conn.channel()
    await ch.set_qos(prefetch_count=1)
    ex = await ch.declare_exchange("booking.events", ExchangeType.TOPIC, durable=True)
    q = await ch.declare_queue("deploy.booking.confirmed", durable=True)
    await q.bind(ex, routing_key="booking.confirmed")

    async def on_confirmed(msg):
        async with msg.process():
            ev = json.loads(msg.body)
            if ev["event_id"] in SEEN:
                return
            SEEN.add(ev["event_id"])
            if not AUTO_DEPLOY:
                log.info("RECEIVED booking.confirmed booking_id=%s (AUTO_DEPLOY=false, пропущено)", ev["booking_id"])
                return
            if any(d["booking_id"] == ev["booking_id"] for d in DEPLOYMENTS.values()):
                return
            log.info("RECEIVED booking.confirmed booking_id=%s -> разворачиваем сервер", ev["booking_id"])
            start(ev["booking_id"], ev["user_id"])

    await q.consume(on_confirmed)
    return conn


@app.on_event("startup")
async def startup():
    asyncio.ensure_future(consume())


def find(deployment_id: UUID, who: Principal) -> dict:
    dep = DEPLOYMENTS.get(str(deployment_id))
    if dep is None:
        raise ApiError(404, "not_found", f"Развёртывание {deployment_id} не найдено")
    if not who.privileged and str(who.user_id) != dep["user_id"]:
        raise ApiError(403, "forbidden", "Нет доступа к чужому развёртыванию")
    return dep


@app.post("/api/deployments", status_code=202, tags=["Deployments"])
async def start_deployment(body: StartDeployment, who: Principal = Depends(get_principal)):
    if not who.privileged:
        raise ApiError(403, "forbidden", "Развёртывание запускает система или администратор")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{BOOKING_URL}/api/bookings/{body.booking_id}", headers={"X-Service-Token": SERVICE_TOKEN})
    except httpx.HTTPError:
        raise ApiError(503, "dependency_unavailable", "Booking Service недоступен") from None
    if resp.status_code == 404:
        raise ApiError(404, "booking_not_found", f"Бронь {body.booking_id} не найдена")
    if resp.status_code != 200:
        raise ApiError(503, "dependency_unavailable", f"Booking Service ответил {resp.status_code}")
    booking = resp.json()
    if booking["status"] != "confirmed":
        raise ApiError(409, "booking_not_confirmed", f"Бронь в статусе {booking['status']}: развёртывание возможно только для confirmed")
    if any(d["booking_id"] == str(body.booking_id) and d["status"] in ("provisioning", "running") for d in DEPLOYMENTS.values()):
        raise ApiError(409, "already_started", "Для этой брони развёртывание уже запущено")
    dep, op = start(str(body.booking_id), booking["user_id"])
    return {"operation_id": op["id"], "deployment_id": dep["id"]}


@app.get("/api/operations/{operation_id}", tags=["Deployments"])
def get_operation(operation_id: UUID, who: Principal = Depends(get_principal)):
    op = OPERATIONS.get(str(operation_id))
    if op is None:
        raise ApiError(404, "not_found", f"Операция {operation_id} не найдена")
    find(UUID(op["deployment_id"]), who)
    return {"id": op["id"], "is_finished": op["is_finished"], "result": op["result"]}


@app.get("/api/deployments/{deployment_id}", tags=["Deployments"])
def get_deployment(deployment_id: UUID, who: Principal = Depends(get_principal)):
    dep = find(deployment_id, who)
    return {k: dep[k] for k in ("id", "booking_id", "status", "ip", "port", "started_at", "finished_at")}


@app.post("/api/deployments/{deployment_id}:stop", tags=["Deployments"])
def stop_deployment(deployment_id: UUID, who: Principal = Depends(get_principal)):
    dep = find(deployment_id, who)
    if dep["status"] != "running":
        raise ApiError(409, "invalid_status", f"Остановить можно только запущенный сервер, текущий статус — {dep['status']}")
    dep.update(status="stopped", finished_at=now_iso())
    return {k: dep[k] for k in ("id", "booking_id", "status", "ip", "port", "started_at", "finished_at")}
