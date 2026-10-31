from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.errors import not_found
from app.models.notification import Notification

TEMPLATES = {  # routing key -> (заголовок, текст)
    "user.registered": ("Добро пожаловать!", "Аккаунт создан. Можно выбирать сервер и бронировать."),
    "booking.created": ("Бронь создана", "Бронь ждёт оплаты."),
    "booking.confirmed": ("Бронь подтверждена", "Оплата получена, сервер разворачивается."),
    "booking.cancelled": ("Бронь отменена", "Бронь отменена, оплаченные суммы будут возвращены."),
    "booking.extended": ("Аренда продлена", "Выставлен счёт на доплату."),
    "booking.finished": ("Аренда завершена", "Спасибо! Оставьте отзыв о сервере."),
    "payment.succeeded": ("Оплата прошла", "Квитанция отправлена на почту."),
    "payment.failed": ("Ошибка оплаты", "Платёж отклонён, бронь отменена."),
    "payment.refunded": ("Возврат средств", "Деньги возвращены на карту."),
    "deploy.completed": ("Сервер готов", "Данные для подключения доступны в личном кабинете."),
    "deploy.failed": ("Не удалось развернуть сервер", "Бронь будет отменена."),
    "monitoring.load_exceeded": ("Высокая нагрузка", "Нагрузка на сервер превысила порог."),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotificationService:
    def __init__(self, repo, clock=utcnow) -> None:
        self.repo = repo
        self.clock = clock

    def handle_event(self, routing_key: str, event: dict) -> Notification | None:
        """Любое событие системы → уведомление по шаблону. Дубликаты (по event_id) и события без адресата игнорируются."""
        if self.repo.is_event_processed(event["event_id"]):
            return None
        self.repo.mark_event_processed(event["event_id"])
        template = TEMPLATES.get(routing_key)
        if template is None or not event.get("user_id"):
            return None
        title, body = template
        note = Notification(id=uuid4(), user_id=UUID(event["user_id"]), type=routing_key, title=title, body=body,
                            booking_id=UUID(event["booking_id"]) if event.get("booking_id") else None, created_at=self.clock())
        return self.repo.add(note)

    def list_notifications(self, user_id=None, type=None, unread=None, offset=0, count=20):
        return self.repo.list(user_id, type, unread, offset, count)

    def get_notification(self, note_id: UUID) -> Notification:
        try:
            return self.repo.get_by_id(note_id)
        except KeyError:
            raise not_found(f"Уведомление {note_id}") from None

    def mark_read(self, note_id: UUID) -> Notification:
        note = self.get_notification(note_id)
        note.read = True
        return self.repo.update(note)
