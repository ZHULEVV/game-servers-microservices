from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.dependencies import get_service
from app.errors import forbidden
from app.models.monitor import Alert, Monitor
from app.security import Principal, get_principal, require_owner_or_privileged
from app.services.monitor_service import MonitorService

router = APIRouter(tags=["Monitoring"])


class ThresholdsRequest(BaseModel):
    cpu: int
    ram: int


class SampleRequest(BaseModel):
    cpu: float
    ram: float


class AlertPage(BaseModel):
    items: list[Alert]
    offset: int
    count: int
    total: int


@router.get("/monitors/{booking_id}", response_model=Monitor)
def monitor_state(booking_id: UUID, who: Principal = Depends(get_principal), service: MonitorService = Depends(get_service)):
    monitor = service.get_monitor(booking_id)
    require_owner_or_privileged(who, monitor.user_id, "мониторинг")
    return monitor


@router.get("/monitors/{booking_id}/alerts", response_model=AlertPage)
def monitor_alerts(booking_id: UUID, offset: int = Query(default=0, ge=0), count: int = Query(default=20, ge=1, le=100),
                   who: Principal = Depends(get_principal), service: MonitorService = Depends(get_service)):
    require_owner_or_privileged(who, service.get_monitor(booking_id).user_id, "мониторинг")
    items, total = service.alerts(booking_id, offset, count)
    return AlertPage(items=items, offset=offset, count=count, total=total)


@router.put("/monitors/{booking_id}/thresholds", response_model=Monitor)
def set_thresholds(booking_id: UUID, body: ThresholdsRequest, who: Principal = Depends(get_principal),
                   service: MonitorService = Depends(get_service)):
    require_owner_or_privileged(who, service.get_monitor(booking_id).user_id, "мониторинг")
    return service.set_thresholds(booking_id, body.cpu, body.ram)


@router.post("/monitors/{booking_id}/samples", status_code=202)
def add_sample(booking_id: UUID, body: SampleRequest, who: Principal = Depends(get_principal), service: MonitorService = Depends(get_service)):
    if not who.privileged:
        raise forbidden("Метрики принимаются только от агента сервера")
    alerts = service.add_sample(booking_id, body.cpu, body.ram)
    return {"accepted": True, "alerts": len(alerts)}
