import asyncio
import json
import logging

from aio_pika import ExchangeType, IncomingMessage, connect_robust

from app.database import SessionLocal
from app.repositories.db_notification_repo import DbNotificationRepo
from app.services.notification_service import NotificationService
from app.settings import settings

log = logging.getLogger("notification.rabbitmq")
EXCHANGES = ("user.events", "booking.events", "payment.events", "deploy.events", "monitoring.events", "catalog.events", "review.events")


def _handle(routing_key: str, event: dict) -> None:
    db = SessionLocal()
    try:
        note = NotificationService(DbNotificationRepo(db)).handle_event(routing_key, event)
        if note:
            log.info("NOTIFY %s user_id=%s", routing_key, note.user_id)
    finally:
        db.close()


async def process(msg: IncomingMessage) -> None:
    try:
        event = json.loads(msg.body.decode())
        log.info("RECEIVED %s event_id=%s", msg.routing_key, event.get("event_id"))
        await asyncio.to_thread(_handle, msg.routing_key, event)
        await msg.ack()
    except Exception:
        log.exception("Ошибка обработки сообщения")
        await msg.nack(requeue=False)


async def consume(loop):
    connection = await connect_robust(settings.amqp_url, loop=loop)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    queue = await channel.declare_queue("notification.all", durable=True)
    for name in EXCHANGES:
        exchange = await channel.declare_exchange(name, ExchangeType.TOPIC, durable=True)
        await queue.bind(exchange, routing_key="#")
    await queue.consume(process)
    log.info("Started RabbitMQ consuming...")
    return connection
