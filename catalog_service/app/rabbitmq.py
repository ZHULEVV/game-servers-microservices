import asyncio
import json
import logging

from aio_pika import ExchangeType, IncomingMessage, connect_robust

from app.database import SessionLocal
from app.errors import DomainError
from app.events import RabbitPublisher
from app.repositories.db_server_repo import DbServerRepo
from app.services.server_service import ServerService
from app.settings import settings

log = logging.getLogger("catalog.rabbitmq")

# (обменник, routing key, метод сервиса) → очередь <сервис>.<routing_key>
SUBSCRIPTIONS = [("review.events", "review.published", "handle_review_published")]


def _run_handler(method: str, event: dict) -> None:
    db = SessionLocal()
    try:
        getattr(ServerService(DbServerRepo(db), RabbitPublisher("catalog.events")), method)(event)
    finally:
        db.close()


def make_handler(method: str):
    async def process(msg: IncomingMessage) -> None:
        try:
            event = json.loads(msg.body.decode())
            log.info("RECEIVED %s event_id=%s", msg.routing_key, event.get("event_id"))
            await asyncio.to_thread(_run_handler, method, event)
            await msg.ack()
        except DomainError as exc:
            log.warning("Сообщение отброшено: %s", exc.message)
            await msg.ack()
        except Exception:
            log.exception("Ошибка обработки сообщения")
            await msg.nack(requeue=False)

    return process


async def consume(loop):
    connection = await connect_robust(settings.amqp_url, loop=loop)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    for exchange_name, key, method in SUBSCRIPTIONS:
        exchange = await channel.declare_exchange(exchange_name, ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(f"catalog.{key}", durable=True)
        await queue.bind(exchange, routing_key=key)
        await queue.consume(make_handler(method))
    log.info("Started RabbitMQ consuming...")
    return connection
