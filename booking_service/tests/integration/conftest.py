import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SERVICE_DIR = Path(__file__).resolve().parents[2]
TABLES = ["bookings", "processed_events"]


@pytest.fixture(scope="session")
def pg_url():
    """Настоящий PostgreSQL: переменная TEST_DATABASE_URL (например, service-контейнер в CI) или одноразовый контейнер testcontainers."""
    url = os.getenv("TEST_DATABASE_URL")
    if url:
        yield url
        return
    postgres = pytest.importorskip("testcontainers.postgres", reason="нужен testcontainers или TEST_DATABASE_URL")
    with postgres.PostgresContainer("postgres:16-alpine", driver="psycopg2") as container:
        yield container.get_connection_url()


@pytest.fixture(scope="session")
def migrated(pg_url):
    """Схема создаётся теми же миграциями Alembic, что и при старте контейнера сервиса."""
    env = {**os.environ, "POSTGRES_URL": pg_url}
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=SERVICE_DIR, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return pg_url


@pytest.fixture()
def db(migrated):
    """Сессия SQLAlchemy; перед каждым тестом таблицы очищаются – тесты изолированы."""
    engine = create_engine(migrated)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(TABLES) + " CASCADE"))
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()
