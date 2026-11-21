from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.booking import Booking, BookingStatus
from app.repositories.db_booking_repo import DbBookingRepo

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)
SERVER = uuid4()


@pytest.fixture()
def repo(db) -> DbBookingRepo:
    return DbBookingRepo(db)


def make(start_h=0, hours=3, server=SERVER, status=BookingStatus.CONFIRMED, user=None, amount="450.00") -> Booking:
    return Booking(id=uuid4(), user_id=user or uuid4(), server_id=server, start=T0 + timedelta(hours=start_h),
                   end=T0 + timedelta(hours=start_h + hours), status=status, amount=Decimal(amount), created_at=T0)


def test_booking_roundtrip_keeps_money_and_timezone(repo):
    """Бронь записывается в PostgreSQL и читается обратно: сумма (Numeric) и время с часовым поясом не искажаются."""
    booking = make(amount="1234.56")
    repo.add(booking)
    saved = repo.get_by_id(booking.id)
    assert saved.amount == Decimal("1234.56") and saved.status == BookingStatus.CONFIRMED
    assert saved.start == booking.start and saved.start.utcoffset() == timedelta(0)


def test_find_overlapping_uses_sql_conditions(repo):
    """Поиск пересечений в SQL: пересекающаяся бронь найдена, бронь встык, чужой сервер и отменённая бронь – нет."""
    busy = make(0, 3)
    repo.add(busy)
    repo.add(make(0, 3, status=BookingStatus.CANCELLED))          # отменённая слот не занимает
    repo.add(make(0, 3, server=uuid4()))                           # другой сервер
    found = repo.find_overlapping(SERVER, T0 + timedelta(hours=2), T0 + timedelta(hours=5))
    assert [b.id for b in found] == [busy.id]
    assert repo.find_overlapping(SERVER, T0 + timedelta(hours=3), T0 + timedelta(hours=6)) == []   # встык


def test_list_filters_pagination_and_total(repo):
    """list(): фильтры по пользователю и статусу, сортировка по created_at, offset/count и общий total."""
    user = uuid4()
    for i in range(5):
        repo.add(make(i * 4, 2, user=user, status=BookingStatus.CONFIRMED if i < 4 else BookingStatus.CANCELLED))
    repo.add(make(40, 2))                                          # чужая бронь
    items, total = repo.list(user, BookingStatus.CONFIRMED, None, None, offset=1, count=2)
    assert total == 4 and len(items) == 2 and all(b.user_id == user for b in items)
    assert repo.list(user, None, T0 + timedelta(hours=8), None, 0, 10)[1] == 3     # фильтр по дате начала
