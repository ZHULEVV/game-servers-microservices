from uuid import uuid4

from tests.conftest import SERVICE


def start(client, booking_id=None, headers=SERVICE):
    return client.post("/api/deployments", json={"booking_id": str(booking_id or uuid4())}, headers=headers)


def test_start_returns_202_with_operation_id(client, booking):
    """POST /deployments → 202 Accepted, operation_id и deployment_id; Booking Service вызван."""
    booking_id = uuid4()
    resp = start(client, booking_id)
    body = resp.json()
    assert resp.status_code == 202 and body["operation_id"] and body["deployment_id"]
    assert booking.calls == [booking_id]


def test_operation_polling_shows_result(client):
    """GET /operations/{id}: после завершения фоновой задачи is_finished=true и результат с адресом и портом."""
    op_id = start(client).json()["operation_id"]
    body = client.get(f"/api/operations/{op_id}", headers=SERVICE).json()
    assert body["is_finished"] is True and body["result"]["status"] == "running" and body["result"]["port"]


def test_get_deployment_has_ip_and_port(client):
    """GET /deployments/{id} → 200, статус running, адрес и порт."""
    dep_id = start(client).json()["deployment_id"]
    body = client.get(f"/api/deployments/{dep_id}", headers=SERVICE).json()
    assert body["status"] == "running" and body["ip"].startswith("10.0.0.") and body["finished_at"]


def test_start_by_ordinary_user_is_forbidden(client):
    """Развёртывание запускает система или администратор: обычный пользователь → 403."""
    from tests.component.test_helpers import user_headers
    assert start(client, headers=user_headers(uuid4())).status_code == 403


def test_start_without_credentials_returns_401(client):
    """Без авторизации → 401."""
    assert start(client, headers={}).status_code == 401


def test_start_for_unconfirmed_booking_returns_409(client, booking):
    """Бронь не подтверждена → 409 booking_not_confirmed."""
    booking.status = "awaiting_payment"
    resp = start(client)
    assert resp.status_code == 409 and resp.json()["code"] == "booking_not_confirmed"


def test_start_twice_returns_409(client):
    """Повторный запуск для той же брони → 409 already_started."""
    booking_id = uuid4()
    start(client, booking_id)
    resp = start(client, booking_id)
    assert resp.status_code == 409 and resp.json()["code"] == "already_started"


def test_start_when_booking_down_returns_503(client, booking):
    """Booking Service недоступен → 503 dependency_unavailable."""
    booking.down = True
    resp = start(client)
    assert resp.status_code == 503 and resp.json()["code"] == "dependency_unavailable"


def test_stop_then_stop_again(client):
    """POST :stop: первый раз 200 и статус stopped, второй раз 409 invalid_status."""
    dep_id = start(client).json()["deployment_id"]
    first = client.post(f"/api/deployments/{dep_id}:stop", headers=SERVICE)
    assert first.status_code == 200 and first.json()["status"] == "stopped"
    second = client.post(f"/api/deployments/{dep_id}:stop", headers=SERVICE)
    assert second.status_code == 409 and second.json()["code"] == "invalid_status"


def test_unknown_ids_return_404(client):
    """Неизвестные операция, развёртывание и :stop → 404 not_found."""
    for url, method in ((f"/api/operations/{uuid4()}", "get"), (f"/api/deployments/{uuid4()}", "get"), (f"/api/deployments/{uuid4()}:stop", "post")):
        resp = getattr(client, method)(url, headers=SERVICE)
        assert resp.status_code == 404 and resp.json()["code"] == "not_found"
