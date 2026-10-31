import random
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.errors import DomainError, not_found
from app.events import make_event
from app.models.deployment import Deployment, DeploymentStatus, Operation


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeploymentService:
    def __init__(self, repo, booking_client, publisher, clock=utcnow) -> None:
        self.repo = repo
        self.booking = booking_client
        self.publisher = publisher
        self.clock = clock

    # ---------- синхронные команды ----------
    def start_for_booking(self, booking_id: UUID) -> tuple[Deployment, Operation]:
        """POST /deployments: параметры брони запрашиваются у Booking Service, затем создаётся долгая операция."""
        booking = self.booking.get_booking(booking_id)
        if booking["status"] != "confirmed":
            raise DomainError(409, "booking_not_confirmed",
                              f"Бронь в статусе {booking['status']}: развёртывание возможно только для confirmed")
        return self._create(booking_id, UUID(booking["user_id"]))

    def _create(self, booking_id: UUID, user_id: UUID) -> tuple[Deployment, Operation]:
        if self.repo.active_for_booking(booking_id) is not None:
            raise DomainError(409, "already_started", "Для этой брони развёртывание уже запущено")
        dep = Deployment(id=uuid4(), booking_id=booking_id, user_id=user_id, status=DeploymentStatus.PROVISIONING, started_at=self.clock())
        op = Operation(id=uuid4(), deployment_id=dep.id)
        self.repo.add(dep, op)
        return dep, op

    def complete(self, deployment_id: UUID) -> Deployment:
        """Сервер развёрнут: выдаём адрес и порт, закрываем операцию и публикуем deploy.completed."""
        dep = self.repo.get_deployment(deployment_id)
        if dep.status != DeploymentStatus.PROVISIONING:  # аренду успели отменить во время развёртывания
            return dep
        dep.status, dep.finished_at = DeploymentStatus.RUNNING, self.clock()
        dep.ip, dep.port = f"10.0.0.{random.randint(10, 250)}", random.choice([25565, 27015, 7777])
        op = self.repo.operation_of(dep.id)
        op.is_finished, op.result = True, {"deployment_id": str(dep.id), "status": dep.status.value, "ip": dep.ip, "port": dep.port}
        self.publisher.publish("deploy.completed", make_event(booking_id=str(dep.booking_id), user_id=str(dep.user_id), ip=dep.ip, port=dep.port))
        return dep

    def get_operation(self, operation_id: UUID) -> Operation:
        try:
            return self.repo.get_operation(operation_id)
        except KeyError:
            raise not_found(f"Операция {operation_id}") from None

    def get_deployment(self, deployment_id: UUID) -> Deployment:
        try:
            return self.repo.get_deployment(deployment_id)
        except KeyError:
            raise not_found(f"Развёртывание {deployment_id}") from None

    def stop(self, deployment_id: UUID) -> Deployment:
        dep = self.get_deployment(deployment_id)
        if dep.status != DeploymentStatus.RUNNING:
            raise DomainError(409, "invalid_status", f"Остановить можно только запущенный сервер, текущий статус — {dep.status.value}")
        dep.status, dep.finished_at = DeploymentStatus.STOPPED, self.clock()
        return dep

    # ---------- реакции на сообщения ----------
    def _once(self, event: dict) -> bool:
        if self.repo.is_event_processed(event["event_id"]):
            return False
        self.repo.mark_event_processed(event["event_id"])
        return True

    def handle_booking_confirmed(self, event: dict) -> Deployment | None:
        """booking.confirmed → автоматически запустить развёртывание."""
        if not self._once(event):
            return None
        try:
            dep, _ = self._create(UUID(event["booking_id"]), UUID(event["user_id"]))
        except DomainError:  # уже запущено
            return None
        return dep

    def handle_booking_released(self, event: dict) -> None:
        """booking.cancelled / booking.finished → освободить сервер."""
        if not self._once(event):
            return
        dep = self.repo.active_for_booking(UUID(event["booking_id"]))
        if dep is not None:
            dep.status, dep.finished_at = DeploymentStatus.STOPPED, self.clock()
