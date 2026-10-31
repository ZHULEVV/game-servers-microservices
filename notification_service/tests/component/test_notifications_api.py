from uuid import uuid4

from tests.conftest import bearer


def test_user_sees_own_notifications_only(client, emit, user_id):
    """GET /notifications: пользователь получает только свои уведомления в формате Page."""
    emit("booking.created", user_id)
    emit("payment.succeeded", user_id)
    emit("booking.created", uuid4())
    body = client.get("/api/notifications", headers=bearer(user_id)).json()
    assert body["total"] == 2 and body["offset"] == 0 and body["count"] == 20 and len(body["items"]) == 2


def test_list_requires_authorization(client):
    """Без токена → 401."""
    assert client.get("/api/notifications").status_code == 401


def test_foreign_user_id_filter_is_forbidden_but_admin_allowed(client, emit, user_id):
    """Запрос чужих уведомлений → 403; администратору доступен любой user_id."""
    emit("booking.created", user_id)
    assert client.get("/api/notifications", params={"user_id": str(user_id)}, headers=bearer(uuid4())).status_code == 403
    body = client.get("/api/notifications", params={"user_id": str(user_id)}, headers=bearer(uuid4(), "admin")).json()
    assert body["total"] == 1


def test_type_filter_and_pagination(client, emit, user_id):
    """Фильтр type и пагинация count."""
    for key in ("booking.created", "payment.succeeded", "booking.created"):
        emit(key, user_id)
    body = client.get("/api/notifications", params={"type": "booking.created", "count": 1}, headers=bearer(user_id)).json()
    assert body["total"] == 2 and len(body["items"]) == 1


def test_mark_read_and_unread_filter(client, emit, user_id):
    """POST /notifications/{id}:read → 200, read=true; непрочитанных остаётся на одно меньше."""
    note = emit("booking.created", user_id)
    emit("payment.succeeded", user_id)
    resp = client.post(f"/api/notifications/{note.id}:read", headers=bearer(user_id))
    assert resp.status_code == 200 and resp.json()["read"] is True
    unread = client.get("/api/notifications", params={"unread": True}, headers=bearer(user_id)).json()
    assert unread["total"] == 1


def test_mark_foreign_notification_is_forbidden(client, emit, user_id):
    """Нельзя пометить чужое уведомление (403)."""
    note = emit("booking.created", user_id)
    assert client.post(f"/api/notifications/{note.id}:read", headers=bearer(uuid4())).status_code == 403


def test_mark_unknown_notification_returns_404(client):
    """Неизвестное уведомление → 404 not_found."""
    resp = client.post(f"/api/notifications/{uuid4()}:read", headers=bearer(uuid4()))
    assert resp.status_code == 404 and resp.json()["code"] == "not_found"


def test_invalid_uuid_returns_400(client, user_id):
    """Некорректный идентификатор в пути → 400 validation_error."""
    resp = client.post("/api/notifications/not-a-uuid:read", headers=bearer(user_id))
    assert resp.status_code == 400 and resp.json()["code"] == "validation_error"
