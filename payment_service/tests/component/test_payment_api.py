from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_service
from app.endpoints import payment_router
from app.main import app
from app.security import create_token

SERVICE = {"X-Service-Token": "service-secret"}


@pytest.fixture()
def client(service, monkeypatch):
    app.dependency_overrides[get_service] = lambda: service

    async def charge_now(payment_id):  # вместо паузы и реальной БД — сразу через тестовый сервис
        service.process_payment(payment_id)

    monkeypatch.setattr(payment_router, "charge_in_background", charge_now)
    yield TestClient(app)
    app.dependency_overrides.clear()


def user_auth(user_id):
    return {"Authorization": f"Bearer {create_token(user_id)}"}


def body(booking_id, user_id, amount="450.00", **extra):
    return {"booking_id": str(booking_id), "user_id": str(user_id), "amount": amount, **extra}


def test_create_payment_returns_pending_then_succeeds(client, booking_id, user_id):
    resp = client.post("/api/payments", json=body(booking_id, user_id), headers=SERVICE)
    assert resp.status_code == 201 and resp.json()["status"] == "pending"
    fetched = client.get(f"/api/payments/{resp.json()['id']}", headers=user_auth(user_id))
    assert fetched.status_code == 200 and fetched.json()["status"] == "succeeded"  # фоновое списание отработало


def test_declined_card_leads_to_failed_status(client, booking_id, user_id):
    created = client.post("/api/payments", json=body(booking_id, user_id, card_token="tok_fail"),
                          headers=SERVICE).json()
    stored = client.get(f"/api/payments/{created['id']}", headers=SERVICE).json()
    assert stored["status"] == "failed" and stored["fail_reason"] == "card_declined"


def test_create_payment_invalid_amount_returns_400(client, booking_id, user_id):
    resp = client.post("/api/payments", json=body(booking_id, user_id, amount="0"), headers=SERVICE)
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_amount"


def test_create_payment_by_ordinary_user_is_forbidden(client, booking_id, user_id):
    resp = client.post("/api/payments", json=body(booking_id, user_id), headers=user_auth(user_id))
    assert resp.status_code == 403


def test_requests_without_credentials_are_rejected(client, booking_id, user_id):
    assert client.post("/api/payments", json=body(booking_id, user_id)).status_code == 401
    assert client.post("/api/payments", json=body(booking_id, user_id),
                       headers={"X-Service-Token": "wrong"}).status_code == 401


def test_get_unknown_payment_returns_404(client, user_id):
    assert client.get(f"/api/payments/{uuid4()}", headers=user_auth(user_id)).status_code == 404


def test_get_foreign_payment_is_forbidden(client, booking_id, user_id):
    created = client.post("/api/payments", json=body(booking_id, user_id), headers=SERVICE).json()
    assert client.get(f"/api/payments/{created['id']}", headers=user_auth(uuid4())).status_code == 403


def test_list_filters_and_pagination(client, user_id):
    booking = uuid4()
    for amount in ("100", "200", "300"):
        client.post("/api/payments", json=body(booking, user_id, amount=amount), headers=SERVICE)
    client.post("/api/payments", json=body(uuid4(), user_id), headers=SERVICE)
    page = client.get("/api/payments", params={"booking_id": str(booking), "offset": 1, "count": 2},
                      headers=user_auth(user_id)).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and Decimal(page["items"][0]["amount"]) == Decimal("200")


def test_refund_paid_payment(client, booking_id, user_id):
    created = client.post("/api/payments", json=body(booking_id, user_id), headers=SERVICE).json()
    resp = client.post(f"/api/payments/{created['id']}:refund", json={"reason": "тест"}, headers=user_auth(user_id))
    assert resp.status_code == 200 and resp.json()["status"] == "refunded"


def test_refund_failed_payment_returns_409(client, booking_id, user_id):
    created = client.post("/api/payments", json=body(booking_id, user_id, card_token="tok_fail"),
                          headers=SERVICE).json()
    resp = client.post(f"/api/payments/{created['id']}:refund", json={}, headers=user_auth(user_id))
    assert resp.status_code == 409 and resp.json()["code"] == "invalid_status"
