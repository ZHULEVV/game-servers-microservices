from decimal import Decimal
from uuid import UUID

import httpx

from app.errors import DependencyUnavailable
from app.settings import settings


class PaymentClient:
    """HTTP-клиент к Payment Service (синхронный вызов, ПР4: Бронирование → Оплата)."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float | None = None):
        self.base_url = base_url or settings.payment_url
        self.token = token or settings.service_token
        self.timeout = timeout or settings.http_timeout

    def create_invoice(self, booking_id: UUID, user_id: UUID, amount: Decimal, card_token: str | None) -> dict:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/payments",
                json={"booking_id": str(booking_id), "user_id": str(user_id), "amount": str(amount),
                      "card_token": card_token},
                headers={"X-Service-Token": self.token},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise DependencyUnavailable(f"Payment Service недоступен: {exc.__class__.__name__}") from exc
        if resp.status_code >= 500:
            raise DependencyUnavailable(f"Payment Service ответил {resp.status_code}")
        if resp.status_code != 201:
            raise DependencyUnavailable(f"Payment Service отклонил запрос: {resp.status_code}")
        return resp.json()
