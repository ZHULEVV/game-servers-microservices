"""Booking при недоступном Payment Service: ожидаем 503 и отменённую бронь."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt

now = datetime.now(timezone.utc)
user = str(uuid4())
token = jwt.encode({"sub": user, "role": "user", "exp": now + timedelta(hours=1)},
                   "game-servers-jwt-secret-key-32-bytes", algorithm="HS256")
auth = {"Authorization": f"Bearer {token}"}
resp = httpx.post("http://localhost:8003/api/bookings", headers=auth, json={
    "server_id": "33333333-3333-4333-8333-333333333333",
    "start": (now + timedelta(hours=10)).isoformat(), "end": (now + timedelta(hours=12)).isoformat()})
print("POST /api/bookings при остановленном Payment Service ->", resp.status_code, resp.json())
items = httpx.get("http://localhost:8003/api/bookings", headers=auth).json()["items"]
print("Бронь пользователя:", [(b["status"], b["cancel_reason"]) for b in items])
