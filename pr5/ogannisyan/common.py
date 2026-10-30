import pika

EXCHANGE = "ikbo-63-23_ogannisyan.topic"

# очередь -> шаблон ключа маршрутизации (topic: * — ровно одно слово, # — любое число слов)
QUEUES = {
    "ikbo-63-23_ogannisyan": "booking.*",
    "ikbo-63-23_ogannisyan_payments": "payment.#",
}


def connect() -> pika.BlockingConnection:
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            "localhost", 5672, credentials=pika.PlainCredentials("guest", "guest")
        )
    )


def setup(channel) -> None:
    """Обменник topic и авто-удаляемые очереди с привязками (вызывается и у отправителя, и у получателя)."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic")
    for queue, pattern in QUEUES.items():
        channel.queue_declare(queue=queue, auto_delete=True)
        channel.queue_bind(exchange=EXCHANGE, queue=queue, routing_key=pattern)
