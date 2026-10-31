from uuid import uuid4

from tests.conftest import SERVER_ID, bearer


def post_review(client, user_id, booking_id, rating=5, **extra):
    return client.post("/api/reviews", json={"booking_id": str(booking_id), "rating": rating, **extra}, headers=bearer(user_id))


def test_create_review_returns_201(client, finished, user_id):
    """POST /reviews для завершённой аренды → 201, сервер и автор взяты из события и токена."""
    booking_id = finished(user_id)
    resp = post_review(client, user_id, booking_id, 5, text="Отлично")
    body = resp.json()
    assert resp.status_code == 201 and body["server_id"] == str(SERVER_ID) and body["user_id"] == str(user_id)


def test_create_review_without_token_returns_401(client, finished, user_id):
    """Без токена отзыв не принимается (401)."""
    resp = client.post("/api/reviews", json={"booking_id": str(finished(user_id)), "rating": 5})
    assert resp.status_code == 401


def test_invalid_rating_returns_400(client, finished, user_id):
    """Оценка 7 → 400 invalid_rating."""
    resp = post_review(client, user_id, finished(user_id), 7)
    assert resp.status_code == 400 and resp.json()["code"] == "invalid_rating"


def test_review_before_finish_returns_409(client, user_id):
    """Аренда не завершена → 409 review_not_open."""
    resp = post_review(client, user_id, uuid4())
    assert resp.status_code == 409 and resp.json()["code"] == "review_not_open"


def test_duplicate_review_returns_409(client, finished, user_id):
    """Повторный отзыв на ту же аренду → 409 review_exists."""
    booking_id = finished(user_id)
    post_review(client, user_id, booking_id)
    resp = post_review(client, user_id, booking_id, 4)
    assert resp.status_code == 409 and resp.json()["code"] == "review_exists"


def test_users_service_unavailable_returns_503(client, users, finished, user_id):
    """Users Service недоступен → 503 dependency_unavailable."""
    booking_id = finished(user_id)
    users.down = True
    resp = post_review(client, user_id, booking_id)
    assert resp.status_code == 503 and resp.json()["code"] == "dependency_unavailable"


def test_get_review_and_404(client, finished, user_id):
    """GET /reviews/{id}: существующий → 200, неизвестный → 404."""
    created = post_review(client, user_id, finished(user_id), 4).json()
    assert client.get(f"/api/reviews/{created['id']}").status_code == 200
    assert client.get(f"/api/reviews/{uuid4()}").status_code == 404


def test_server_reviews_with_filter_pagination_and_average(client, finished):
    """GET /servers/{id}/reviews: min_rating, offset/count, total и средняя оценка."""
    for rating in (5, 4, 2):
        u = uuid4()
        post_review(client, u, finished(u), rating)
    page = client.get(f"/api/servers/{SERVER_ID}/reviews", params={"min_rating": 4, "count": 1}).json()
    assert page["total"] == 2 and len(page["items"]) == 1 and page["average_rating"] == 4.5 and page["count"] == 1


def test_server_reviews_invalid_min_rating_returns_400(client):
    """min_rating вне диапазона 1–5 → 400 validation_error."""
    resp = client.get(f"/api/servers/{SERVER_ID}/reviews", params={"min_rating": 9})
    assert resp.status_code == 400 and resp.json()["code"] == "validation_error"
