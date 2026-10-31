from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.errors import DomainError, not_found
from app.events import make_event
from app.models.monitor import Alert, Monitor, Thresholds


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MonitorService:
    def __init__(self, repo, booking_client, publisher, clock=utcnow) -> None:
        self.repo = repo
        self.booking = booking_client
        self.publisher = publisher
        self.clock = clock

    def get_monitor(self, booking_id: UUID) -> Monitor:
        try:
            return self.repo.get(booking_id)
        except KeyError:
            raise not_found(f"Мониторинг брони {booking_id}") from None

    def alerts(self, booking_id: UUID, offset=0, count=20):
        self.get_monitor(booking_id)
        return self.repo.alerts(booking_id, offset, count)

    def set_thresholds(self, booking_id: UUID, cpu: int, ram: int) -> Monitor:
        if not (1 <= cpu <= 100 and 1 <= ram <= 100):
            raise DomainError(400, "invalid_threshold", "Пороги должны быть в диапазоне 1–100 %")
        monitor = self.get_monitor(booking_id)
        booking = self.booking.get_booking(booking_id)  # синхронный вызов Booking Service
        if booking["status"] in ("finished", "cancelled"):
            raise DomainError(409, "booking_closed", f"Бронь в статусе {booking['status']}: пороги менять нельзя")
        monitor.thresholds = Thresholds(cpu=cpu, ram=ram)
        return self.repo.update(monitor)

    def add_sample(self, booking_id: UUID, cpu: float, ram: float) -> list[Alert]:
        """Метрики от агента на игровом сервере; превышение порога → оповещение и событие monitoring.load_exceeded."""
        monitor = self.get_monitor(booking_id)
        if monitor.status != "active":
            raise DomainError(409, "monitor_stopped", "Мониторинг остановлен")
        monitor.cpu, monitor.ram = cpu, ram
        created = []
        for metric, value, limit in (("cpu", cpu, monitor.thresholds.cpu), ("ram", ram, monitor.thresholds.ram)):
            if value > limit:
                alert = Alert(id=uuid4(), metric=metric, value=value, threshold=limit, occurred_at=self.clock())
                self.repo.add_alert(booking_id, alert)
                created.append(alert)
                self.publisher.publish("monitoring.load_exceeded", make_event(
                    booking_id=str(booking_id), user_id=str(monitor.user_id), metric=metric, value=value, threshold=limit))
        self.repo.update(monitor)
        return created

    # ---------- реакции на сообщения ----------
    def _once(self, event: dict) -> bool:
        if self.repo.is_event_processed(event["event_id"]):
            return False
        self.repo.mark_event_processed(event["event_id"])
        return True

    def handle_deploy_completed(self, event: dict) -> None:
        if self._once(event):
            self.repo.add(Monitor(booking_id=UUID(event["booking_id"]), user_id=UUID(event["user_id"]), started_at=self.clock()))

    def handle_booking_finished(self, event: dict) -> None:
        if self._once(event):
            try:
                monitor = self.repo.get(UUID(event["booking_id"]))
            except KeyError:
                return
            monitor.status = "stopped"
            self.repo.update(monitor)
