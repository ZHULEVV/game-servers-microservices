import asyncio
import json
import logging

from aio_pika import ExchangeType, IncomingMessage, connect_robust

from app.database import SessionLocal
from app.errors import NotFound
from app.clients.catalog_client import CatalogClient
from app.clients.payment_client import PaymentClient
from app.events import RabbitPublisher
from app.repositories.db_booking_repo import DbBookingRepo
from app.services.booking_service import BookingService
from app.settings import settings

log = logging.getLogger("booking.rabbitmq")

# (обменник, routing key, метод сервиса) → очередь <сервис>.<routing_key>
SUBSCRIPTIONS = [
    ("payment.events", "payment.succeeded", "handle_payment_succeeded"),
    ("payment.events", "payment.failed", "handle_payment_failed"),
    ("deploy.events", "deploy.completed", "handle_deploy_completed"),
    ("deploy.events", "deploy.failed", "handle_deploy_failed"),
]


def _run_handler(method: str, event: dict | None) -> None:
    db = SessionLocal()
    try:
        service = BookingService(DbBookingRepo(db), PaymentClient(), CatalogClient(), RabbitPublisher())
        getattr(service, method)(*([event] if event is not None else []))
    finally:
        db.close()


def make_handler(method: str):
    async def process(msg: IncomingMessage) -> None:
        try:
            event = json.loads(msg.body.decode())
            log.info("RECEIVED %s event_id=%s", msg.routing_key, event.get("event_id"))
            await asyncio.to_thread(_run_handler, method, event)
            await msg.ack()
        except NotFound:
            log.warning("Бронь из события не найдена, сообщение отбрасывается")
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
        queue = await channel.declare_queue(f"booking.{key}", durable=True)
        await queue.bind(exchange, routing_key=key)
        await queue.consume(make_handler(method))
    log.info("Started RabbitMQ consuming...")
    return connection


async def finisher() -> None:
    """Периодически завершает истёкшие аренды (команда «Закончить время аренды»)."""
    while True:
        await asyncio.sleep(settings.finish_check_seconds)
        try:
            await asyncio.to_thread(_run_handler, "finish_expired", None)
        except Exception:
            log.exception("finish_expired")
