from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.errors import DomainError
from app.models.review import ReviewSlot
from tests.conftest import SERVER_ID


def test_create_review_success_publishes_event_and_checks_author(service, users, publisher, finished, user_id):
    """Успешный отзыв: сохранён, Users Service вызван один раз, отправлено review.published."""
    booking_id = finished(user_id)
    review = service.create_review(user_id, booking_id, 5, "Отлично")
    assert review.rating == 5 and review.server_id == SERVER_ID
    assert users.calls == [user_id]
    key, event = publisher.sent[-1]
    assert key == "review.published" and event["rating"] == 5 and event["server_id"] == str(SERVER_ID)


@pytest.mark.parametrize("rating", [0, 6, -1, 100])
def test_rating_must_be_between_1_and_5(service, finished, user_id, rating):
    """Оценка вне диапазона 1–5 отвергается кодом invalid_rating."""
    booking_id = finished(user_id)
    with pytest.raises(DomainError) as exc:
        service.create_review(user_id, booking_id, rating)
    assert exc.value.status == 400 and exc.value.code == "invalid_rating"


def test_review_text_length_limit(service, finished, user_id):
    """Текст длиннее 1000 символов отвергается кодом text_too_long."""
    with pytest.raises(DomainError) as exc:
        service.create_review(user_id, finished(user_id), 5, "x" * 1001)
    assert exc.value.code == "text_too_long"


def test_review_not_allowed_before_booking_finished(service, user_id):
    """Для аренды без события booking.finished отзыв не принимается (409 review_not_open)."""
    with pytest.raises(DomainError) as exc:
        service.create_review(user_id, uuid4(), 5)
    assert exc.value.status == 409 and exc.value.code == "review_not_open"


def test_review_on_foreign_booking_is_forbidden(service, finished, user_id):
    """Нельзя оставить отзыв на чужую аренду (403)."""
    booking_id = finished(user_id)
    with pytest.raises(DomainError) as exc:
        service.create_review(uuid4(), booking_id, 5)
    assert exc.value.status == 403


def test_one_review_per_booking(service, finished, user_id):
    """На одну аренду – один отзыв: второй отвергается кодом review_exists."""
    booking_id = finished(user_id)
    service.create_review(user_id, booking_id, 5)
    with pytest.raises(DomainError) as exc:
        service.create_review(user_id, booking_id, 4)
    assert exc.value.status == 409 and exc.value.code == "review_exists"


def test_users_service_down_gives_503_and_nothing_saved(service, users, publisher, repo, finished, user_id):
    """Users Service недоступен → 503; отзыв не сохраняется, событие не отправляется."""
    booking_id = finished(user_id)
    users.down = True
    with pytest.raises(DomainError) as exc:
        service.create_review(user_id, booking_id, 5)
    assert exc.value.status == 503
    assert repo.get_by_booking(booking_id) is None and publisher.sent == []


def test_author_missing_in_users_service(service, users, finished, user_id):
    """Users Service не знает автора → 404 author_not_found."""
    booking_id = finished(user_id)
    users.missing = True
    with pytest.raises(DomainError) as exc:
        service.create_review(user_id, booking_id, 5)
    assert exc.value.status == 404 and exc.value.code == "author_not_found"


def test_duplicate_booking_finished_event_is_ignored(service, repo, user_id):
    """Повторная доставка booking.finished с тем же event_id не открывает аренду заново."""
    booking_id = uuid4()
    event = {"event_id": str(uuid4()), "booking_id": str(booking_id), "user_id": str(user_id), "server_id": str(SERVER_ID)}
    service.handle_booking_finished(event)
    review = service.create_review(user_id, booking_id, 5)
    service.handle_booking_finished(event)
    assert repo.get_by_booking(booking_id).id == review.id


def test_server_reviews_filter_and_average(service, finished):
    """Список отзывов сервера: фильтр min_rating, пагинация и средняя оценка выборки."""
    for rating in (5, 3, 4):
        u = uuid4()
        service.create_review(u, finished(u), rating)
    items, total, avg = service.server_reviews(SERVER_ID, min_rating=4)
    assert total == 2 and avg == 4.5 and {r.rating for r in items} == {4, 5}
    items, total, avg = service.server_reviews(SERVER_ID, offset=1, count=1)
    assert total == 3 and len(items) == 1 and avg == 4.0


def test_get_unknown_review(service):
    """Несуществующий отзыв → 404."""
    with pytest.raises(DomainError) as exc:
        service.get_review(uuid4())
    assert exc.value.status == 404


def test_review_slot_requires_all_ids():
    """Модель ReviewSlot не создаётся без идентификатора сервера."""
    with pytest.raises(ValidationError):
        ReviewSlot(booking_id=uuid4(), user_id=uuid4())
