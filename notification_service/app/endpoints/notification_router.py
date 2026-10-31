from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.dependencies import get_service
from app.errors import forbidden
from app.models.notification import Notification
from app.security import Principal, get_principal, require_owner_or_privileged
from app.services.notification_service import NotificationService

router = APIRouter(tags=["Notifications"])


class NotificationPage(BaseModel):
    items: list[Notification]
    offset: int
    count: int
    total: int


@router.get("/notifications", response_model=NotificationPage)
def list_notifications(user_id: UUID | None = None, type: str | None = None, unread: bool | None = None,
                       offset: int = Query(default=0, ge=0), count: int = Query(default=20, ge=1, le=100),
                       who: Principal = Depends(get_principal), service: NotificationService = Depends(get_service)):
    if not who.privileged:
        if user_id not in (None, who.user_id):
            raise forbidden("Можно запрашивать только свои уведомления")
        user_id = who.user_id
    items, total = service.list_notifications(user_id, type, unread, offset, count)
    return NotificationPage(items=items, offset=offset, count=count, total=total)


@router.post("/notifications/{notification_id}:read", response_model=Notification)
def mark_read(notification_id: UUID, who: Principal = Depends(get_principal), service: NotificationService = Depends(get_service)):
    note = service.get_notification(notification_id)
    require_owner_or_privileged(who, note.user_id, "уведомление")
    return service.mark_read(notification_id)
