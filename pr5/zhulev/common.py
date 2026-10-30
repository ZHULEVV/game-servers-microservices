import pika

EXCHANGE = "ikbo-63-23_zhulev.direct"

# routing key -> очередь (формат имени <группа>_<фамилия>)
ROUTES = {
    "payment.succeeded": "ikbo-63-23_zhulev",
    "payment.failed": "ikbo-63-23_zhulev_failed",
}


def connect() -> pika.BlockingConnection:
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            "localhost", 5672, credentials=pika.PlainCredentials("guest", "guest")
        )
    )


def setup(channel) -> None:
    """Объявляем обменник, очереди и привязки (идемпотентно, вызывается и у отправителя, и у получателя)."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    for routing_key, queue in ROUTES.items():
        channel.queue_declare(queue=queue, durable=True)
        channel.queue_bind(exchange=EXCHANGE, queue=queue, routing_key=routing_key)
