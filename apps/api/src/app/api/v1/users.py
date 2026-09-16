from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, EmailStr

from app.api.deps import CurrentUser, DbSession, SuperAdministrator
from app.models import User
from app.repositories.users import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    is_active: bool
    mfa_enabled: bool
    created_at: datetime
    roles: list[str]


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        mfa_enabled=user.mfa_enabled,
        created_at=user.created_at,
        roles=sorted(role.name for role in user.roles),
    )


@router.get("/me", response_model=UserResponse)
def current_user(user: CurrentUser) -> UserResponse:
    return user_response(user)


@router.get("", response_model=list[UserResponse])
def list_users(session: DbSession, _: SuperAdministrator) -> list[UserResponse]:
    return [user_response(user) for user in UserRepository(session).list_users()]
