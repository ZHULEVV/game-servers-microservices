import jwt
import pytest
from pydantic import ValidationError

from app.errors import DomainError
from app.models.user import Role, User
from app.services.passwords import check_password, hash_password
from app.settings import settings


def test_register_success_normalizes_email_and_publishes_event(service, publisher):
    """Регистрация: email приводится к нижнему регистру, роль user, пароль не хранится открытым, отправлено user.registered."""
    user = service.register("Ivan@Mail.com", " Ivan ", "secret1")
    assert user.email == "ivan@mail.com" and user.name == "Ivan" and user.role == Role.USER
    assert "secret1" not in user.password_hash
    key, event = publisher.sent[-1]
    assert key == "user.registered" and event["user_id"] == str(user.id) and "event_id" in event


@pytest.mark.parametrize("email", ["ivan", "ivan@", "@mail.com", "ivan mail@x.ru"])
def test_register_rejects_invalid_email(service, email):
    """Некорректный формат email отвергается кодом invalid_email."""
    with pytest.raises(DomainError) as exc:
        service.register(email, "Ivan", "secret1")
    assert exc.value.status == 400 and exc.value.code == "invalid_email"


def test_register_rejects_short_password(service):
    """Пароль короче 6 символов отвергается кодом weak_password."""
    with pytest.raises(DomainError) as exc:
        service.register("ivan@mail.com", "Ivan", "12345")
    assert exc.value.code == "weak_password"


def test_register_rejects_blank_name(service):
    """Пустое имя отвергается кодом invalid_name."""
    with pytest.raises(DomainError) as exc:
        service.register("ivan@mail.com", "   ", "secret1")
    assert exc.value.code == "invalid_name"


def test_register_duplicate_email_is_case_insensitive(service, registered, publisher):
    """Повторная регистрация того же email (в другом регистре) – 409 email_taken, событие не отправляется."""
    sent = len(publisher.sent)
    with pytest.raises(DomainError) as exc:
        service.register("IVAN@mail.com", "Другой", "secret2")
    assert exc.value.status == 409 and exc.value.code == "email_taken"
    assert len(publisher.sent) == sent


def test_login_returns_jwt_with_user_id_and_role(service, registered):
    """Вход выдаёт JWT, в котором закодированы идентификатор и роль пользователя."""
    token, user = service.login("Ivan@mail.com", "secret1")
    data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    assert data["sub"] == str(registered.id) and data["role"] == "user" and user.id == registered.id


def test_login_wrong_password(service, registered):
    """Неверный пароль – 401 invalid_credentials."""
    with pytest.raises(DomainError) as exc:
        service.login("ivan@mail.com", "wrong")
    assert exc.value.status == 401 and exc.value.code == "invalid_credentials"


def test_login_unknown_email_has_same_error_as_wrong_password(service):
    """Неизвестный email даёт ту же ошибку, что и неверный пароль (нельзя узнать, зарегистрирован ли адрес)."""
    with pytest.raises(DomainError) as exc:
        service.login("nobody@mail.com", "secret1")
    assert exc.value.status == 401 and exc.value.code == "invalid_credentials"


def test_get_unknown_user(service):
    """Запрос несуществующего пользователя – 404."""
    from uuid import uuid4
    with pytest.raises(DomainError) as exc:
        service.get_user(uuid4())
    assert exc.value.status == 404


def test_password_hash_is_salted_and_verifiable():
    """Хеш пароля содержит соль: одинаковые пароли дают разные хеши, проверка отличает верный пароль от неверного."""
    h1, h2 = hash_password("secret1"), hash_password("secret1")
    assert h1 != h2
    assert check_password("secret1", h1) and not check_password("secret2", h1)


def test_user_model_requires_fields():
    """Модель User не создаётся без обязательных полей."""
    with pytest.raises(ValidationError):
        User(email="a@b.ru")
