from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.events import RabbitPublisher
from app.repositories.db_user_repo import DbUserRepo
from app.services.user_service import UserService


def get_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(DbUserRepo(db), RabbitPublisher("user.events"))
