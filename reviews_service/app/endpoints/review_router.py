from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.dependencies import get_service
from app.errors import forbidden
from app.models.review import Review
from app.security import Principal, get_principal
from app.services.review_service import ReviewService

router = APIRouter(tags=["Reviews"])


class CreateReviewRequest(BaseModel):
    booking_id: UUID
    rating: int
    text: str = ""


class ReviewPage(BaseModel):
    items: list[Review]
    offset: int
    count: int
    total: int
    average_rating: float | None = None


@router.post("/reviews", status_code=201, response_model=Review)
def create_review(body: CreateReviewRequest, who: Principal = Depends(get_principal), service: ReviewService = Depends(get_service)):
    if who.user_id is None:
        raise forbidden("Отзыв оставляет пользователь")
    return service.create_review(who.user_id, body.booking_id, body.rating, body.text)


@router.get("/reviews/{review_id}", response_model=Review)
def get_review(review_id: UUID, service: ReviewService = Depends(get_service)):
    return service.get_review(review_id)


@router.get("/servers/{server_id}/reviews", response_model=ReviewPage)
def server_reviews(server_id: UUID, min_rating: int | None = Query(default=None, ge=1, le=5), offset: int = Query(default=0, ge=0),
                   count: int = Query(default=20, ge=1, le=100), service: ReviewService = Depends(get_service)):
    items, total, avg = service.server_reviews(server_id, min_rating, offset, count)
    return ReviewPage(items=items, offset=offset, count=count, total=total, average_rating=avg)
