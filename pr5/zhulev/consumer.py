import sys
from time import sleep

from common import ROUTES, connect, setup

# python consumer.py <routing_key>
routing_key = sys.argv[1]
queue = ROUTES[routing_key]

connection = connect()
channel = connection.channel()
setup(channel)
channel.basic_qos(prefetch_count=1)


def callback(ch, method, properties, body):
    delay = len(body)  # вариант 2: задержка (с) = длина тела сообщения
    print(f" [x] Received {body!r}, key={method.routing_key}, нагрузка: sleep({delay})")
    sleep(delay)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    print(" [x] Done")


channel.basic_consume(queue=queue, on_message_callback=callback)
print(f" [*] Ждём сообщения в очереди {queue} (ключ {routing_key}). Выход: CTRL+C")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print(" [*] Остановлено")
