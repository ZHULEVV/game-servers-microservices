"""Reviews Service (:8008): отзывы об арендованных серверах. Право оставить отзыв открывает событие booking.finished."""
import asyncio
import json
import logging
from uuid import UUID, uuid4

from aio_pika import ExchangeType, connect_robust
from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel

from app.common import AMQP_URL, ApiError, Principal, get_principal, install, new_event, now_iso, page, publish

log = logging.getLogger("reviews")
app = FastAPI(title="Reviews Service", version="1.0")
install(app)

OPEN: dict[str, dict] = {}      # booking_id -> {user_id, server_id}: аренда завершена, отзыв можно оставить
REVIEWS: dict[str, dict] = {}   # review_id -> review
SEEN: set[str] = set()          # обработанные event_id (дедупликация)


class CreateReview(BaseModel):
    booking_id: UUID
    rating: int
    text: str = ""


async def consume():
    conn = await connect_robust(AMQP_URL)
    ch = await conn.channel()
    await ch.set_qos(prefetch_count=1)
    ex = await ch.declare_exchange("booking.events", ExchangeType.TOPIC, durable=True)
    q = await ch.declare_queue("reviews.booking.finished", durable=True)
    await q.bind(ex, routing_key="booking.finished")

    async def on_finished(msg):
        async with msg.process():
            ev = json.loads(msg.body)
            if ev["event_id"] in SEEN:
                return
            SEEN.add(ev["event_id"])
            OPEN[ev["booking_id"]] = {"user_id": ev["user_id"], "server_id": ev["server_id"]}
            log.info("RECEIVED booking.finished booking_id=%s -> отзыв открыт", ev["booking_id"])

    await q.consume(on_finished)
    return conn


@app.on_event("startup")
async def startup():
    asyncio.ensure_future(consume())


@app.post("/api/reviews", status_code=201, tags=["Reviews"])
def create_review(body: CreateReview, who: Principal = Depends(get_principal)):
    if who.user_id is None:
        raise ApiError(403, "forbidden", "Отзыв оставляет пользователь")
    if not 1 <= body.rating <= 5:
        raise ApiError(400, "invalid_rating", "Оценка должна быть от 1 до 5")
    if len(body.text) > 1000:
        raise ApiError(400, "text_too_long", "Текст отзыва — не более 1000 символов")
    booking = OPEN.get(str(body.booking_id))
    if booking is None:
        raise ApiError(409, "review_not_open", "Отзыв можно оставить только после завершения аренды")
    if booking["user_id"] != str(who.user_id):
        raise ApiError(403, "forbidden", "Нельзя оставить отзыв на чужую аренду")
    if any(r["booking_id"] == str(body.booking_id) for r in REVIEWS.values()):
        raise ApiError(409, "review_exists", "Отзыв на эту аренду уже оставлен")
    review = {"id": str(uuid4()), "booking_id": str(body.booking_id), "server_id": booking["server_id"],
              "user_id": str(who.user_id), "rating": body.rating, "text": body.text, "created_at": now_iso()}
    REVIEWS[review["id"]] = review
    publish("review.events", "review.published", new_event(review_id=review["id"], booking_id=review["booking_id"],
            server_id=review["server_id"], user_id=review["user_id"], rating=review["rating"]))
    return review


@app.get("/api/reviews/{review_id}", tags=["Reviews"])
def get_review(review_id: UUID):
    review = REVIEWS.get(str(review_id))
    if review is None:
        raise ApiError(404, "not_found", f"Отзыв {review_id} не найден")
    return review


@app.get("/api/servers/{server_id}/reviews", tags=["Reviews"])
def server_reviews(server_id: UUID, min_rating: int | None = Query(default=None, ge=1, le=5),
                   offset: int = Query(default=0, ge=0), count: int = Query(default=20, ge=1, le=100)):
    items = [r for r in REVIEWS.values() if r["server_id"] == str(server_id) and (min_rating is None or r["rating"] >= min_rating)]
    items.sort(key=lambda r: r["created_at"], reverse=True)
    avg = round(sum(r["rating"] for r in items) / len(items), 2) if items else None
    return page(items, offset, count, average_rating=avg)
