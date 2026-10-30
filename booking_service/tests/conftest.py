from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.errors import DependencyUnavailable
from app.events import FakePublisher
from app.repositories.local_booking_repo import LocalBookingRepo
from app.services.booking_service import BookingService

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
SERVER_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakePaymentClient:
    """Мок Payment Service: запоминает вызовы, может «упасть»."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.down = False

    def create_invoice(self, booking_id, user_id, amount, card_token):
        if self.down:
            raise DependencyUnavailable("Payment Service недоступен")
        self.calls.append({"booking_id": booking_id, "user_id": user_id, "amount": amount, "card_token": card_token})
        return {"id": str(uuid4()), "status": "pending"}


class FakeCatalogClient:
    """Мок Catalog Service: сервер всегда доступен, цена 150 за час."""

    def __init__(self) -> None:
        self.available = True

    def get_availability(self, server_id, start, end):
        return self.available, Decimal("150")


@pytest.fixture()
def repo() -> LocalBookingRepo:
    return LocalBookingRepo()


@pytest.fixture()
def payment() -> FakePaymentClient:
    return FakePaymentClient()


@pytest.fixture()
def catalog() -> FakeCatalogClient:
    return FakeCatalogClient()


@pytest.fixture()
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture()
def service(repo, payment, catalog, publisher) -> BookingService:
    # внедряем in-memory репозиторий и моки – без БД, брокера и соседних сервисов
    return BookingService(repo, payment, catalog, publisher, clock=lambda: NOW, min_hours=1)


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def period():
    return NOW + timedelta(hours=1), NOW + timedelta(hours=4)
