from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.schemas.payment import PaymentDB, ProcessedEventDB


class DbPaymentRepo:
    """Реализация поверх PostgreSQL. Интерфейс тот же, что у LocalPaymentRepo."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, payment: Payment) -> Payment:
        self.db.add(PaymentDB(**payment.model_dump()))
        self.db.commit()
        return payment

    def get_by_id(self, payment_id: UUID) -> Payment:
        row = self.db.get(PaymentDB, payment_id)
        if row is None:
            raise KeyError(f"Payment {payment_id} not found")
        return Payment.model_validate(row)

    def update(self, payment: Payment) -> Payment:
        row = self.db.get(PaymentDB, payment.id)
        if row is None:
            raise KeyError(f"Payment {payment.id} not found")
        for field, value in payment.model_dump().items():
            setattr(row, field, value)
        self.db.commit()
        return payment

    def list(self, booking_id, user_id, status, offset, count):
        q = self.db.query(PaymentDB)
        if booking_id:
            q = q.filter(PaymentDB.booking_id == booking_id)
        if user_id:
            q = q.filter(PaymentDB.user_id == user_id)
        if status:
            q = q.filter(PaymentDB.status == status)
        total = q.count()
        rows = q.order_by(PaymentDB.created_at).offset(offset).limit(count).all()
        return [Payment.model_validate(r) for r in rows], total

    def is_event_processed(self, event_id: str) -> bool:
        return self.db.get(ProcessedEventDB, event_id) is not None

    def mark_event_processed(self, event_id: str) -> None:
        try:
            self.db.add(ProcessedEventDB(event_id=event_id))
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
