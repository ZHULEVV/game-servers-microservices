from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.events import RabbitPublisher
from app.repositories.db_server_repo import DbServerRepo
from app.services.server_service import ServerService


def get_service(db: Session = Depends(get_db)) -> ServerService:
    return ServerService(DbServerRepo(db), RabbitPublisher("catalog.events"))
