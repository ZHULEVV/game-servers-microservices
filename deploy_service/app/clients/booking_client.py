from uuid import UUID

import httpx

from app.errors import DomainError, unavailable
from app.settings import settings


class BookingClient:
    """HTTP-клиент к Booking Service: параметры и статус брони (синхронный вызов, ПР4: Развёртывание → Бронирование)."""

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float | None = None) -> None:
        self.base_url = base_url or settings.booking_url
        self.token = token or settings.service_token
        self.timeout = timeout or settings.http_timeout

    def get_booking(self, booking_id: UUID) -> dict:
        try:
            resp = httpx.get(f"{self.base_url}/api/bookings/{booking_id}", headers={"X-Service-Token": self.token}, timeout=self.timeout)
        except httpx.HTTPError as exc:
            raise unavailable("Booking Service", exc.__class__.__name__) from exc
        if resp.status_code == 404:
            raise DomainError(404, "booking_not_found", f"Бронь {booking_id} не найдена")
        if resp.status_code != 200:
            raise unavailable("Booking Service", f"ответ {resp.status_code}")
        return resp.json()
