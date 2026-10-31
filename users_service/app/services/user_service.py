import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.errors import DomainError, not_found
from app.events import make_event
from app.models.user import Role, User
from app.security import create_token
from app.services.passwords import check_password, hash_password

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserService:
    def __init__(self, repo, publisher, clock=utcnow) -> None:
        self.repo = repo
        self.publisher = publisher
        self.clock = clock

    def register(self, email: str, name: str, password: str) -> User:
        if not EMAIL_RE.match(email):
            raise DomainError(400, "invalid_email", "Некорректный email")
        if len(password) < 6:
            raise DomainError(400, "weak_password", "Пароль должен быть не короче 6 символов")
        if not name.strip():
            raise DomainError(400, "invalid_name", "Имя не может быть пустым")
        email = email.lower()
        if self.repo.get_by_email(email) is not None:
            raise DomainError(409, "email_taken", "Пользователь с таким email уже зарегистрирован")
        user = User(id=uuid4(), email=email, name=name.strip(), role=Role.USER,
                    password_hash=hash_password(password), created_at=self.clock())
        try:
            self.repo.add(user)
        except KeyError:  # гонка двух регистраций: уникальный индекс в БД
            raise DomainError(409, "email_taken", "Пользователь с таким email уже зарегистрирован") from None
        self.publisher.publish("user.registered", make_event(user_id=str(user.id), email=user.email, name=user.name))
        return user

    def login(self, email: str, password: str) -> tuple[str, User]:
        user = self.repo.get_by_email(email.lower())
        if user is None or not check_password(password, user.password_hash):
            raise DomainError(401, "invalid_credentials", "Неверный email или пароль")
        return create_token(user.id, user.role.value), user

    def get_user(self, user_id: UUID) -> User:
        try:
            return self.repo.get_by_id(user_id)
        except KeyError:
            raise not_found(f"Пользователь {user_id}") from None
