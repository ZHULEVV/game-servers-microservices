import asyncio
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, Field

from app.dependencies import get_service
from app.errors import Forbidden
from app.models.payment import Payment, PaymentStatus
from app.security import Principal, get_principal
from app.services.payment_service import PaymentService
from app.settings import settings

router = APIRouter(prefix="/payments", tags=["Payments"])


class CreatePaymentRequest(BaseModel):
    booking_id: UUID
    user_id: UUID
    amount: Decimal = Field(description="Сумма счёта, > 0")
    card_token: str | None = None


class RefundRequest(BaseModel):
    reason: str | None = None


class PaymentPage(BaseModel):
    items: list[Payment]
    offset: int
    count: int
    total: int


async def charge_in_background(payment_id: UUID) -> None:
    """Обращение к платёжному шлюзу: происходит после ответа клиенту, результат уходит событием."""
    from app.database import SessionLocal
    from app.clients.gateway import FakeGateway
    from app.events import RabbitPublisher
    from app.repositories.db_payment_repo import DbPaymentRepo

    await asyncio.sleep(settings.gateway_delay_seconds)

    def run() -> None:
        db = SessionLocal()
        try:
            PaymentService(DbPaymentRepo(db), FakeGateway(settings.gateway_limit), RabbitPublisher()) \
                .process_payment(payment_id)
        finally:
            db.close()

    await asyncio.to_thread(run)


def _check_access(payment: Payment, who: Principal) -> None:
    if not who.privileged and payment.user_id != who.user_id:
        raise Forbidden("Нет доступа к чужому платежу")


@router.post("", status_code=201, response_model=Payment)
def create_payment(body: CreatePaymentRequest, background: BackgroundTasks,
                   who: Principal = Depends(get_principal),
                   service: PaymentService = Depends(get_service)) -> Payment:
    if not who.privileged:
        raise Forbidden("Счета выставляются только сервисом бронирования")
    payment = service.create_payment(body.booking_id, body.user_id, body.amount, body.card_token)
    background.add_task(charge_in_background, payment.id)
    return payment


@router.get("", response_model=PaymentPage)
def list_payments(booking_id: UUID | None = None, user_id: UUID | None = None, status: PaymentStatus | None = None,
                  offset: int = Query(default=0, ge=0), count: int = Query(default=20, ge=1, le=100),
                  who: Principal = Depends(get_principal),
                  service: PaymentService = Depends(get_service)) -> PaymentPage:
    if not who.privileged:
        if user_id not in (None, who.user_id):
            raise Forbidden("Можно запрашивать только свои платежи")
        user_id = who.user_id
    items, total = service.list_payments(booking_id, user_id, status, offset, count)
    return PaymentPage(items=items, offset=offset, count=count, total=total)


@router.get("/{payment_id}", response_model=Payment)
def get_payment(payment_id: UUID, who: Principal = Depends(get_principal),
                service: PaymentService = Depends(get_service)) -> Payment:
    payment = service.get_payment(payment_id)
    _check_access(payment, who)
    return payment


@router.post("/{payment_id}:refund", response_model=Payment)
def refund_payment(payment_id: UUID, body: RefundRequest | None = None, who: Principal = Depends(get_principal),
                   service: PaymentService = Depends(get_service)) -> Payment:
    _check_access(service.get_payment(payment_id), who)
    return service.refund_payment(payment_id, body.reason if body else None)
