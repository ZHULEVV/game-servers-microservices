from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.booking import Booking, BookingStatus


def make(**over):
    data = dict(id=uuid4(), user_id=uuid4(), server_id=uuid4(), start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc), status=BookingStatus.CREATED, amount=Decimal("100"),
                created_at=datetime.now(timezone.utc))
    data.update(over)
    return Booking(**data)


def test_booking_creation_defaults():
    """Новая модель брони создаётся в статусе created без причины отмены."""
    booking = make()
    assert booking.status == BookingStatus.CREATED
    assert booking.cancel_reason is None


def test_booking_server_id_required():
    """Модель брони не создаётся без обязательного поля server_id."""
    with pytest.raises(ValidationError):
        Booking(id=uuid4(), user_id=uuid4(), start=datetime.now(), end=datetime.now(),
                status=BookingStatus.CREATED, amount=Decimal("1"), created_at=datetime.now())


def test_booking_rejects_unknown_status():
    """Недопустимое значение статуса отвергается валидацией."""
    with pytest.raises(ValidationError):
        make(status="teleported")
