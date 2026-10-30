from fastapi import Depends
from sqlalchemy.orm import Session

from app.clients.gateway import FakeGateway
from app.database import get_db
from app.events import RabbitPublisher
from app.repositories.db_payment_repo import DbPaymentRepo
from app.services.payment_service import PaymentService
from app.settings import settings


def get_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(DbPaymentRepo(db), FakeGateway(settings.gateway_limit), RabbitPublisher())
