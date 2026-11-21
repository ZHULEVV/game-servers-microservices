from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.payment import Payment, PaymentStatus
from app.repositories.db_payment_repo import DbPaymentRepo

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo(db) -> DbPaymentRepo:
    return DbPaymentRepo(db)


def make(booking=None, status=PaymentStatus.PENDING, amount="450.00") -> Payment:
    return Payment(id=uuid4(), booking_id=booking or uuid4(), user_id=uuid4(), amount=Decimal(amount), status=status,
                   card_token="tok_visa", created_at=T0)


def test_payment_roundtrip_and_status_transitions_persist(repo):
    """Платёж записывается в PostgreSQL; смена статуса и причины возврата сохраняется (pending → succeeded → refunded)."""
    payment = make()
    repo.add(payment)
    assert repo.get_by_id(payment.id).status == PaymentStatus.PENDING
    payment.status = PaymentStatus.SUCCEEDED
    repo.update(payment)
    payment.status, payment.refund_reason = PaymentStatus.REFUNDED, "по просьбе клиента"
    repo.update(payment)
    saved = repo.get_by_id(payment.id)
    assert saved.status == PaymentStatus.REFUNDED and saved.refund_reason == "по просьбе клиента"
    assert saved.amount == Decimal("450.00") and saved.card_token == "tok_visa"


def test_processed_events_table_gives_idempotency(repo):
    """Таблица processed_events: событие помечается обработанным, повторная пометка не падает, чужие event_id не затрагиваются."""
    assert repo.is_event_processed("evt-1") is False
    repo.mark_event_processed("evt-1")
    repo.mark_event_processed("evt-1")
    assert repo.is_event_processed("evt-1") is True and repo.is_event_processed("evt-2") is False
