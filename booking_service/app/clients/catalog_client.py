from datetime import datetime
from decimal import Decimal
from uuid import UUID

import httpx

from app.errors import DependencyUnavailable, NotFound
from app.settings import settings


class CatalogClient:
    """HTTP-клиент к Catalog Service (ПР4: Каталог серверов → Бронирование, проверка доступности)."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.catalog_url
        self.token = token or settings.service_token
        self.timeout = timeout or settings.http_timeout

    def get_availability(self, server_id: UUID, start: datetime, end: datetime) -> tuple[bool, Decimal]:
        try:
            resp = httpx.get(
                f"{self.base_url}/api/servers/{server_id}/availability",
                params={"from": start.isoformat(), "to": end.isoformat()},
                headers={"X-Service-Token": self.token},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise DependencyUnavailable(f"Catalog Service недоступен: {exc.__class__.__name__}") from exc
        if resp.status_code == 404:
            raise NotFound(f"Сервер {server_id} не найден в каталоге")
        if resp.status_code != 200:
            raise DependencyUnavailable(f"Catalog Service ответил {resp.status_code}")
        data = resp.json()
        return bool(data["available"]), Decimal(str(data["price_per_hour"]))
