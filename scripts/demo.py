"""Сквозной сценарий: бронь → оплата (RabbitMQ) → деплой → продление → отмена → возврат; отказ шлюза."""
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt

BOOKING, PAYMENT, NOTIFY = "http://localhost:8003/api", "http://localhost:8004/api", "http://localhost:8007/api"
SERVICE = {"X-Service-Token": "service-secret"}
USER = str(uuid4())
TOKEN = jwt.encode({"sub": USER, "role": "user", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                   "game-servers-jwt-secret-key-32-bytes", algorithm="HS256")
AUTH = {"Authorization": f"Bearer {TOKEN}"}
MC, CS2 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
now = datetime.now(timezone.utc)


def show(title, resp, fields=None):
    body = resp.json()
    if fields and isinstance(body, dict):
        body = {k: body.get(k) for k in fields}
    print(f"{title}\n  -> {resp.status_code} {body}")


def payments_of(booking_id):
    items = httpx.get(f"{PAYMENT}/payments", params={"booking_id": booking_id}, headers=AUTH).json()["items"]
    return [(p["amount"], p["status"]) for p in items]


print(f"Пользователь: {USER}\n")
b = httpx.post(f"{BOOKING}/bookings", headers=AUTH, json={
    "server_id": MC, "start": (now + timedelta(hours=1)).isoformat(), "end": (now + timedelta(hours=4)).isoformat()})
show("1. POST /bookings (Minecraft, 3 ч × 150)", b, ["status", "amount"])
bid = b.json()["id"]

show("2. Повторная бронь на то же время", httpx.post(f"{BOOKING}/bookings", headers=AUTH, json={
    "server_id": MC, "start": (now + timedelta(hours=2)).isoformat(), "end": (now + timedelta(hours=3)).isoformat()}))

time.sleep(1)
print("3. Сразу после создания:", httpx.get(f"{BOOKING}/bookings/{bid}", headers=AUTH).json()["status"])
time.sleep(7)
print("4. Через 8 с (payment.succeeded → booking.confirmed → deploy.completed):",
      httpx.get(f"{BOOKING}/bookings/{bid}", headers=AUTH).json()["status"])
print("   Платежи брони:", payments_of(bid))

show("5. POST /bookings/{id}:extend (+2 ч)", httpx.post(f"{BOOKING}/bookings/{bid}:extend", headers=AUTH,
     json={"new_end": (now + timedelta(hours=6)).isoformat()}), ["status", "amount"])
time.sleep(4)
print("   Платежи брони (основной + доплата):", payments_of(bid))

show("6. POST /bookings/{id}:cancel", httpx.post(f"{BOOKING}/bookings/{bid}:cancel", headers=AUTH,
     json={"reason": "передумал"}), ["status", "cancel_reason"])
show("7. Повторная отмена", httpx.post(f"{BOOKING}/bookings/{bid}:cancel", headers=AUTH, json={}))
time.sleep(3)
print("8. Платежи после отмены (booking.cancelled → возврат):", payments_of(bid))

f = httpx.post(f"{BOOKING}/bookings", headers=AUTH, json={
    "server_id": CS2, "start": (now + timedelta(hours=1)).isoformat(), "end": (now + timedelta(hours=2)).isoformat(),
    "card_token": "tok_fail"})
show("9. Бронь с картой, которую отклонит шлюз", f, ["status", "amount"])
time.sleep(5)
fb = httpx.get(f"{BOOKING}/bookings/{f.json()['id']}", headers=AUTH).json()
print("10. Статус через 5 с:", fb["status"], "| причина:", fb["cancel_reason"])
print("    Платежи:", payments_of(f.json()["id"]))

notes = httpx.get(f"{NOTIFY}/notifications", params={"user_id": USER}).json()["items"]
print("\nNotification Service получил события:", [n["type"] for n in notes])
