from fastapi import Depends
from sqlalchemy.orm import Session

from app.clients.catalog_client import CatalogClient
from app.clients.payment_client import PaymentClient
from app.database import get_db
from app.events import RabbitPublisher
from app.repositories.db_booking_repo import DbBookingRepo
from app.services.booking_service import BookingService


def get_service(db: Session = Depends(get_db)) -> BookingService:
    return BookingService(DbBookingRepo(db), PaymentClient(), CatalogClient(), RabbitPublisher())
