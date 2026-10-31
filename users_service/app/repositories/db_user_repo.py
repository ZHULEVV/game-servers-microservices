from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserDB


class DbUserRepo:
    """Реализация поверх PostgreSQL. Интерфейс тот же, что у LocalUserRepo."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, user: User) -> User:
        try:
            self.db.add(UserDB(**user.model_dump()))
            self.db.commit()
        except IntegrityError:  # уникальный индекс по email
            self.db.rollback()
            raise KeyError(f"email {user.email} already exists") from None
        return user

    def get_by_id(self, user_id: UUID) -> User:
        row = self.db.get(UserDB, user_id)
        if row is None:
            raise KeyError(f"User {user_id} not found")
        return User.model_validate(row)

    def get_by_email(self, email: str) -> User | None:
        row = self.db.query(UserDB).filter(UserDB.email == email).first()
        return User.model_validate(row) if row else None
