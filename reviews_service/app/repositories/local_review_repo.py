from uuid import UUID

from app.models.review import Review, ReviewSlot


class LocalReviewRepo:
    """Хранилище отзывов в памяти процесса (за интерфейсом репозитория его можно заменить на БД без изменения сервиса)."""

    def __init__(self) -> None:
        self._slots: dict[UUID, ReviewSlot] = {}
        self._reviews: dict[UUID, Review] = {}
        self._events: set[str] = set()

    def open_slot(self, slot: ReviewSlot) -> None:
        self._slots[slot.booking_id] = slot

    def get_slot(self, booking_id: UUID) -> ReviewSlot | None:
        return self._slots.get(booking_id)

    def add(self, review: Review) -> Review:
        self._reviews[review.id] = review
        return review

    def get_by_id(self, review_id: UUID) -> Review:
        try:
            return self._reviews[review_id]
        except KeyError:
            raise KeyError(f"Review {review_id} not found") from None

    def get_by_booking(self, booking_id: UUID) -> Review | None:
        return next((r for r in self._reviews.values() if r.booking_id == booking_id), None)

    def list_for_server(self, server_id: UUID, min_rating: int | None, offset: int, count: int):
        rows = sorted((r for r in self._reviews.values() if r.server_id == server_id and (min_rating is None or r.rating >= min_rating)),
                      key=lambda r: r.created_at, reverse=True)
        avg = round(sum(r.rating for r in rows) / len(rows), 2) if rows else None
        return rows[offset:offset + count], len(rows), avg

    def is_event_processed(self, event_id: str) -> bool:
        return event_id in self._events

    def mark_event_processed(self, event_id: str) -> None:
        self._events.add(event_id)
