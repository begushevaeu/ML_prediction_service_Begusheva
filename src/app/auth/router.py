"""Authentication API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import CurrentUser, DbSession
from app.auth.schemas import TokenResponse
from app.auth.tokens import create_access_token
from app.core.config import Settings, get_settings
from app.users.schemas import UserCreate, UserRead
from app.users.service import DuplicateUserError, authenticate_user, create_user, user_to_read

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register_user(payload: UserCreate, session: DbSession) -> UserRead:
    """Create a user account with the default user role."""

    try:
        user = create_user(session, payload)
    except DuplicateUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        ) from exc

    return user_to_read(user)


@router.post("/login", response_model=TokenResponse, summary="Log in and receive JWT")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Authenticate by email/password and return a bearer token."""

    user = authenticate_user(session, email=form_data.username, password=form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(str(user.id), settings))


@router.post("/logout", summary="Log out from a stateless JWT session")
def logout(current_user: CurrentUser) -> dict[str, str]:
    """Return the client-side logout strategy for stateless JWT tokens."""

    return {
        "status": "ok",
        "user": current_user.email,
        "strategy": "discard bearer token on the client",
    }


__all__ = ["router"]
