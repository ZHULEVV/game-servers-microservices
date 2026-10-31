from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.endpoints import deployment_router
from app.errors import DomainError, unavailable
from app.events import FakePublisher
from app.main import app
from app.repositories.local_deployment_repo import LocalDeploymentRepo
from app.services.deployment_service import DeploymentService

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
SERVICE = {"X-Service-Token": "service-secret"}


class FakeBookingClient:
    """Мок Booking Service: статус и владелец брони задаются тестом, сервис может «упасть» или не найти бронь."""

    def __init__(self) -> None:
        self.status = "confirmed"
        self.user_id = uuid4()
        self.down = False
        self.missing = False
        self.calls: list[UUID] = []

    def get_booking(self, booking_id):
        if self.down:
            raise unavailable("Booking Service", "ConnectError")
        if self.missing:
            raise DomainError(404, "booking_not_found", f"Бронь {booking_id} не найдена")
        self.calls.append(booking_id)
        return {"id": str(booking_id), "status": self.status, "user_id": str(self.user_id)}


@pytest.fixture()
def repo() -> LocalDeploymentRepo:
    return LocalDeploymentRepo()


@pytest.fixture()
def booking() -> FakeBookingClient:
    return FakeBookingClient()


@pytest.fixture()
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture()
def service(repo, booking, publisher) -> DeploymentService:
    # in-memory репозиторий, мок Booking Service и подменённый брокер – внешних зависимостей нет
    return DeploymentService(repo, booking, publisher, clock=lambda: NOW)


@pytest.fixture()
def client(service, monkeypatch):
    app.dependency_overrides[get_service] = lambda: service

    async def finish_now(deployment_id):  # вместо паузы развёртывания: завершаем операцию сразу, через тестовый сервис
        service.complete(deployment_id)

    monkeypatch.setattr(deployment_router, "run_deployment", finish_now)
    yield TestClient(app)
    app.dependency_overrides.clear()


def confirmed_event(booking_id=None, user_id=None) -> dict:
    return {"event_id": str(uuid4()), "booking_id": str(booking_id or uuid4()), "user_id": str(user_id or uuid4())}
