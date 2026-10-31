from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import get_service
from app.errors import forbidden
from app.models.user import Role
from app.security import Principal, get_principal
from app.services.user_service import UserService

router = APIRouter(tags=["Users"])


class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    role: Role
    created_at: datetime


class LoginOut(BaseModel):
    token: str
    user_id: UUID
    role: Role
    expires_in: int = 3600


@router.post("/users", status_code=201, response_model=UserOut)
def create_user(body: CreateUserRequest, service: UserService = Depends(get_service)):
    return service.register(body.email, body.name, body.password)


@router.post("/users:login", response_model=LoginOut)
def login(body: LoginRequest, service: UserService = Depends(get_service)):
    token, user = service.login(body.email, body.password)
    return LoginOut(token=token, user_id=user.id, role=user.role)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: UUID, who: Principal = Depends(get_principal), service: UserService = Depends(get_service)):
    user = service.get_user(user_id)
    if not who.privileged and who.user_id != user_id:
        raise forbidden("Можно просматривать только свой профиль")
    return user
