from sqlalchemy import Column, DateTime, Enum, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.server import ServerStatus
from app.schemas.base_schema import Base


class ServerDB(Base):
    __tablename__ = "servers"

    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String, nullable=False)
    game = Column(String, nullable=False, index=True)
    region = Column(String, nullable=False, index=True)
    slots = Column(Integer, nullable=False)
    price_per_hour = Column(Numeric(10, 2), nullable=False)
    rating = Column(Numeric(3, 2), nullable=True)
    rating_count = Column(Integer, nullable=False, default=0)
    provider_id = Column(UUID(as_uuid=True), nullable=False)
    status = Column(Enum(ServerStatus, name="server_status", values_callable=lambda e: [x.value for x in e]), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)


class ProcessedEventDB(Base):
    __tablename__ = "processed_events"

    event_id = Column(String, primary_key=True)
