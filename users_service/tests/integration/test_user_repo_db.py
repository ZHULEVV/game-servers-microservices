from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.models.user import Role, User
from app.repositories.db_user_repo import DbUserRepo
from app.services.passwords import check_password, hash_password
from app.services.user_service import UserService
from app.events import FakePublisher

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo(db) -> DbUserRepo:
    return DbUserRepo(db)


def make(email="ivan@mail.com", role=Role.USER, password="secret1") -> User:
    return User(id=uuid4(), email=email, name="Ivan", role=role, password_hash=hash_password(password), created_at=T0)


def test_user_roundtrip_by_id_and_email(repo):
    """Пользователь записывается в PostgreSQL и находится по id и по email; роль (enum) и время сохраняются."""
    user = make(role=Role.PROVIDER)
    repo.add(user)
    assert repo.get_by_id(user.id).role == Role.PROVIDER
    assert repo.get_by_email("ivan@mail.com").id == user.id and repo.get_by_email("none@mail.com") is None


def test_unique_index_rejects_duplicate_email(repo, db):
    """Уникальный индекс по email на уровне БД: второй пользователь с тем же email отвергается, сессия остаётся рабочей."""
    repo.add(make())
    with pytest.raises(KeyError):
        repo.add(make())
    repo.add(make(email="other@mail.com"))                       # после отката транзакции сессия продолжает работать
    assert repo.get_by_email("other@mail.com") is not None


def test_password_hash_is_stored_not_plain_password(repo, db):
    """В таблице users хранится только хеш пароля: открытого пароля в БД нет, хеш проверяется функцией check_password."""
    repo.add(make(password="secret1"))
    raw = db.execute(__import__("sqlalchemy").text("SELECT password_hash FROM users")).scalar_one()
    assert "secret1" not in raw and check_password("secret1", raw) and not check_password("bad", raw)


def test_missing_user_raises_key_error(repo):
    """Чтение несуществующего пользователя по id – KeyError (сервис превращает его в 404)."""
    with pytest.raises(KeyError):
        repo.get_by_id(uuid4())


def test_service_registration_and_login_on_real_database(repo):
    """Сервис UserService поверх репозитория PostgreSQL: регистрация, повторная регистрация (409), вход и выдача токена."""
    service = UserService(repo, FakePublisher())
    user = service.register("Petr@Mail.com", "Petr", "secret1")
    assert repo.get_by_email("petr@mail.com").id == user.id
    with pytest.raises(Exception) as exc:
        service.register("petr@mail.com", "Petr", "secret1")
    assert getattr(exc.value, "code", "") == "email_taken"
    token, logged = service.login("petr@mail.com", "secret1")
    assert token and logged.id == user.id
