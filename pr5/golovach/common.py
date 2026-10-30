import pika

EXCHANGE = "ikbo-63-23_golovach.direct"

# ключ маршрутизации -> очередь
ROUTES = {
    "deploy.start": "ikbo-63-23_golovach",
    "deploy.stop": "ikbo-63-23_golovach_stop",
}


def connect() -> pika.BlockingConnection:
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            "localhost", 5672, credentials=pika.PlainCredentials("guest", "guest")
        )
    )


def setup(channel) -> None:
    """Сохраняемые обменник и очереди с привязками по точному ключу."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="direct", durable=True)
    for routing_key, queue in ROUTES.items():
        channel.queue_declare(queue=queue, durable=True)
        channel.queue_bind(exchange=EXCHANGE, queue=queue, routing_key=routing_key)
