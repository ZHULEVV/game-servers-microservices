from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.dependencies import get_service
from app.errors import forbidden
from app.models.server import Server
from app.security import Principal, get_principal
from app.services.server_service import ServerService

router = APIRouter(tags=["Servers"])


class CreateServerRequest(BaseModel):
    name: str
    game: str
    region: str
    slots: int
    price_per_hour: float


class PriceRequest(BaseModel):
    price_per_hour: float


class ServerPage(BaseModel):
    items: list[Server]
    offset: int
    count: int
    total: int


class Availability(BaseModel):
    available: bool
    price_per_hour: float


def need_provider(who: Principal) -> None:
    if not (who.privileged or who.role == "provider"):
        raise forbidden("Управлять каталогом могут провайдеры и администраторы")


@router.get("/servers", response_model=ServerPage)
def list_servers(game: str | None = None, region: str | None = None, min_slots: int | None = Query(default=None, ge=0),
                 max_price: float | None = Query(default=None, ge=0), offset: int = Query(default=0, ge=0),
                 count: int = Query(default=20, ge=1, le=100), service: ServerService = Depends(get_service)):
    items, total = service.list_servers(game, region, min_slots, max_price, offset, count)
    return ServerPage(items=items, offset=offset, count=count, total=total)


@router.get("/servers/{server_id}", response_model=Server)
def get_server(server_id: UUID, service: ServerService = Depends(get_service)):
    return service.get_server(server_id)


@router.get("/servers/{server_id}/availability", response_model=Availability)
def availability(server_id: UUID, from_: datetime = Query(alias="from"), to: datetime = Query(),
                 who: Principal = Depends(get_principal), service: ServerService = Depends(get_service)):
    available, price = service.availability(server_id, from_, to)
    return Availability(available=available, price_per_hour=price)


@router.post("/servers", status_code=201, response_model=Server)
def create_server(body: CreateServerRequest, who: Principal = Depends(get_principal), service: ServerService = Depends(get_service)):
    need_provider(who)
    provider = who.user_id or UUID("00000000-0000-4000-8000-0000000000aa")
    return service.add_server(provider, body.name, body.game, body.region, body.slots, body.price_per_hour)


@router.patch("/servers/{server_id}/price", response_model=Server)
def change_price(server_id: UUID, body: PriceRequest, who: Principal = Depends(get_principal), service: ServerService = Depends(get_service)):
    need_provider(who)
    return service.change_price(server_id, body.price_per_hour, who.user_id, who.privileged)
