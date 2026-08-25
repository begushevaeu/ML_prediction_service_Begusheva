"""Authentication and authorization dependencies."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.tokens import TokenError, decode_access_token
from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def unauthorized_exception() -> HTTPException:
    """Build a consistent unauthenticated response."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve the authenticated active user from a bearer token."""

    try:
        payload = decode_access_token(token, settings)
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError, TokenError) as exc:
        raise unauthorized_exception() from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active or user.role is None:
        raise unauthorized_exception()

    return user


def require_roles(*role_names: str) -> Callable[[User], User]:
    """Create a dependency that allows only users with specific roles."""

    allowed_roles = set(role_names)

    def dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role.name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db_session)]

__all__ = [
    "CurrentUser",
    "DbSession",
    "get_current_user",
    "oauth2_scheme",
    "require_roles",
    "unauthorized_exception",
]
