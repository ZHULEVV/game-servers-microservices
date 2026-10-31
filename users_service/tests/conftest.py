from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.events import FakePublisher
from app.main import app
from app.repositories.local_user_repo import LocalUserRepo
from app.security import create_token
from app.services.user_service import UserService

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo() -> LocalUserRepo:
    return LocalUserRepo()


@pytest.fixture()
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture()
def service(repo, publisher) -> UserService:
    # внедряем in-memory репозиторий и подменённый брокер – без БД и RabbitMQ
    return UserService(repo, publisher, clock=lambda: NOW)


@pytest.fixture()
def registered(service):
    """Зарегистрированный пользователь ivan@mail.com / secret1."""
    return service.register("ivan@mail.com", "Ivan", "secret1")


@pytest.fixture()
def client(service):
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def bearer(user_id: UUID, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}
