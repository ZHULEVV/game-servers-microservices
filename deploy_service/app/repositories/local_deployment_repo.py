from uuid import UUID

from app.models.deployment import Deployment, DeploymentStatus, Operation


class LocalDeploymentRepo:
    """Хранилище развёртываний в памяти процесса (за интерфейсом репозитория его можно заменить на БД)."""

    def __init__(self) -> None:
        self._deployments: dict[UUID, Deployment] = {}
        self._operations: dict[UUID, Operation] = {}
        self._events: set[str] = set()

    def add(self, deployment: Deployment, operation: Operation) -> None:
        self._deployments[deployment.id] = deployment
        self._operations[operation.id] = operation

    def get_deployment(self, deployment_id: UUID) -> Deployment:
        try:
            return self._deployments[deployment_id]
        except KeyError:
            raise KeyError(f"Deployment {deployment_id} not found") from None

    def get_operation(self, operation_id: UUID) -> Operation:
        try:
            return self._operations[operation_id]
        except KeyError:
            raise KeyError(f"Operation {operation_id} not found") from None

    def operation_of(self, deployment_id: UUID) -> Operation:
        return next(o for o in self._operations.values() if o.deployment_id == deployment_id)

    def active_for_booking(self, booking_id: UUID) -> Deployment | None:
        return next((d for d in self._deployments.values()
                     if d.booking_id == booking_id and d.status in (DeploymentStatus.PROVISIONING, DeploymentStatus.RUNNING)), None)

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self._events

    def mark_event_processed(self, event_id: str) -> None:
        self._events.add(event_id)
