from app.clients.booking_client import BookingClient
from app.events import RabbitPublisher
from app.repositories.local_monitor_repo import LocalMonitorRepo
from app.services.monitor_service import MonitorService

_repo = LocalMonitorRepo()  # одно хранилище на процесс: его делят HTTP-запросы и потребитель сообщений


def get_service() -> MonitorService:
    return MonitorService(_repo, BookingClient(), RabbitPublisher("monitoring.events"))
