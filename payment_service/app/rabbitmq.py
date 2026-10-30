import asyncio
import json
import logging

from aio_pika import ExchangeType, IncomingMessage, connect_robust

from app.clients.gateway import FakeGateway
from app.database import SessionLocal
from app.errors import NotFound
from app.events import RabbitPublisher
from app.repositories.db_payment_repo import DbPaymentRepo
from app.services.payment_service import PaymentService
from app.settings import settings

log = logging.getLogger("payment.rabbitmq")

# (обменник, routing key, метод сервиса) → очередь <сервис>.<routing_key>
SUBSCRIPTIONS = [
    ("booking.events", "booking.cancelled", "handle_booking_cancelled"),
    ("booking.events", "booking.extended", "handle_booking_extended"),
]


def _run_handler(method: str, event: dict) -> None:
    db = SessionLocal()
    try:
        service = PaymentService(DbPaymentRepo(db), FakeGateway(settings.gateway_limit), RabbitPublisher())
        getattr(service, method)(event)
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
        queue = await channel.declare_queue(f"payment.{key}", durable=True)
        await queue.bind(exchange, routing_key=key)
        await queue.consume(make_handler(method))
    log.info("Started RabbitMQ consuming...")
    return connection
