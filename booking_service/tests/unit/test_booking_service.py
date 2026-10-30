from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.errors import (DependencyUnavailable, InvalidDates, InvalidStatus, NotFound, ServerUnavailable, SlotBusy)
from app.models.booking import BookingStatus
from app.services.booking_service import billable_hours
from tests.conftest import NOW, SERVER_ID


def create(service, user_id, period, **kw):
    return service.create_booking(user_id, kw.pop("server_id", SERVER_ID), *period, **kw)


def event(booking, **extra):
    return {"event_id": str(uuid4()), "booking_id": str(booking.id), **extra}


# ---------- создание брони ----------
def test_create_booking_calculates_amount_and_waits_payment(service, user_id, period, payment, publisher):
    booking = create(service, user_id, period, card_token="tok_ok")
    assert booking.amount == Decimal("450.00")           # 3 ч × 150
    assert booking.status == BookingStatus.AWAITING_PAYMENT
    assert payment.calls[0]["amount"] == Decimal("450.00") and payment.calls[0]["card_token"] == "tok_ok"
    assert [k for k, _ in publisher.sent] == ["booking.created"]


def test_create_booking_end_before_start(service, user_id):
    with pytest.raises(InvalidDates):
        service.create_booking(user_id, SERVER_ID, NOW + timedelta(hours=3), NOW + timedelta(hours=2))


def test_create_booking_shorter_than_minimum(service, user_id):
    with pytest.raises(InvalidDates):
        service.create_booking(user_id, SERVER_ID, NOW + timedelta(hours=1), NOW + timedelta(hours=1, minutes=30))


def test_create_booking_in_the_past(service, user_id):
    with pytest.raises(InvalidDates):
        service.create_booking(user_id, SERVER_ID, NOW - timedelta(hours=3), NOW - timedelta(hours=1))


def test_create_booking_overlapping_slot(service, user_id, period):
    create(service, user_id, period)
    other = (period[0] + timedelta(hours=1), period[1] + timedelta(hours=1))
    with pytest.raises(SlotBusy):
        create(service, uuid4(), other)


def test_adjacent_slots_do_not_overlap(service, user_id, period):
    create(service, user_id, period)
    create(service, uuid4(), (period[1], period[1] + timedelta(hours=2)))  # встык — разрешено


def test_create_booking_server_unavailable(service, catalog, user_id, period):
    catalog.available = False
    with pytest.raises(ServerUnavailable):
        create(service, user_id, period)


def test_create_booking_payment_down_cancels_booking(service, payment, repo, user_id, period, publisher):
    payment.down = True
    with pytest.raises(DependencyUnavailable):
        create(service, user_id, period)
    saved, _ = repo.list(None, None, None, None, 0, 10)
    assert saved[0].status == BookingStatus.CANCELLED and saved[0].cancel_reason == "payment_unavailable"
    assert publisher.sent == []                           # событие booking.created не отправлено


def test_billable_hours_rounds_up():
    assert billable_hours(NOW, NOW + timedelta(hours=2, minutes=1)) == 3


# ---------- отмена и продление ----------
def test_cancel_confirmed_booking_publishes_event(service, user_id, period, publisher):
    booking = create(service, user_id, period)
    service.handle_payment_succeeded(event(booking))
    cancelled = service.cancel_booking(booking.id, "не нужен")
    assert cancelled.status == BookingStatus.CANCELLED and cancelled.cancel_reason == "не нужен"
    assert publisher.sent[-1][0] == "booking.cancelled"


def test_cancel_finished_booking_forbidden(service, repo, user_id, period):
    booking = create(service, user_id, period)
    booking.status = BookingStatus.FINISHED
    repo.update(booking)
    with pytest.raises(InvalidStatus):
        service.cancel_booking(booking.id)


def test_cancel_unknown_booking(service):
    with pytest.raises(NotFound):
        service.cancel_booking(uuid4())


def test_extend_in_wrong_status_forbidden(service, user_id, period):
    booking = create(service, user_id, period)            # awaiting_payment
    with pytest.raises(InvalidStatus):
        service.extend_booking(booking.id, period[1] + timedelta(hours=1))


def test_extend_recalculates_amount_and_publishes(service, user_id, period, publisher):
    booking = create(service, user_id, period)
    service.handle_payment_succeeded(event(booking))
    extended = service.extend_booking(booking.id, period[1] + timedelta(hours=2))
    assert extended.amount == Decimal("750.00")           # 450 + 2 ч × 150
    assert publisher.sent[-1][0] == "booking.extended"
    assert publisher.sent[-1][1]["extra_amount"] == "300.00"


def test_extend_into_busy_slot(service, user_id, period):
    booking = create(service, user_id, period)
    service.handle_payment_succeeded(event(booking))
    create(service, uuid4(), (period[1], period[1] + timedelta(hours=2)))
    with pytest.raises(SlotBusy):
        service.extend_booking(booking.id, period[1] + timedelta(hours=1))


# ---------- реакции на сообщения ----------
def test_payment_succeeded_confirms_booking(service, user_id, period, publisher):
    booking = create(service, user_id, period)
    service.handle_payment_succeeded(event(booking))
    assert service.get_booking(booking.id).status == BookingStatus.CONFIRMED
    assert publisher.sent[-1][0] == "booking.confirmed"


def test_payment_failed_cancels_booking(service, user_id, period, publisher):
    booking = create(service, user_id, period)
    service.handle_payment_failed(event(booking))
    stored = service.get_booking(booking.id)
    assert stored.status == BookingStatus.CANCELLED and stored.cancel_reason == "payment_failed"
    assert publisher.sent[-1][0] == "booking.cancelled"


def test_duplicate_event_is_ignored(service, user_id, period, publisher):
    booking = create(service, user_id, period)
    ev = event(booking)
    service.handle_payment_succeeded(ev)
    sent = len(publisher.sent)
    service.handle_payment_succeeded(ev)                  # тот же event_id
    assert len(publisher.sent) == sent


def test_deploy_completed_activates_booking(service, user_id, period):
    booking = create(service, user_id, period)
    service.handle_payment_succeeded(event(booking))
    service.handle_deploy_completed(event(booking))
    assert service.get_booking(booking.id).status == BookingStatus.ACTIVE


def test_finish_expired_finishes_only_past_rent(service, repo, user_id, period, publisher):
    booking = create(service, user_id, period)
    service.handle_payment_succeeded(event(booking))
    assert service.finish_expired() == 0                  # аренда ещё не закончилась
    service.clock = lambda: period[1] + timedelta(minutes=1)
    assert service.finish_expired() == 1
    assert service.get_booking(booking.id).status == BookingStatus.FINISHED
    assert publisher.sent[-1][0] == "booking.finished"
