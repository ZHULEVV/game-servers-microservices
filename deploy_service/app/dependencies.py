from app.clients.booking_client import BookingClient
from app.events import RabbitPublisher
from app.repositories.local_deployment_repo import LocalDeploymentRepo
from app.services.deployment_service import DeploymentService

_repo = LocalDeploymentRepo()  # одно хранилище на процесс: его делят HTTP-запросы и потребитель сообщений


def get_service() -> DeploymentService:
    return DeploymentService(_repo, BookingClient(), RabbitPublisher("deploy.events"))
