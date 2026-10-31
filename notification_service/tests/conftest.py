from datetime import datetime, timedelta, timezone
from itertools import count
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.main import app
from app.repositories.local_notification_repo import LocalNotificationRepo
from app.security import create_token
from app.services.notification_service import NotificationService

START = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo() -> LocalNotificationRepo:
    return LocalNotificationRepo()


@pytest.fixture()
def service(repo) -> NotificationService:
    ticks = count()  # каждое обращение к часам – на минуту позже, чтобы порядок уведомлений был определённым
    return NotificationService(repo, clock=lambda: START + timedelta(minutes=next(ticks)))


@pytest.fixture()
def emit(service):
    """Фабрика: событие системы (routing key) для пользователя → созданное уведомление."""
    def make(routing_key, user_id, booking_id=None):
        event = {"event_id": str(uuid4()), "user_id": str(user_id)}
        if booking_id:
            event["booking_id"] = str(booking_id)
        return service.handle_event(routing_key, event)
    return make


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def client(service):
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def bearer(user_id: UUID, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}
