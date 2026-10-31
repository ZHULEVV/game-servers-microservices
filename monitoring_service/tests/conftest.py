from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.errors import DomainError, unavailable
from app.events import FakePublisher
from app.main import app
from app.repositories.local_monitor_repo import LocalMonitorRepo
from app.security import create_token
from app.services.monitor_service import MonitorService

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
SERVICE = {"X-Service-Token": "service-secret"}


class FakeBookingClient:
    """Мок Booking Service: статус брони задаётся тестом, сервис может «упасть» или не найти бронь."""

    def __init__(self) -> None:
        self.status = "active"
        self.down = False
        self.missing = False
        self.calls: list[UUID] = []

    def get_booking(self, booking_id):
        if self.down:
            raise unavailable("Booking Service", "ConnectError")
        if self.missing:
            raise DomainError(404, "booking_not_found", f"Бронь {booking_id} не найдена")
        self.calls.append(booking_id)
        return {"id": str(booking_id), "status": self.status}


@pytest.fixture()
def repo() -> LocalMonitorRepo:
    return LocalMonitorRepo()


@pytest.fixture()
def booking() -> FakeBookingClient:
    return FakeBookingClient()


@pytest.fixture()
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture()
def service(repo, booking, publisher) -> MonitorService:
    # in-memory репозиторий, мок Booking Service и подменённый брокер – внешних зависимостей нет
    return MonitorService(repo, booking, publisher, clock=lambda: NOW)


@pytest.fixture()
def monitor(service):
    """Запущенный монитор (событие deploy.completed): возвращает (booking_id, user_id)."""
    booking_id, user_id = uuid4(), uuid4()
    service.handle_deploy_completed({"event_id": str(uuid4()), "booking_id": str(booking_id), "user_id": str(user_id)})
    return booking_id, user_id


@pytest.fixture()
def client(service):
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def bearer(user_id: UUID, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}
