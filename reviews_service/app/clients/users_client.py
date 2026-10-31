from uuid import UUID

import httpx

from app.errors import DomainError, unavailable
from app.settings import settings


class UsersClient:
    """HTTP-клиент к Users Service: проверка, что автор отзыва существует (синхронный вызов)."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float | None = None) -> None:
        self.base_url = base_url or settings.users_url
        self.token = token or settings.service_token
        self.timeout = timeout or settings.http_timeout

    def get_user(self, user_id: UUID) -> dict:
        try:
            resp = httpx.get(f"{self.base_url}/api/users/{user_id}", headers={"X-Service-Token": self.token}, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise unavailable("Users Service", exc.__class__.__name__) from exc
        if resp.status_code == 404:
            raise DomainError(404, "author_not_found", f"Пользователь {user_id} не найден")
        if resp.status_code != 200:
            raise unavailable("Users Service", f"ответ {resp.status_code}")
        return resp.json()
