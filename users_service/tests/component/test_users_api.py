from uuid import uuid4

from tests.conftest import bearer


def register(client, email="ivan@mail.com", **extra):
    return client.post("/api/users", json={"email": email, "name": "Ivan", "password": "secret1", **extra})


def test_register_returns_201_without_password(client):
    """POST /users → 201, в ответе нет пароля и его хеша."""
    resp = register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "ivan@mail.com" and body["role"] == "user"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_returns_409(client):
    """Повторная регистрация → 409 email_taken."""
    register(client)
    resp = register(client)
    assert resp.status_code == 409 and resp.json()["code"] == "email_taken"


def test_register_invalid_email_returns_400(client):
    """Неверный email → 400 invalid_email."""
    resp = register(client, email="not-an-email")
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_email"


def test_register_missing_field_returns_400(client):
    """Нет обязательного поля → 400 validation_error в общем формате {code, message}."""
    resp = client.post("/api/users", json={"email": "a@b.ru"})
    assert resp.status_code == 400 and resp.json()["code"] == "validation_error"


def test_login_success_returns_token(client):
    """POST /users:login → 200, токен, роль и срок действия."""
    register(client)
    resp = client.post("/api/users:login", json={"email": "ivan@mail.com", "password": "secret1"})
    body = resp.json()
    assert resp.status_code == 200 and body["token"] and body["role"] == "user" and body["expires_in"] == 3600


def test_login_wrong_password_returns_401(client):
    """Неверный пароль → 401 invalid_credentials."""
    register(client)
    resp = client.post("/api/users:login", json={"email": "ivan@mail.com", "password": "bad"})
    assert resp.status_code == 401 and resp.json()["code"] == "invalid_credentials"


def test_get_own_profile_with_issued_token(client):
    """Токен, выданный при входе, открывает собственный профиль."""
    user = register(client).json()
    token = client.post("/api/users:login", json={"email": "ivan@mail.com", "password": "secret1"}).json()["token"]
    resp = client.get(f"/api/users/{user['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200 and resp.json()["id"] == user["id"]


def test_get_profile_without_token_returns_401(client):
    """Запрос профиля без токена → 401."""
    user = register(client).json()
    assert client.get(f"/api/users/{user['id']}").status_code == 401


def test_get_foreign_profile_is_forbidden_but_admin_allowed(client):
    """Чужой профиль → 403; администратору доступен."""
    user = register(client).json()
    assert client.get(f"/api/users/{user['id']}", headers=bearer(uuid4())).status_code == 403
    assert client.get(f"/api/users/{user['id']}", headers=bearer(uuid4(), "admin")).status_code == 200


def test_get_unknown_user_returns_404(client):
    """Несуществующий пользователь → 404 not_found."""
    resp = client.get(f"/api/users/{uuid4()}", headers=bearer(uuid4(), "admin"))
    assert resp.status_code == 404 and resp.json()["code"] == "not_found"
