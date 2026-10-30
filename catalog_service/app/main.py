"""Catalog Service (:8002): каталог игровых серверов. Учебная in-memory реализация контракта ПР6."""
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel

from app.common import ApiError, Principal, get_principal, install, new_event, now_iso, optional_principal, page, publish

app = FastAPI(title="Catalog Service", version="1.0")
install(app)

PROVIDER = "00000000-0000-4000-8000-0000000000aa"
SERVERS: dict[str, dict] = {}
for sid, name, game, region, slots, price in (
        ("11111111-1111-4111-8111-111111111111", "Minecraft 8 GB", "minecraft", "eu", 20, 150),
        ("22222222-2222-4222-8222-222222222222", "CS2 Competitive", "cs2", "eu", 10, 250),
        ("33333333-3333-4333-8333-333333333333", "ARK Survival", "ark", "us", 30, 400),
        ("44444444-4444-4444-8444-444444444444", "Minecraft Lite", "minecraft", "us", 8, 90)):
    SERVERS[sid] = {"id": sid, "name": name, "game": game, "region": region, "slots": slots, "price_per_hour": price,
                    "rating": None, "provider_id": PROVIDER, "status": "active", "created_at": now_iso()}


class CreateServer(BaseModel):
    name: str
    game: str
    region: str
    slots: int
    price_per_hour: float


class PriceUpdate(BaseModel):
    price_per_hour: float


def need_provider(who: Principal) -> None:
    if not (who.privileged or who.role == "provider"):
        raise ApiError(403, "forbidden", "Управлять каталогом могут провайдеры и администраторы")


def find(server_id: UUID) -> dict:
    server = SERVERS.get(str(server_id))
    if server is None:
        raise ApiError(404, "not_found", f"Сервер {server_id} не найден")
    return server


@app.get("/api/servers", tags=["Servers"])
def list_servers(game: str | None = None, region: str | None = None, min_slots: int | None = Query(default=None, ge=0),
                 max_price: float | None = Query(default=None, ge=0), offset: int = Query(default=0, ge=0),
                 count: int = Query(default=20, ge=1, le=100)):
    items = [s for s in SERVERS.values() if s["status"] == "active"
             and (game is None or s["game"] == game) and (region is None or s["region"] == region)
             and (min_slots is None or s["slots"] >= min_slots) and (max_price is None or s["price_per_hour"] <= max_price)]
    return page(items, offset, count)


@app.get("/api/servers/{server_id}", tags=["Servers"])
def get_server(server_id: UUID):
    return find(server_id)


@app.get("/api/servers/{server_id}/availability", tags=["Servers"])
def availability(server_id: UUID, from_: datetime = Query(alias="from"), to: datetime = Query(),
                 who: Principal = Depends(get_principal)):
    if to <= from_:
        raise ApiError(400, "invalid_dates", "Параметр to должен быть позже from")
    server = find(server_id)
    return {"available": server["status"] == "active", "price_per_hour": server["price_per_hour"]}


@app.post("/api/servers", status_code=201, tags=["Servers"])
def create_server(body: CreateServer, who: Principal = Depends(get_principal)):
    need_provider(who)
    if body.slots <= 0 or body.price_per_hour <= 0:
        raise ApiError(400, "invalid_params", "slots и price_per_hour должны быть больше нуля")
    server = {"id": str(uuid4()), "name": body.name, "game": body.game.lower(), "region": body.region.lower(), "slots": body.slots,
              "price_per_hour": body.price_per_hour, "rating": None, "provider_id": str(who.user_id) if who.user_id else PROVIDER,
              "status": "active", "created_at": now_iso()}
    SERVERS[server["id"]] = server
    return server


@app.patch("/api/servers/{server_id}/price", tags=["Servers"])
def change_price(server_id: UUID, body: PriceUpdate, who: Principal = Depends(get_principal)):
    need_provider(who)
    server = find(server_id)
    if not who.privileged and server["provider_id"] != str(who.user_id):
        raise ApiError(403, "forbidden", "Менять цену может только владелец сервера")
    if body.price_per_hour <= 0:
        raise ApiError(400, "invalid_price", "Цена должна быть больше нуля")
    old, server["price_per_hour"] = server["price_per_hour"], body.price_per_hour
    publish("catalog.events", "catalog.price_changed", new_event(server_id=server["id"], old_price=str(old), new_price=str(body.price_per_hour)))
    return server
