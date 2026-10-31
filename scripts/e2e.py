"""Сквозной сценарий через все 8 сервисов: регистрация → поиск → бронь → оплата → деплой → мониторинг → завершение → отзыв → рейтинг → уведомления."""
import sys, time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx

H = {"users": "http://localhost:8001/api", "catalog": "http://localhost:8002/api", "booking": "http://localhost:8003/api",
     "payment": "http://localhost:8004/api", "monitoring": "http://localhost:8005/api", "deploy": "http://localhost:8006/api",
     "notification": "http://localhost:8007/api", "reviews": "http://localhost:8008/api"}
SVC = {"X-Service-Token": "service-secret"}
email = f"user{uuid4().hex[:6]}@mail.com"


def step(n, title, r, pick=None):
    body = r.json() if r.content else None
    shown = {k: body.get(k) for k in pick} if (pick and isinstance(body, dict)) else body
    print(f"{n}. {title}\n   -> {r.status_code} {shown}")
    return body


u = step(1, "Регистрация (Users)", httpx.post(f"{H['users']}/users", json={"email": email, "name": "Ivan", "password": "secret1"}), ["id", "email", "role"])
tok = step(2, "Вход (Users)", httpx.post(f"{H['users']}/users:login", json={"email": email, "password": "secret1"}), ["role", "expires_in"])
auth = {"Authorization": f"Bearer {tok['token']}"}
found = step(3, "Поиск серверов Minecraft до 200 (Catalog)", httpx.get(f"{H['catalog']}/servers", params={"game": "minecraft", "max_price": 200}), ["total"])
sid = httpx.get(f"{H['catalog']}/servers", params={"game": "minecraft", "region": "eu"}).json()["items"][0]["id"]
import random
now = datetime.now(timezone.utc) + timedelta(hours=random.randint(100, 2000))  # свободное окно: сервер не занят другими бронями
b = step(4, "Бронь на 3 часа (Booking → Catalog, Payment)", httpx.post(f"{H['booking']}/bookings", headers=auth, json={
    "server_id": sid, "start": now.isoformat(), "end": (now + timedelta(hours=3)).isoformat()}), ["status", "amount"])
bid = b["id"]
time.sleep(10)
step(5, "Бронь после оплаты и развёртывания (RabbitMQ: payment.succeeded → booking.confirmed → deploy.completed)", httpx.get(f"{H['booking']}/bookings/{bid}", headers=auth), ["status"])
step(6, "Монитор запущен по deploy.completed (Monitoring)", httpx.get(f"{H['monitoring']}/monitors/{bid}", headers=auth), ["status", "thresholds"])
step(7, "Метрики агента: cpu=97 (Monitoring)", httpx.post(f"{H['monitoring']}/monitors/{bid}/samples", headers=SVC, json={"cpu": 97, "ram": 40}))
step(8, "Пороги 80/70 (Monitoring → Booking)", httpx.put(f"{H['monitoring']}/monitors/{bid}/thresholds", headers=auth, json={"cpu": 80, "ram": 70}), ["thresholds"])
pay = httpx.get(f"{H['payment']}/payments", headers=auth, params={"booking_id": bid}).json()
print(f"9. Платежи брони (Payment): {[(p['amount'], p['status']) for p in pay['items']]}")
# завершение аренды: событие публикует Booking по истечении срока; в демо отправляем его вручную
import subprocess
PY = sys.executable
subprocess.run([PY, "scripts/publish_event.py", "booking.events", "booking.finished", f"booking_id={bid}", f"user_id={u['id']}", f"server_id={sid}"], capture_output=True)
time.sleep(2)
r = step(10, "Отзыв после завершения аренды (Reviews → Users)", httpx.post(f"{H['reviews']}/reviews", headers=auth, json={"booking_id": bid, "rating": 5, "text": "Отлично"}), ["rating", "server_id"])
time.sleep(2)
step(11, "Рейтинг сервера обновлён по review.published (Catalog)", httpx.get(f"{H['catalog']}/servers/{sid}"), ["name", "rating", "rating_count"])
n = httpx.get(f"{H['notification']}/notifications", headers=auth, params={"count": 50}).json()
print(f"12. Уведомления пользователя (Notification): {sorted({x['type'] for x in n['items']})}")
