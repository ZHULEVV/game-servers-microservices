from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.errors import DomainError, unavailable
from app.events import FakePublisher
from app.main import app
from app.repositories.local_review_repo import LocalReviewRepo
from app.security import create_token
from app.services.review_service import ReviewService

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
SERVER_ID = UUID("11111111-1111-4111-8111-111111111111")


class FakeUsersClient:
    """Мок Users Service: запоминает проверенных авторов, может «упасть» или не найти пользователя."""

    def __init__(self) -> None:
        self.calls: list[UUID] = []
        self.down = False
        self.missing = False

    def get_user(self, user_id):
        if self.down:
            raise unavailable("Users Service", "ConnectError")
        if self.missing:
            raise DomainError(404, "author_not_found", f"Пользователь {user_id} не найден")
        self.calls.append(user_id)
        return {"id": str(user_id)}


@pytest.fixture()
def repo() -> LocalReviewRepo:
    return LocalReviewRepo()


@pytest.fixture()
def users() -> FakeUsersClient:
    return FakeUsersClient()


@pytest.fixture()
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture()
def service(repo, users, publisher) -> ReviewService:
    # in-memory репозиторий, мок Users Service и подменённый брокер – внешних зависимостей нет
    return ReviewService(repo, users, publisher, clock=lambda: NOW)


@pytest.fixture()
def finished(service):
    """Фабрика: завершённая аренда пользователя (событие booking.finished) → booking_id."""
    def make(user_id, server_id=SERVER_ID):
        booking_id = uuid4()
        service.handle_booking_finished({"event_id": str(uuid4()), "booking_id": str(booking_id),
                                         "user_id": str(user_id), "server_id": str(server_id)})
        return booking_id
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
