from uuid import uuid4

from tests.conftest import ARK, MC, OTHER_PROVIDER, PROVIDER, bearer

PERIOD = {"from": "2026-11-01T10:00:00Z", "to": "2026-11-01T14:00:00Z"}
NEW_SERVER = {"name": "Rust PvP", "game": "rust", "region": "eu", "slots": 50, "price_per_hour": 300}


def test_list_with_filters_and_total(client):
    """GET /servers?game=minecraft&max_price=200 → 200, два сервера, поля Page."""
    body = client.get("/api/servers", params={"game": "minecraft", "max_price": 200}).json()
    assert body["total"] == 2 and body["offset"] == 0 and body["count"] == 20 and len(body["items"]) == 2


def test_list_pagination(client):
    """offset/count возвращают страницу, total остаётся полным."""
    body = client.get("/api/servers", params={"offset": 3, "count": 5}).json()
    assert body["total"] == 4 and len(body["items"]) == 1


def test_list_rejects_negative_offset(client):
    """Отрицательный offset → 400 validation_error."""
    resp = client.get("/api/servers", params={"offset": -1})
    assert resp.status_code == 400 and resp.json()["code"] == "validation_error"


def test_get_server_and_404(client):
    """GET /servers/{id}: существующий → 200, неизвестный → 404."""
    assert client.get(f"/api/servers/{ARK}").json()["name"] == "ARK Survival"
    resp = client.get(f"/api/servers/{uuid4()}")
    assert resp.status_code == 404 and resp.json()["code"] == "not_found"


def test_availability_for_service_caller(client):
    """GET availability с X-Service-Token (так вызывает Booking) → доступность и цена."""
    resp = client.get(f"/api/servers/{MC}/availability", params=PERIOD, headers={"X-Service-Token": "service-secret"})
    assert resp.status_code == 200 and resp.json() == {"available": True, "price_per_hour": 150.0}


def test_availability_requires_authorization(client):
    """Без авторизации availability → 401."""
    assert client.get(f"/api/servers/{MC}/availability", params=PERIOD).status_code == 401


def test_availability_inverted_period_returns_400(client):
    """Перепутанные даты → 400 invalid_dates."""
    resp = client.get(f"/api/servers/{MC}/availability", params={"from": PERIOD["to"], "to": PERIOD["from"]},
                      headers={"X-Service-Token": "service-secret"})
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_dates"


def test_create_server_by_user_is_forbidden(client):
    """Обычный пользователь не может добавлять серверы (403)."""
    assert client.post("/api/servers", json=NEW_SERVER, headers=bearer(uuid4())).status_code == 403


def test_create_server_by_provider(client):
    """Провайдер добавляет сервер → 201, владелец – из токена."""
    resp = client.post("/api/servers", json=NEW_SERVER, headers=bearer(PROVIDER, "provider"))
    body = resp.json()
    assert resp.status_code == 201 and body["provider_id"] == str(PROVIDER) and body["status"] == "active"


def test_change_price_owner_other_provider_and_unknown(client):
    """PATCH цены: владелец → 200; чужой провайдер → 403; неизвестный сервер → 404."""
    owner = bearer(PROVIDER, "provider")
    assert client.patch(f"/api/servers/{MC}/price", json={"price_per_hour": 175}, headers=owner).json()["price_per_hour"] == 175
    assert client.patch(f"/api/servers/{MC}/price", json={"price_per_hour": 99}, headers=bearer(OTHER_PROVIDER, "provider")).status_code == 403
    assert client.patch(f"/api/servers/{uuid4()}/price", json={"price_per_hour": 99}, headers=owner).status_code == 404
