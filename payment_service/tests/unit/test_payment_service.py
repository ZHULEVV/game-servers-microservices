from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.errors import InvalidAmount, InvalidStatus, NotFound
from app.models.payment import Payment, PaymentStatus


def test_payment_model_requires_booking_id():
    """Модель платежа не создаётся без booking_id."""
    with pytest.raises(ValidationError):
        Payment(id=uuid4(), user_id=uuid4(), amount=Decimal("1"), status=PaymentStatus.PENDING,
                created_at="2026-11-01T12:00:00Z")


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-10")])
def test_create_payment_rejects_non_positive_amount(service, booking_id, user_id, amount):
    """Сумма 0 или отрицательная – ошибка invalid_amount (два параметра)."""
    with pytest.raises(InvalidAmount):
        service.create_payment(booking_id, user_id, amount)


def test_new_payment_is_pending_and_nothing_published(service, publisher, booking_id, user_id):
    """Новый платёж имеет статус pending, событий не публикуется."""
    payment = service.create_payment(booking_id, user_id, Decimal("450"))
    assert payment.status == PaymentStatus.PENDING
    assert publisher.sent == []


def test_process_payment_success_publishes_payment_succeeded(service, publisher, booking_id, user_id):
    """Успешное списание: succeeded и событие payment.succeeded с event_id."""
    payment = service.create_payment(booking_id, user_id, Decimal("450"), "tok_ok")
    result = service.process_payment(payment.id)
    assert result.status == PaymentStatus.SUCCEEDED
    key, event = publisher.sent[-1]
    assert key == "payment.succeeded" and event["booking_id"] == str(booking_id) and "event_id" in event


def test_process_payment_declined_card_publishes_payment_failed(service, publisher, booking_id, user_id):
    """Карта tok_fail: failed (card_declined), событие payment.failed."""
    payment = service.create_payment(booking_id, user_id, Decimal("450"), "tok_fail")
    result = service.process_payment(payment.id)
    assert result.status == PaymentStatus.FAILED and result.fail_reason == "card_declined"
    assert publisher.sent[-1][0] == "payment.failed"


def test_process_payment_over_limit_fails(service, booking_id, user_id):
    """Сумма выше лимита шлюза: failed (limit_exceeded)."""
    payment = service.create_payment(booking_id, user_id, Decimal("100001"))
    assert service.process_payment(payment.id).fail_reason == "limit_exceeded"


def test_process_payment_is_idempotent(service, publisher, paid):
    """Повторная обработка не отправляет событие повторно."""
    sent = len(publisher.sent)
    service.process_payment(paid.id)  # повторная обработка не шлёт событие
    assert len(publisher.sent) == sent


def test_refund_unpaid_payment_forbidden(service, booking_id, user_id):
    """Возврат неоплаченного платежа – ошибка invalid_status."""
    payment = service.create_payment(booking_id, user_id, Decimal("450"))
    with pytest.raises(InvalidStatus):
        service.refund_payment(payment.id)


def test_refund_paid_payment(service, publisher, paid):
    """Возврат оплаченного: refunded, причина сохранена, отправлено payment.refunded."""
    refunded = service.refund_payment(paid.id, "по просьбе клиента")
    assert refunded.status == PaymentStatus.REFUNDED and refunded.refund_reason == "по просьбе клиента"
    assert publisher.sent[-1][0] == "payment.refunded"


def test_refund_twice_forbidden(service, paid):
    """Повторный возврат – ошибка invalid_status."""
    service.refund_payment(paid.id)
    with pytest.raises(InvalidStatus):
        service.refund_payment(paid.id)


def test_get_unknown_payment(service):
    """Несуществующий платёж – ошибка not_found."""
    with pytest.raises(NotFound):
        service.get_payment(uuid4())


def test_booking_cancelled_refunds_paid_payments(service, publisher, paid, booking_id):
    """booking.cancelled возвращает оплаченные платежи брони."""
    service.handle_booking_cancelled({"event_id": str(uuid4()), "booking_id": str(booking_id), "reason": "x"})
    assert service.get_payment(paid.id).status == PaymentStatus.REFUNDED
    assert publisher.sent[-1][0] == "payment.refunded"


def test_duplicate_booking_cancelled_event_ignored(service, publisher, paid, booking_id):
    """Повторное booking.cancelled не даёт повторных возвратов."""
    event = {"event_id": str(uuid4()), "booking_id": str(booking_id)}
    service.handle_booking_cancelled(event)
    sent = len(publisher.sent)
    service.handle_booking_cancelled(event)
    assert len(publisher.sent) == sent


def test_booking_extended_creates_surcharge(service, publisher, paid, booking_id, user_id):
    """booking.extended создаёт и проводит платёж на доплату 300.00."""
    service.handle_booking_extended({"event_id": str(uuid4()), "booking_id": str(booking_id),
                                     "user_id": str(user_id), "extra_amount": "300.00"})
    payments, total = service.list_payments(booking_id=booking_id)
    assert total == 2 and payments[1].amount == Decimal("300.00") and payments[1].status == PaymentStatus.SUCCEEDED
