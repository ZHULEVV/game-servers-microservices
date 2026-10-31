from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.main import app
from app.models.booking import BookingStatus
from app.security import create_token
from tests.conftest import NOW, SERVER_ID


@pytest.fixture()
def client(service):
    app.dependency_overrides[get_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def auth(user_id: UUID, role="user"):
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}


def payload(period, **extra):
    return {"server_id": str(SERVER_ID), "start": period[0].isoformat(), "end": period[1].isoformat(), **extra}


def test_create_booking_success(client, user_id, period, payment):
    """POST /bookings → 201, awaiting_payment, 450.00, владелец из токена, Payment вызван."""
    resp = client.post("/api/bookings", json=payload(period), headers=auth(user_id))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "awaiting_payment" and body["amount"] == "450.00" and body["user_id"] == str(user_id)
    assert len(payment.calls) == 1                         # Payment Service вызван один раз


def test_create_booking_when_payment_is_down_returns_503(client, user_id, period, payment):
    """Payment недоступен → 503 dependency_unavailable."""
    payment.down = True
    resp = client.post("/api/bookings", json=payload(period), headers=auth(user_id))
    assert resp.status_code == 503
    assert resp.json()["code"] == "dependency_unavailable"


def test_create_booking_slot_busy_returns_409(client, period):
    """Пересечение слотов → 409 slot_busy."""
    assert client.post("/api/bookings", json=payload(period), headers=auth(uuid4())).status_code == 201
    resp = client.post("/api/bookings", json=payload(period), headers=auth(uuid4()))
    assert resp.status_code == 409 and resp.json()["code"] == "slot_busy"


def test_create_booking_invalid_dates_returns_400(client, user_id, period):
    """Конец раньше начала → 400 invalid_dates."""
    resp = client.post("/api/bookings", json=payload((period[1], period[0])), headers=auth(user_id))
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_dates"


def test_requests_without_token_are_rejected(client, period):
    """Запросы без токена → 401."""
    assert client.post("/api/bookings", json=payload(period)).status_code == 401
    assert client.get("/api/bookings").status_code == 401


def test_list_with_filter_and_pagination(client, user_id, period):
    """Фильтр по статусу, offset/count, total; чужие брони не попадают в список."""
    for i in range(3):                                     # три брони подряд, без пересечений
        start = period[0] + timedelta(hours=3 * i)
        client.post("/api/bookings", json=payload((start, start + timedelta(hours=2))), headers=auth(user_id))
    client.post("/api/bookings", json=payload(period), headers=auth(uuid4()))  # чужая бронь
    page = client.get("/api/bookings", params={"status": "awaiting_payment", "offset": 1, "count": 1},
                      headers=auth(user_id)).json()
    assert page["total"] == 3 and page["offset"] == 1 and page["count"] == 1 and len(page["items"]) == 1
    assert client.get("/api/bookings", params={"status": "confirmed"}, headers=auth(user_id)).json()["total"] == 0


def test_get_unknown_booking_returns_404(client, user_id):
    """GET несуществующей брони → 404 not_found."""
    resp = client.get(f"/api/bookings/{uuid4()}", headers=auth(user_id))
    assert resp.status_code == 404 and resp.json()["code"] == "not_found"


def test_foreign_booking_is_forbidden(client, period):
    """Чужая бронь: пользователю 403, администратору 200."""
    booking = client.post("/api/bookings", json=payload(period), headers=auth(uuid4())).json()
    assert client.get(f"/api/bookings/{booking['id']}", headers=auth(uuid4())).status_code == 403
    assert client.get(f"/api/bookings/{booking['id']}", headers=auth(uuid4(), "admin")).status_code == 200


def test_cancel_twice_returns_409(client, user_id, period):
    """Первая отмена 200, повторная → 409 invalid_status."""
    booking = client.post("/api/bookings", json=payload(period), headers=auth(user_id)).json()
    first = client.post(f"/api/bookings/{booking['id']}:cancel", json={"reason": "тест"}, headers=auth(user_id))
    assert first.status_code == 200 and first.json()["status"] == "cancelled"
    second = client.post(f"/api/bookings/{booking['id']}:cancel", json={}, headers=auth(user_id))
    assert second.status_code == 409 and second.json()["code"] == "invalid_status"


def test_extend_unpaid_booking_returns_409(client, user_id, period):
    """Продление неоплаченной брони → 409."""
    booking = client.post("/api/bookings", json=payload(period), headers=auth(user_id)).json()
    resp = client.post(f"/api/bookings/{booking['id']}:extend",
                       json={"new_end": (period[1] + timedelta(hours=1)).isoformat()}, headers=auth(user_id))
    assert resp.status_code == 409
