from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.db_notification_repo import DbNotificationRepo
from app.services.notification_service import NotificationService


def get_service(db: Session = Depends(get_db)) -> NotificationService:
    return NotificationService(DbNotificationRepo(db))
