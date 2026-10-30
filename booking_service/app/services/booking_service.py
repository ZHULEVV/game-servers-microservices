import math
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable
from uuid import UUID, uuid4

from app.errors import (DependencyUnavailable, InvalidDates, InvalidStatus, NotFound, ServerUnavailable,
                        SlotBusy)
from app.events import make_event
from app.models.booking import Booking, BookingStatus
from app.settings import settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def billable_hours(start: datetime, end: datetime) -> int:
    """Аренда тарифицируется по полным часам (округление вверх)."""
    return math.ceil((end - start).total_seconds() / 3600)


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class BookingService:
    def __init__(self, repo, payment_client, catalog_client, publisher,
                 clock: Callable[[], datetime] = utcnow, min_hours: int | None = None) -> None:
        self.repo = repo
        self.payment = payment_client
        self.catalog = catalog_client
        self.publisher = publisher
        self.clock = clock
        self.min_hours = settings.min_hours if min_hours is None else min_hours

    # ---------- синхронные команды ----------
    def validate_period(self, start: datetime, end: datetime) -> tuple[datetime, datetime]:
        start, end = as_utc(start), as_utc(end)
        if end <= start:
            raise InvalidDates("Дата окончания должна быть позже даты начала")
        if end - start < timedelta(hours=self.min_hours):
            raise InvalidDates(f"Минимальная длительность аренды — {self.min_hours} ч")
        if start < self.clock() - timedelta(minutes=1):
            raise InvalidDates("Дата начала аренды не может быть в прошлом")
        return start, end

    def create_booking(self, user_id: UUID, server_id: UUID, start: datetime, end: datetime,
                       card_token: str | None = None) -> Booking:
        start, end = self.validate_period(start, end)
        available, price_per_hour = self.catalog.get_availability(server_id, start, end)
        if not available:
            raise ServerUnavailable("Сервер недоступен в выбранный период")
        if self.repo.find_overlapping(server_id, start, end):
            raise SlotBusy("Сервер уже забронирован на это время")

        booking = Booking(id=uuid4(), user_id=user_id, server_id=server_id, start=start, end=end,
                          status=BookingStatus.CREATED, amount=money(price_per_hour * billable_hours(start, end)),
                          created_at=self.clock())
        self.repo.add(booking)
        try:
            self.payment.create_invoice(booking.id, user_id, booking.amount, card_token)
        except DependencyUnavailable:
            booking.status, booking.cancel_reason = BookingStatus.CANCELLED, "payment_unavailable"
            self.repo.update(booking)
            raise
        booking = self.repo.get_by_id(booking.id)  # шлюз мог успеть ответить, пока шёл вызов
        if booking.status == BookingStatus.CREATED:
            booking.status = BookingStatus.AWAITING_PAYMENT
            self.repo.update(booking)
        self.publisher.publish("booking.created", make_event(
            booking_id=str(booking.id), user_id=str(user_id), server_id=str(server_id),
            start=booking.start.isoformat(), end=booking.end.isoformat(), amount=str(booking.amount)))
        return booking

    def get_booking(self, booking_id: UUID) -> Booking:
        try:
            return self.repo.get_by_id(booking_id)
        except KeyError:
            raise NotFound(f"Бронь {booking_id} не найдена") from None

    def list_bookings(self, user_id=None, status=None, start_from=None, start_to=None, offset=0, count=20):
        return self.repo.list(user_id, status, start_from, start_to, offset, count)

    def cancel_booking(self, booking_id: UUID, reason: str | None = None) -> Booking:
        booking = self.get_booking(booking_id)
        if booking.status in (BookingStatus.CANCELLED, BookingStatus.FINISHED):
            raise InvalidStatus(f"Бронь в статусе {booking.status.value} не может быть отменена")
        return self._cancel(booking, reason or "cancelled_by_user")

    def extend_booking(self, booking_id: UUID, new_end: datetime) -> Booking:
        booking = self.get_booking(booking_id)
        if booking.status not in (BookingStatus.CONFIRMED, BookingStatus.ACTIVE):
            raise InvalidStatus("Продлить можно только подтверждённую или активную бронь")
        new_end = as_utc(new_end)
        if new_end <= booking.end:
            raise InvalidDates("Новая дата окончания должна быть позже текущей")
        if self.repo.find_overlapping(booking.server_id, booking.end, new_end, exclude_id=booking.id):
            raise SlotBusy("Сервер занят в период продления")
        rate = booking.amount / billable_hours(booking.start, booking.end)
        extra = money(rate * billable_hours(booking.end, new_end))
        booking.end, booking.amount = new_end, booking.amount + extra
        self.repo.update(booking)
        self.publisher.publish("booking.extended", make_event(
            booking_id=str(booking.id), user_id=str(booking.user_id), new_end=new_end.isoformat(),
            extra_amount=str(extra)))
        return booking

    # ---------- реакции на асинхронные сообщения ----------
    def _once(self, event: dict) -> bool:
        """Дедупликация по event_id: True — событие новое."""
        if self.repo.is_event_processed(event["event_id"]):
            return False
        self.repo.mark_event_processed(event["event_id"])
        return True

    def handle_payment_succeeded(self, event: dict) -> None:
        if not self._once(event):
            return
        booking = self.get_booking(UUID(event["booking_id"]))
        # доплата за продление приходит для уже подтверждённой брони и статус не меняет
        if booking.status in (BookingStatus.CREATED, BookingStatus.AWAITING_PAYMENT):
            booking.status = BookingStatus.CONFIRMED
            self.repo.update(booking)
            self.publisher.publish("booking.confirmed", make_event(
                booking_id=str(booking.id), user_id=str(booking.user_id), server_id=str(booking.server_id),
                start=booking.start.isoformat(), end=booking.end.isoformat()))

    def handle_payment_failed(self, event: dict) -> None:
        if not self._once(event):
            return
        booking = self.get_booking(UUID(event["booking_id"]))
        if booking.status in (BookingStatus.CREATED, BookingStatus.AWAITING_PAYMENT):
            self._cancel(booking, "payment_failed")

    def handle_deploy_completed(self, event: dict) -> None:
        if not self._once(event):
            return
        booking = self.get_booking(UUID(event["booking_id"]))
        if booking.status == BookingStatus.CONFIRMED:
            booking.status = BookingStatus.ACTIVE
            self.repo.update(booking)

    def handle_deploy_failed(self, event: dict) -> None:
        if not self._once(event):
            return
        booking = self.get_booking(UUID(event["booking_id"]))
        if booking.status == BookingStatus.CONFIRMED:
            self._cancel(booking, "deploy_failed")

    # ---------- команда системы: «Аренда истекла / завершена» ----------
    def finish_expired(self) -> int:
        expired = self.repo.find_expired(self.clock())
        for booking in expired:
            booking.status = BookingStatus.FINISHED
            self.repo.update(booking)
            self.publisher.publish("booking.finished", make_event(
                booking_id=str(booking.id), user_id=str(booking.user_id), server_id=str(booking.server_id)))
        return len(expired)

    def _cancel(self, booking: Booking, reason: str) -> Booking:
        booking.status, booking.cancel_reason = BookingStatus.CANCELLED, reason
        self.repo.update(booking)
        self.publisher.publish("booking.cancelled", make_event(
            booking_id=str(booking.id), user_id=str(booking.user_id), server_id=str(booking.server_id),
            reason=reason))
        return booking
