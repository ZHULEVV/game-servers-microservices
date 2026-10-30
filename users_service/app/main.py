"""Users Service (:8001): регистрация, авторизация, профиль. Учебная in-memory реализация контракта ПР6."""
import hashlib
import hmac
import os
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app.common import ApiError, Principal, get_principal, install, make_token, new_event, now_iso, publish

app = FastAPI(title="Users Service", version="1.0")
install(app)

USERS: dict[UUID, dict] = {}
BY_EMAIL: dict[str, UUID] = {}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


def check_password(password: str, stored: str) -> bool:
    salt, digest = stored.split(":")
    return hmac.compare_digest(hash_password(password, bytes.fromhex(salt)).split(":")[1], digest)


class CreateUser(BaseModel):
    email: str
    name: str
    password: str


class Login(BaseModel):
    email: str
    password: str


def public(user: dict) -> dict:
    return {k: user[k] for k in ("id", "email", "name", "role", "created_at")}


@app.post("/api/users", status_code=201, tags=["Users"])
def create_user(body: CreateUser):
    if not EMAIL_RE.match(body.email):
        raise ApiError(400, "invalid_email", "Некорректный email")
    if len(body.password) < 6:
        raise ApiError(400, "weak_password", "Пароль должен быть не короче 6 символов")
    if not body.name.strip():
        raise ApiError(400, "invalid_name", "Имя не может быть пустым")
    email = body.email.lower()
    if email in BY_EMAIL:
        raise ApiError(409, "email_taken", "Пользователь с таким email уже зарегистрирован")
    user = {"id": str(uuid4()), "email": email, "name": body.name.strip(), "role": "user",
            "created_at": now_iso(), "password_hash": hash_password(body.password)}
    USERS[UUID(user["id"])] = user
    BY_EMAIL[email] = UUID(user["id"])
    publish("user.events", "user.registered", new_event(user_id=user["id"], email=email, name=user["name"]))
    return public(user)


@app.post("/api/users:login", tags=["Users"])
def login(body: Login):
    uid = BY_EMAIL.get(body.email.lower())
    if uid is None or not check_password(body.password, USERS[uid]["password_hash"]):
        raise ApiError(401, "invalid_credentials", "Неверный email или пароль")
    user = USERS[uid]
    return {"token": make_token(uid, user["role"]), "user_id": user["id"], "role": user["role"], "expires_in": 3600}


@app.get("/api/users/{user_id}", tags=["Users"])
def get_user(user_id: UUID, who: Principal = Depends(get_principal)):
    user = USERS.get(user_id)
    if user is None:
        raise ApiError(404, "not_found", f"Пользователь {user_id} не найден")
    if not who.privileged and who.user_id != user_id:
        raise ApiError(403, "forbidden", "Можно просматривать только свой профиль")
    return public(user)
