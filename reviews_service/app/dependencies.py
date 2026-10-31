from app.clients.users_client import UsersClient
from app.events import RabbitPublisher
from app.repositories.local_review_repo import LocalReviewRepo
from app.services.review_service import ReviewService

_repo = LocalReviewRepo()  # одно хранилище на процесс: его делят HTTP-запросы и потребитель сообщений


def get_service() -> ReviewService:
    return ReviewService(_repo, UsersClient(), RabbitPublisher("review.events"))
