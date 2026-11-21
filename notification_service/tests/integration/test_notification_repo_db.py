from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models.notification import Notification
from app.repositories.db_notification_repo import DbNotificationRepo
from app.services.notification_service import NotificationService

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo(db) -> DbNotificationRepo:
    return DbNotificationRepo(db)


def make(user, kind="booking.created", minutes=0, read=False) -> Notification:
    return Notification(id=uuid4(), user_id=user, type=kind, title="t", body="b", booking_id=uuid4(), read=read,
                        created_at=T0 + timedelta(minutes=minutes))


def test_notification_roundtrip_and_mark_read(repo):
    """Уведомление записывается в PostgreSQL; update() меняет признак прочтения, остальные поля сохраняются."""
    note = make(uuid4())
    repo.add(note)
    note.read = True
    repo.update(note)
    saved = repo.get_by_id(note.id)
    assert saved.read is True and saved.type == "booking.created" and saved.booking_id == note.booking_id


def test_list_filters_by_user_type_and_unread(repo):
    """Фильтры списка работают в SQL: по пользователю, типу события и признаку «непрочитано»."""
    a, b = uuid4(), uuid4()
    repo.add(make(a, "booking.created", 0))
    repo.add(make(a, "payment.succeeded", 1, read=True))
    repo.add(make(b, "booking.created", 2))
    assert repo.list(a, None, None, 0, 10)[1] == 2
    assert repo.list(a, "payment.succeeded", None, 0, 10)[1] == 1
    assert [n.type for n in repo.list(a, None, True, 0, 10)[0]] == ["booking.created"]        # unread=True
    assert repo.list(None, None, False, 0, 10)[1] == 1                                        # unread=False – прочитанные


def test_list_is_newest_first_with_pagination(repo):
    """Порядок «новые первыми»; offset/count вырезают страницу, total – полное число уведомлений пользователя."""
    user = uuid4()
    for i in range(5):
        repo.add(make(user, minutes=i))
    items, total = repo.list(user, None, None, offset=1, count=2)
    assert total == 5 and [n.created_at for n in items] == [T0 + timedelta(minutes=3), T0 + timedelta(minutes=2)]


def test_event_becomes_notification_once_on_real_database(repo):
    """Сервис поверх PostgreSQL: событие создаёт одно уведомление, повторная доставка с тем же event_id игнорируется."""
    service = NotificationService(repo)
    user = uuid4()
    event = {"event_id": str(uuid4()), "user_id": str(user), "booking_id": str(uuid4())}
    assert service.handle_event("payment.succeeded", event) is not None
    assert service.handle_event("payment.succeeded", event) is None
    assert repo.list(user, None, None, 0, 10)[1] == 1


def test_processed_events_survive_in_database(repo):
    """Таблица processed_events: пометка сохраняется в БД и повторная пометка не приводит к ошибке."""
    repo.mark_event_processed("evt-9")
    repo.mark_event_processed("evt-9")
    assert repo.is_event_processed("evt-9") and not repo.is_event_processed("evt-10")
