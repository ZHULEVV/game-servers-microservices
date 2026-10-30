"""Публикация события в RabbitMQ (имитация другого сервиса) для демонстраций.
python scripts/publish_event.py <exchange> <routing_key> поле=значение ..."""
import json
import sys
from datetime import datetime, timezone
from uuid import uuid4

import pika

exchange, routing_key, *pairs = sys.argv[1:]
event = {"event_id": str(uuid4()), "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
event.update(p.split("=", 1) for p in pairs)
conn = pika.BlockingConnection(pika.ConnectionParameters("localhost", 5672, credentials=pika.PlainCredentials("guest", "guest")))
ch = conn.channel()
ch.exchange_declare(exchange=exchange, exchange_type="topic", durable=True)
ch.basic_publish(exchange=exchange, routing_key=routing_key, body=json.dumps(event, ensure_ascii=False),
                 properties=pika.BasicProperties(content_type="application/json", delivery_mode=2))
print(f"PUBLISHED {routing_key}: {json.dumps(event, ensure_ascii=False)}")
conn.close()
