from typing import Protocol
from uuid import UUID

from app.models.user import User


class UserRepoProtocol(Protocol):
    def add(self, user: User) -> User: ...
    def get_by_id(self, user_id: UUID) -> User: ...
    def get_by_email(self, email: str) -> User | None: ...
