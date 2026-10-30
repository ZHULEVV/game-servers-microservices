import pika

EXCHANGE = "ikbo-63-23_pospelov.fanout"

# подписчики рассылки: каждый получает свою копию каждого сообщения
QUEUES = ["ikbo-63-23_pospelov", "ikbo-63-23_pospelov_notify"]


def connect() -> pika.BlockingConnection:
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            "localhost", 5672, credentials=pika.PlainCredentials("guest", "guest")
        )
    )


def setup(channel) -> None:
    """Обменник fanout и авто-удаляемые очереди; ключ маршрутизации не нужен."""
    channel.exchange_declare(exchange=EXCHANGE, exchange_type="fanout")
    for queue in QUEUES:
        channel.queue_declare(queue=queue, auto_delete=True)
        channel.queue_bind(exchange=EXCHANGE, queue=queue)
