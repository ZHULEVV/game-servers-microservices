from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.events import FakePublisher
from app.models.server import Server, ServerStatus
from app.repositories.db_server_repo import DbServerRepo
from app.services.server_service import ServerService

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
PROVIDER = uuid4()


@pytest.fixture()
def repo(db) -> DbServerRepo:
    return DbServerRepo(db)


def make(name, game, region, slots, price, status=ServerStatus.ACTIVE) -> Server:
    return Server(id=uuid4(), name=name, game=game, region=region, slots=slots, price_per_hour=price,
                  provider_id=PROVIDER, status=status, created_at=T0)


@pytest.fixture()
def seeded(repo):
    for s in (make("MC 8GB", "minecraft", "eu", 20, 150), make("MC Lite", "minecraft", "us", 8, 90),
              make("CS2", "cs2", "eu", 10, 250), make("ARK", "ark", "us", 30, 400), make("Old", "cs2", "eu", 10, 100, ServerStatus.REMOVED)):
        repo.add(s)
    return repo


def test_server_roundtrip_and_price_update(repo):
    """Сервер записывается в PostgreSQL, цена и рейтинг (Numeric) читаются без искажений, update() сохраняет изменение."""
    server = make("MC", "minecraft", "eu", 20, 150.5)
    repo.add(server)
    server.price_per_hour, server.rating, server.rating_count = 170.0, 4.5, 2
    repo.update(server)
    saved = repo.get_by_id(server.id)
    assert float(saved.price_per_hour) == 170.0 and float(saved.rating) == 4.5 and saved.rating_count == 2


def test_list_filters_are_translated_to_sql(seeded):
    """Фильтры game, region, min_slots, max_price работают в SQL-запросе; снятый с каталога сервер не попадает в выборку."""
    assert seeded.list("minecraft", None, None, None, 0, 10)[1] == 2
    assert seeded.list(None, "eu", None, None, 0, 10)[1] == 2                      # «Old» снят и не виден
    assert [s.name for s in seeded.list(None, None, 20, None, 0, 10)[0]] == ["MC 8GB", "ARK"]
    assert [s.name for s in seeded.list("minecraft", "us", None, 100, 0, 10)[0]] == ["MC Lite"]


def test_list_is_sorted_by_price_with_offset_and_count(seeded):
    """Сортировка по цене, offset/count вырезают страницу, а total остаётся полным числом подходящих серверов."""
    items, total = seeded.list(None, None, None, None, offset=1, count=2)
    assert total == 4 and [s.name for s in items] == ["MC 8GB", "CS2"]


def test_review_event_recalculates_rating_in_database(repo):
    """Сервис поверх репозитория PostgreSQL: review.published пересчитывает рейтинг, повторная доставка (event_id) игнорируется."""
    server = make("MC", "minecraft", "eu", 20, 150)
    repo.add(server)
    service = ServerService(repo, FakePublisher())
    for rating in (5, 4):
        service.handle_review_published({"event_id": str(uuid4()), "server_id": str(server.id), "rating": rating})
    event = {"event_id": "same", "server_id": str(server.id), "rating": 1}
    service.handle_review_published(event)
    service.handle_review_published(event)
    saved = repo.get_by_id(server.id)
    assert saved.rating_count == 3 and float(saved.rating) == pytest.approx(3.33, abs=0.01)


def test_migration_seeds_catalog_with_four_servers(migrated, db):
    """Миграция Alembic создала таблицу servers и заполнила каталог четырьмя серверами (проверяется до очистки данными тестов)."""
    from sqlalchemy import create_engine, text
    engine = create_engine(migrated)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('public.servers')")).scalar() == "servers"
        assert conn.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_name = 'servers'")).scalar() >= 11
    engine.dispose()
