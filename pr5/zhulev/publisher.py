import sys

import pika

from common import EXCHANGE, connect, setup

# python publisher.py <routing_key> <тело> [<тело> ...]
routing_key, *bodies = sys.argv[1:]

connection = connect()
channel = connection.channel()
setup(channel)

for body in bodies:
    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key=routing_key,
        body=body,
        properties=pika.BasicProperties(delivery_mode=pika.spec.PERSISTENT_DELIVERY_MODE),
    )
    print(f"SENT: key={routing_key} body={body!r} (длина {len(body)})")

connection.close()
