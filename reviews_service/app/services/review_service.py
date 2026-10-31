from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.errors import DomainError, not_found
from app.events import make_event
from app.models.review import Review, ReviewSlot


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReviewService:
    def __init__(self, repo, users_client, publisher, clock=utcnow) -> None:
        self.repo = repo
        self.users = users_client
        self.publisher = publisher
        self.clock = clock

    def create_review(self, user_id: UUID, booking_id: UUID, rating: int, text: str = "") -> Review:
        if not 1 <= rating <= 5:
            raise DomainError(400, "invalid_rating", "Оценка должна быть от 1 до 5")
        if len(text) > 1000:
            raise DomainError(400, "text_too_long", "Текст отзыва — не более 1000 символов")
        slot = self.repo.get_slot(booking_id)
        if slot is None:
            raise DomainError(409, "review_not_open", "Отзыв можно оставить только после завершения аренды")
        if slot.user_id != user_id:
            raise DomainError(403, "forbidden", "Нельзя оставить отзыв на чужую аренду")
        if self.repo.get_by_booking(booking_id) is not None:
            raise DomainError(409, "review_exists", "Отзыв на эту аренду уже оставлен")
        self.users.get_user(user_id)  # синхронный вызов Users Service: автор должен существовать
        review = Review(id=uuid4(), booking_id=booking_id, server_id=slot.server_id, user_id=user_id,
                        rating=rating, text=text, created_at=self.clock())
        self.repo.add(review)
        self.publisher.publish("review.published", make_event(review_id=str(review.id), booking_id=str(booking_id),
                               server_id=str(slot.server_id), user_id=str(user_id), rating=rating))
        return review

    def get_review(self, review_id: UUID) -> Review:
        try:
            return self.repo.get_by_id(review_id)
        except KeyError:
            raise not_found(f"Отзыв {review_id}") from None

    def server_reviews(self, server_id: UUID, min_rating=None, offset=0, count=20):
        return self.repo.list_for_server(server_id, min_rating, offset, count)

    def handle_booking_finished(self, event: dict) -> None:
        """booking.finished → открыть возможность оставить отзыв."""
        if self.repo.is_event_processed(event["event_id"]):
            return
        self.repo.mark_event_processed(event["event_id"])
        self.repo.open_slot(ReviewSlot(booking_id=UUID(event["booking_id"]), user_id=UUID(event["user_id"]), server_id=UUID(event["server_id"])))
