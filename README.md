# Аренда игровых серверов — микросервисы (МиАР, ПР5–8)

Предметная область из практических работ 1–4 (Event Storming): платформа аренды игровых серверов.

## ПР5 — брокер сообщений RabbitMQ (`pr5/`)

Скрипты по индивидуальным вариантам (каждая папка — отправитель `publisher.py`, получатель `consumer.py`, общий модуль `common.py`):

| Студент | Папка | Вариант | Очередь | Обменник | Задержка |
|---|---|---|---|---|---|
| Жулёв Е.А. | `pr5/zhulev` | 2 | durable | direct | длина тела |
| Оганнисян Н.Г. | `pr5/ogannisyan` | 1 | auto-delete | topic | число точек в теле |
| Поспелов Д.Д. | `pr5/pospelov` | 3 | auto-delete | fanout | случайное [1, 5] |
| Головач Н.Е. | `pr5/golovach` | 4 | durable | direct | число в теле |

```bash
cd pr5 && docker compose up -d          # RabbitMQ (UI: http://localhost:15672, guest/guest)
python3 -m venv venv && source venv/bin/activate && pip install pika
cd zhulev
python publisher.py payment.succeeded ok:1001 ok:1002
python consumer.py payment.succeeded
```

## ПР6–8 — Booking и Payment (Жулёв Е.А.)

Сервисы `booking_service` (:8003) и `payment_service` (:8004), заглушки соседей `catalog_service`, `deploy_service`, `notification_service`.

```bash
docker compose up --build -d        # вся система
python scripts/demo.py              # сквозной сценарий (нужны httpx, pyjwt)
cd booking_service && pytest -v     # тесты (аналогично payment_service)
```
