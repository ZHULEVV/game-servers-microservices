from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.errors import DomainError
from app.models.notification import Notification
from app.services.notification_service import TEMPLATES


def test_known_event_creates_notification_from_template(emit, user_id):
    """Известное событие превращается в уведомление по шаблону: заголовок, текст, бронь, не прочитано."""
    booking_id = uuid4()
    note = emit("booking.confirmed", user_id, booking_id)
    title, body = TEMPLATES["booking.confirmed"]
    assert note.user_id == user_id and note.type == "booking.confirmed" and note.booking_id == booking_id
    assert note.title == title and note.body == body and note.read is False


@pytest.mark.parametrize("key", sorted(TEMPLATES))
def test_every_system_event_has_a_template(emit, user_id, key):
    """Для каждого события системы, которое видит клиент, есть шаблон уведомления."""
    assert emit(key, user_id).title


def test_unknown_event_type_is_ignored(emit, user_id, repo):
    """Событие без шаблона не создаёт уведомления."""
    assert emit("catalog.price_changed", user_id) is None
    assert repo.list(None, None, None, 0, 10)[1] == 0


def test_event_without_addressee_is_ignored(service, repo):
    """Событие без user_id (некому слать) игнорируется."""
    assert service.handle_event("deploy.completed", {"event_id": str(uuid4())}) is None
    assert repo.list(None, None, None, 0, 10)[1] == 0


def test_duplicate_event_is_deduplicated_by_event_id(service, user_id):
    """Повторная доставка события с тем же event_id не создаёт второго уведомления."""
    event = {"event_id": str(uuid4()), "user_id": str(user_id)}
    assert service.handle_event("payment.succeeded", event) is not None
    assert service.handle_event("payment.succeeded", event) is None
    assert service.list_notifications(user_id=user_id)[1] == 1


def test_list_is_filtered_by_user_and_type(emit, service):
    """Список фильтруется по пользователю и типу события."""
    a, b = uuid4(), uuid4()
    emit("booking.created", a)
    emit("payment.succeeded", a)
    emit("booking.created", b)
    assert service.list_notifications(user_id=a)[1] == 2
    items, total = service.list_notifications(user_id=a, type="payment.succeeded")
    assert total == 1 and items[0].type == "payment.succeeded"


def test_list_is_newest_first_with_pagination(emit, service, user_id):
    """Порядок – новые первыми; offset/count вырезают страницу, total остаётся полным."""
    for key in ("booking.created", "payment.succeeded", "booking.confirmed"):
        emit(key, user_id)
    items, total = service.list_notifications(user_id=user_id, offset=0, count=2)
    assert total == 3 and [n.type for n in items] == ["booking.confirmed", "payment.succeeded"]


def test_mark_read_and_unread_filter(emit, service, user_id):
    """Пометка «прочитано» меняет признак; фильтр unread показывает только непрочитанные."""
    first = emit("booking.created", user_id)
    emit("payment.succeeded", user_id)
    assert service.mark_read(first.id).read is True
    items, total = service.list_notifications(user_id=user_id, unread=True)
    assert total == 1 and items[0].type == "payment.succeeded"


def test_mark_read_is_idempotent(emit, service, user_id):
    """Повторная пометка уведомления остаётся прочитанным и не вызывает ошибок."""
    note = emit("booking.created", user_id)
    service.mark_read(note.id)
    assert service.mark_read(note.id).read is True


def test_unknown_notification_is_404(service):
    """Неизвестное уведомление → 404."""
    with pytest.raises(DomainError) as exc:
        service.get_notification(uuid4())
    assert exc.value.status == 404


def test_notification_model_requires_fields():
    """Модель Notification не создаётся без обязательных полей."""
    with pytest.raises(ValidationError):
        Notification(id=uuid4(), type="booking.created")
