from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.dependencies import get_service
from app.errors import Forbidden
from app.models.booking import Booking, BookingStatus
from app.security import Principal, get_principal
from app.services.booking_service import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


class CreateBookingRequest(BaseModel):
    server_id: UUID
    start: datetime
    end: datetime
    card_token: str | None = Field(default=None, description="Токен карты (в учебной системе tok_fail имитирует отказ)")


class CancelRequest(BaseModel):
    reason: str | None = None


class ExtendRequest(BaseModel):
    new_end: datetime


class BookingPage(BaseModel):
    items: list[Booking]
    offset: int
    count: int
    total: int


def _check_access(booking: Booking, who: Principal) -> None:
    if not who.privileged and booking.user_id != who.user_id:
        raise Forbidden("Нет доступа к чужой брони")


@router.post("", status_code=201, response_model=Booking)
def create_booking(body: CreateBookingRequest, who: Principal = Depends(get_principal),
                   service: BookingService = Depends(get_service)) -> Booking:
    if who.user_id is None:
        raise Forbidden("Бронь создаётся от имени пользователя")
    return service.create_booking(who.user_id, body.server_id, body.start, body.end, body.card_token)


@router.get("", response_model=BookingPage)
def list_bookings(user_id: UUID | None = None, status: BookingStatus | None = None,
                  from_: datetime | None = Query(default=None, alias="from"), to: datetime | None = None,
                  offset: int = Query(default=0, ge=0), count: int = Query(default=20, ge=1, le=100),
                  who: Principal = Depends(get_principal),
                  service: BookingService = Depends(get_service)) -> BookingPage:
    if not who.privileged:
        if user_id not in (None, who.user_id):
            raise Forbidden("Можно запрашивать только свои брони")
        user_id = who.user_id
    items, total = service.list_bookings(user_id, status, from_, to, offset, count)
    return BookingPage(items=items, offset=offset, count=count, total=total)


@router.get("/{booking_id}", response_model=Booking)
def get_booking(booking_id: UUID, who: Principal = Depends(get_principal),
                service: BookingService = Depends(get_service)) -> Booking:
    booking = service.get_booking(booking_id)
    _check_access(booking, who)
    return booking


@router.post("/{booking_id}:cancel", response_model=Booking)
def cancel_booking(booking_id: UUID, body: CancelRequest | None = None, who: Principal = Depends(get_principal),
                   service: BookingService = Depends(get_service)) -> Booking:
    _check_access(service.get_booking(booking_id), who)
    return service.cancel_booking(booking_id, body.reason if body else None)


@router.post("/{booking_id}:extend", response_model=Booking)
def extend_booking(booking_id: UUID, body: ExtendRequest, who: Principal = Depends(get_principal),
                   service: BookingService = Depends(get_service)) -> Booking:
    _check_access(service.get_booking(booking_id), who)
    return service.extend_booking(booking_id, body.new_end)
