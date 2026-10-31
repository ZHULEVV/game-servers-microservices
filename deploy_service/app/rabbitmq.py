import asyncio
import json
import logging

from aio_pika import ExchangeType, IncomingMessage, connect_robust

from app.dependencies import get_service
from app.errors import DomainError
from app.runner import run_deployment
from app.settings import settings

log = logging.getLogger("deploy.rabbitmq")
SUBSCRIPTIONS = [("booking.events", "booking.confirmed", "handle_booking_confirmed"),
                 ("booking.events", "booking.cancelled", "handle_booking_released"),
                 ("booking.events", "booking.finished", "handle_booking_released")]


def make_handler(method: str):
    async def process(msg: IncomingMessage) -> None:
        try:
            event = json.loads(msg.body.decode())
            log.info("RECEIVED %s event_id=%s booking_id=%s", msg.routing_key, event.get("event_id"), event.get("booking_id"))
            if method == "handle_booking_confirmed" and not settings.auto_deploy:
                log.info("AUTO_DEPLOY=false: автоматический запуск пропущен")
            else:
                result = await asyncio.to_thread(getattr(get_service(), method), event)
                if method == "handle_booking_confirmed" and result is not None:
                    asyncio.ensure_future(run_deployment(result.id))
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
        queue = await channel.declare_queue(f"deploy.{key}", durable=True)
        await queue.bind(exchange, routing_key=key)
        await queue.consume(make_handler(method))
    log.info("Started RabbitMQ consuming...")
    return connection
