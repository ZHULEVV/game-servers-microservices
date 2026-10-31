from uuid import UUID

from app.models.monitor import Alert, Monitor


class LocalMonitorRepo:
    """Хранилище мониторов в памяти процесса (за интерфейсом репозитория его можно заменить на БД)."""

    def __init__(self) -> None:
        self._monitors: dict[UUID, Monitor] = {}
        self._alerts: dict[UUID, list[Alert]] = {}
        self._events: set[str] = set()

    def add(self, monitor: Monitor) -> Monitor:
        self._monitors[monitor.booking_id] = monitor
        self._alerts.setdefault(monitor.booking_id, [])
        return monitor

    def get(self, booking_id: UUID) -> Monitor:
        try:
            return self._monitors[booking_id]
        except KeyError:
            raise KeyError(f"Monitor {booking_id} not found") from None

    def update(self, monitor: Monitor) -> Monitor:
        self._monitors[monitor.booking_id] = monitor
        return monitor

    def add_alert(self, booking_id: UUID, alert: Alert) -> None:
        self._alerts[booking_id].append(alert)

    def alerts(self, booking_id: UUID, offset: int, count: int):
        rows = list(reversed(self._alerts.get(booking_id, [])))
        return rows[offset:offset + count], len(rows)

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self._events

    def mark_event_processed(self, event_id: str) -> None:
        self._events.add(event_id)
