import json
import logging
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

import pika

from app.settings import settings

log = logging.getLogger("events")


class EventPublisher(Protocol):
    def publish(self, routing_key: str, payload: dict) -> None: ...


def make_event(**fields) -> dict:
    """Общие поля любого сообщения: event_id, occurred_at (+ booking_id/user_id в полях)."""
    return {"event_id": str(uuid4()), "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), **fields}


class RabbitPublisher:
    def __init__(self, exchange: str) -> None:
        self.exchange = exchange

    def publish(self, routing_key: str, payload: dict) -> None:
        try:
            conn = pika.BlockingConnection(pika.URLParameters(settings.amqp_url))
            try:
                ch = conn.channel()
                ch.exchange_declare(exchange=self.exchange, exchange_type="topic", durable=True)
                ch.basic_publish(
                    exchange=self.exchange, routing_key=routing_key,
                    body=json.dumps(payload, default=str, ensure_ascii=False),
                    properties=pika.BasicProperties(content_type="application/json", delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE),
                )
                log.info("PUBLISHED %s %s", routing_key, payload.get("event_id"))
            finally:
                conn.close()
        except Exception:  # брокер недоступен: бизнес-операция уже выполнена, событие логируем
            log.exception("Не удалось опубликовать %s", routing_key)


class FakePublisher:
    """Подмена брокера в тестах: запоминает опубликованные сообщения."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def publish(self, routing_key: str, payload: dict) -> None:
        self.sent.append((routing_key, payload))
