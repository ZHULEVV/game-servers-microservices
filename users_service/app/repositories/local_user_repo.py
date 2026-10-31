from uuid import UUID

from app.models.user import User


class LocalUserRepo:
    """In-memory реализация (unit- и компонентные тесты)."""

    def __init__(self) -> None:
        self._items: dict[UUID, User] = {}

    def add(self, user: User) -> User:
        if self.get_by_email(user.email) is not None:
            raise KeyError(f"email {user.email} already exists")
        self._items[user.id] = user
        return user

    def get_by_id(self, user_id: UUID) -> User:
        try:
            return self._items[user_id]
        except KeyError:
            raise KeyError(f"User {user_id} not found") from None

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._items.values() if u.email == email), None)
