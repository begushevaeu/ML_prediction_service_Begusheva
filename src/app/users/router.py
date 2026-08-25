"""User API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, DbSession, require_roles
from app.db.models import User
from app.users.schemas import AdminCheckResponse, UserRead, UserUpdate
from app.users.service import ADMIN_ROLE, update_user, user_to_read

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead, summary="Get current user")
def get_me(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's public profile."""

    return user_to_read(current_user)


@router.patch("/me", response_model=UserRead, summary="Update current user")
def update_me(
    payload: UserUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> UserRead:
    """Update allowed profile fields for the authenticated user."""

    return user_to_read(update_user(current_user, payload, session))


@router.get(
    "/admin-check",
    response_model=AdminCheckResponse,
    summary="Check admin role",
)
def admin_check(
    current_user: Annotated[User, Depends(require_roles(ADMIN_ROLE))],
) -> AdminCheckResponse:
    """Small admin-only endpoint used to verify role enforcement."""

    return AdminCheckResponse(status="ok", role=current_user.role.name)


__all__ = ["router"]
