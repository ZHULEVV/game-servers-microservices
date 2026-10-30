from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.errors import InvalidAmount, InvalidStatus, NotFound
from app.events import make_event
from app.models.payment import Payment, PaymentStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PaymentService:
    def __init__(self, repo, gateway, publisher, clock=utcnow) -> None:
        self.repo = repo
        self.gateway = gateway
        self.publisher = publisher
        self.clock = clock

    # ---------- синхронные команды ----------
    def create_payment(self, booking_id: UUID, user_id: UUID, amount: Decimal,
                       card_token: str | None = None) -> Payment:
        """Выставить счёт: платёж создаётся в статусе pending, списание выполняется асинхронно."""
        if amount <= 0:
            raise InvalidAmount("Сумма платежа должна быть больше нуля")
        payment = Payment(id=uuid4(), booking_id=booking_id, user_id=user_id, amount=amount,
                          status=PaymentStatus.PENDING, card_token=card_token, created_at=self.clock())
        return self.repo.add(payment)

    def get_payment(self, payment_id: UUID) -> Payment:
        try:
            return self.repo.get_by_id(payment_id)
        except KeyError:
            raise NotFound(f"Платёж {payment_id} не найден") from None

    def list_payments(self, booking_id=None, user_id=None, status=None, offset=0, count=20):
        return self.repo.list(booking_id, user_id, status, offset, count)

    def refund_payment(self, payment_id: UUID, reason: str | None = None) -> Payment:
        payment = self.get_payment(payment_id)
        if payment.status != PaymentStatus.SUCCEEDED:
            raise InvalidStatus(f"Вернуть можно только оплаченный платёж, текущий статус — {payment.status.value}")
        self.gateway.refund(payment.amount)
        payment.status, payment.refund_reason = PaymentStatus.REFUNDED, reason or "refund_requested"
        self.repo.update(payment)
        self._publish_refunded(payment)
        return payment

    # ---------- списание через шлюз (выполняется в фоне после ответа клиенту) ----------
    def process_payment(self, payment_id: UUID) -> Payment:
        payment = self.get_payment(payment_id)
        if payment.status != PaymentStatus.PENDING:
            return payment
        result = self.gateway.charge(payment.amount, payment.card_token)
        if result.ok:
            payment.status = PaymentStatus.SUCCEEDED
            self.repo.update(payment)
            self.publisher.publish("payment.succeeded", make_event(
                booking_id=str(payment.booking_id), user_id=str(payment.user_id),
                payment_id=str(payment.id), amount=str(payment.amount)))
        else:
            payment.status, payment.fail_reason = PaymentStatus.FAILED, result.reason
            self.repo.update(payment)
            self.publisher.publish("payment.failed", make_event(
                booking_id=str(payment.booking_id), user_id=str(payment.user_id),
                payment_id=str(payment.id), amount=str(payment.amount), reason=result.reason))
        return payment

    # ---------- реакции на асинхронные сообщения ----------
    def _once(self, event: dict) -> bool:
        if self.repo.is_event_processed(event["event_id"]):
            return False
        self.repo.mark_event_processed(event["event_id"])
        return True

    def handle_booking_cancelled(self, event: dict) -> None:
        """booking.cancelled → вернуть деньги по оплаченным платежам брони."""
        if not self._once(event):
            return
        payments, _ = self.repo.list(UUID(event["booking_id"]), None, PaymentStatus.SUCCEEDED, 0, 1000)
        for payment in payments:
            self.gateway.refund(payment.amount)
            payment.status, payment.refund_reason = PaymentStatus.REFUNDED, event.get("reason", "booking_cancelled")
            self.repo.update(payment)
            self._publish_refunded(payment)

    def handle_booking_extended(self, event: dict) -> None:
        """booking.extended → выставить счёт на доплату."""
        if not self._once(event):
            return
        extra = Decimal(event["extra_amount"])
        if extra > 0:
            booking_id = UUID(event["booking_id"])
            previous, _ = self.repo.list(booking_id, None, None, 0, 1)
            token = previous[0].card_token if previous else None
            payment = self.create_payment(booking_id, UUID(event["user_id"]), extra, token)
            self.process_payment(payment.id)

    def _publish_refunded(self, payment: Payment) -> None:
        self.publisher.publish("payment.refunded", make_event(
            booking_id=str(payment.booking_id), user_id=str(payment.user_id),
            payment_id=str(payment.id), amount=str(payment.amount)))
