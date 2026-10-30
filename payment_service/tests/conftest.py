from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.clients.gateway import FakeGateway
from app.events import FakePublisher
from app.repositories.local_payment_repo import LocalPaymentRepo
from app.services.payment_service import PaymentService

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo() -> LocalPaymentRepo:
    return LocalPaymentRepo()


@pytest.fixture()
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture()
def service(repo, publisher) -> PaymentService:
    # in-memory репозиторий, шлюз-заглушка и подмена брокера – внешних зависимостей нет
    return PaymentService(repo, FakeGateway(limit=100000), publisher, clock=lambda: NOW)


@pytest.fixture()
def booking_id():
    return uuid4()


@pytest.fixture()
def user_id():
    return uuid4()


@pytest.fixture()
def paid(service, booking_id, user_id):
    """Оплаченный платёж на 450."""
    payment = service.create_payment(booking_id, user_id, Decimal("450"))
    return service.process_payment(payment.id)
