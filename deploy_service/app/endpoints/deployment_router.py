from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel

from app.dependencies import get_service
from app.errors import forbidden
from app.models.deployment import Deployment
from app.runner import run_deployment
from app.security import Principal, get_principal, require_owner_or_privileged
from app.services.deployment_service import DeploymentService

router = APIRouter(tags=["Deployments"])


class StartRequest(BaseModel):
    booking_id: UUID


class StartResponse(BaseModel):
    operation_id: UUID
    deployment_id: UUID


class OperationOut(BaseModel):
    id: UUID
    is_finished: bool
    result: dict | None = None


class DeploymentOut(BaseModel):
    id: UUID
    booking_id: UUID
    status: str
    ip: str | None
    port: int | None
    started_at: str
    finished_at: str | None


def to_out(dep: Deployment) -> DeploymentOut:
    return DeploymentOut(id=dep.id, booking_id=dep.booking_id, status=dep.status.value, ip=dep.ip, port=dep.port,
                         started_at=dep.started_at.isoformat().replace("+00:00", "Z"),
                         finished_at=dep.finished_at.isoformat().replace("+00:00", "Z") if dep.finished_at else None)


@router.post("/deployments", status_code=202, response_model=StartResponse)
def start_deployment(body: StartRequest, background: BackgroundTasks, who: Principal = Depends(get_principal),
                     service: DeploymentService = Depends(get_service)):
    if not who.privileged:
        raise forbidden("Развёртывание запускает система или администратор")
    dep, op = service.start_for_booking(body.booking_id)
    background.add_task(run_deployment, dep.id)
    return StartResponse(operation_id=op.id, deployment_id=dep.id)


@router.get("/operations/{operation_id}", response_model=OperationOut)
def get_operation(operation_id: UUID, who: Principal = Depends(get_principal), service: DeploymentService = Depends(get_service)):
    op = service.get_operation(operation_id)
    require_owner_or_privileged(who, service.get_deployment(op.deployment_id).user_id, "операция")
    return OperationOut(id=op.id, is_finished=op.is_finished, result=op.result)


@router.get("/deployments/{deployment_id}", response_model=DeploymentOut)
def get_deployment(deployment_id: UUID, who: Principal = Depends(get_principal), service: DeploymentService = Depends(get_service)):
    dep = service.get_deployment(deployment_id)
    require_owner_or_privileged(who, dep.user_id, "развёртывание")
    return to_out(dep)


@router.post("/deployments/{deployment_id}:stop", response_model=DeploymentOut)
def stop_deployment(deployment_id: UUID, who: Principal = Depends(get_principal), service: DeploymentService = Depends(get_service)):
    require_owner_or_privileged(who, service.get_deployment(deployment_id).user_id, "развёртывание")
    return to_out(service.stop(deployment_id))
