import random
import sys
from time import sleep

from common import QUEUES, connect, setup

# python consumer.py <очередь>
queue = sys.argv[1]
assert queue in QUEUES, f"неизвестная очередь {queue}"

connection = connect()
channel = connection.channel()
setup(channel)
channel.basic_qos(prefetch_count=1)


def callback(ch, method, properties, body):
    delay = random.randint(1, 5)  # вариант 3: задержка — случайное число секунд из [1, 5]
    print(f" [x] {queue}: получено {body!r}, нагрузка: sleep({delay})")
    sleep(delay)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    print(" [x] Done")


channel.basic_consume(queue=queue, on_message_callback=callback)
print(f" [*] Ждём рассылку в очереди {queue}. Выход: CTRL+C")
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print(" [*] Остановлено, очередь будет удалена брокером (auto_delete)")
