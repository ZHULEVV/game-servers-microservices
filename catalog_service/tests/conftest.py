from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.events import FakePublisher
from app.main import app
from app.models.server import Server, ServerStatus
from app.repositories.local_server_repo import LocalServerRepo
from app.security import create_token
from app.services.server_service import ServerService

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
PROVIDER = UUID("00000000-0000-4000-8000-0000000000aa")
OTHER_PROVIDER = UUID("00000000-0000-4000-8000-0000000000bb")
MC = UUID("11111111-1111-4111-8111-111111111111")
CS = UUID("22222222-2222-4222-8222-222222222222")
ARK = UUID("33333333-3333-4333-8333-333333333333")
MC_LITE = UUID("44444444-4444-4444-8444-444444444444")


def make_server(server_id, name, game, region, slots, price, status=ServerStatus.ACTIVE) -> Server:
    return Server(id=server_id, name=name, game=game, region=region, slots=slots, price_per_hour=price,
                  provider_id=PROVIDER, status=status, created_at=NOW)


@pytest.fixture()
def repo() -> LocalServerRepo:
    repo = LocalServerRepo()
    for s in (make_server(MC, "Minecraft 8 GB", "minecraft", "eu", 20, 150), make_server(CS, "CS2 Competitive", "cs2", "eu", 10, 250),
              make_server(ARK, "ARK Survival", "ark", "us", 30, 400), make_server(MC_LITE, "Minecraft Lite", "minecraft", "us", 8, 90)):
        repo.add(s)
    return repo


@pytest.fixture()
def publisher() -> FakePublisher:
    return FakePublisher()


@pytest.fixture()
def service(repo, publisher) -> ServerService:
    # in-memory репозиторий с четырьмя серверами и подменённый брокер – без БД и RabbitMQ
    return ServerService(repo, publisher, clock=lambda: NOW)


@pytest.fixture()
def client(service):
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def bearer(user_id: UUID, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}
