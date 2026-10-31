from uuid import uuid4

from tests.conftest import SERVICE, bearer


def test_owner_reads_monitor_state(client, monitor):
    """GET /monitors/{id} владельцем → 200, состояние и пороги."""
    booking_id, user_id = monitor
    body = client.get(f"/api/monitors/{booking_id}", headers=bearer(user_id)).json()
    assert body["status"] == "active" and body["thresholds"] == {"cpu": 90, "ram": 90}


def test_monitor_access_control(client, monitor):
    """Без токена → 401; чужой пользователь → 403; администратор → 200; неизвестная бронь → 404."""
    booking_id, _ = monitor
    assert client.get(f"/api/monitors/{booking_id}").status_code == 401
    assert client.get(f"/api/monitors/{booking_id}", headers=bearer(uuid4())).status_code == 403
    assert client.get(f"/api/monitors/{booking_id}", headers=bearer(uuid4(), "admin")).status_code == 200
    resp = client.get(f"/api/monitors/{uuid4()}", headers=bearer(uuid4(), "admin"))
    assert resp.status_code == 404 and resp.json()["code"] == "not_found"


def test_agent_sample_creates_alert(client, monitor):
    """POST samples от агента (X-Service-Token) → 202; превышение порога попадает в журнал оповещений."""
    booking_id, user_id = monitor
    resp = client.post(f"/api/monitors/{booking_id}/samples", json={"cpu": 95, "ram": 40}, headers=SERVICE)
    assert resp.status_code == 202 and resp.json() == {"accepted": True, "alerts": 1}
    alerts = client.get(f"/api/monitors/{booking_id}/alerts", headers=bearer(user_id)).json()
    assert alerts["total"] == 1 and alerts["items"][0]["metric"] == "cpu"


def test_samples_from_ordinary_user_are_forbidden(client, monitor):
    """Метрики принимаются только от агента: пользователь получает 403."""
    booking_id, user_id = monitor
    resp = client.post(f"/api/monitors/{booking_id}/samples", json={"cpu": 95, "ram": 40}, headers=bearer(user_id))
    assert resp.status_code == 403


def test_put_thresholds_success(client, monitor):
    """PUT thresholds владельцем → 200 с новыми порогами."""
    booking_id, user_id = monitor
    resp = client.put(f"/api/monitors/{booking_id}/thresholds", json={"cpu": 80, "ram": 70}, headers=bearer(user_id))
    assert resp.status_code == 200 and resp.json()["thresholds"] == {"cpu": 80, "ram": 70}


def test_put_thresholds_out_of_range_returns_400(client, monitor):
    """Порог 150 % → 400 invalid_threshold."""
    booking_id, user_id = monitor
    resp = client.put(f"/api/monitors/{booking_id}/thresholds", json={"cpu": 150, "ram": 70}, headers=bearer(user_id))
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_threshold"


def test_put_thresholds_for_finished_booking_returns_409(client, booking, monitor):
    """Booking сообщил, что бронь завершена → 409 booking_closed."""
    booking_id, user_id = monitor
    booking.status = "finished"
    resp = client.put(f"/api/monitors/{booking_id}/thresholds", json={"cpu": 80, "ram": 70}, headers=bearer(user_id))
    assert resp.status_code == 409 and resp.json()["code"] == "booking_closed"


def test_put_thresholds_when_booking_down_returns_503(client, booking, monitor):
    """Booking Service недоступен → 503 dependency_unavailable."""
    booking_id, user_id = monitor
    booking.down = True
    resp = client.put(f"/api/monitors/{booking_id}/thresholds", json={"cpu": 80, "ram": 70}, headers=bearer(user_id))
    assert resp.status_code == 503 and resp.json()["code"] == "dependency_unavailable"


def test_alerts_pagination(client, monitor):
    """GET alerts: offset/count и total."""
    booking_id, user_id = monitor
    for value in (91, 92, 93):
        client.post(f"/api/monitors/{booking_id}/samples", json={"cpu": value, "ram": 10}, headers=SERVICE)
    page = client.get(f"/api/monitors/{booking_id}/alerts", params={"offset": 1, "count": 1}, headers=bearer(user_id)).json()
    assert page["total"] == 3 and len(page["items"]) == 1 and page["items"][0]["value"] == 92
