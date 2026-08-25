"""User domain helpers."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.db.models import CreditBalance, Role, User
from app.users.schemas import UserCreate, UserRead, UserUpdate, normalize_email

DEFAULT_USER_ROLE = "user"
ADMIN_ROLE = "admin"


class DuplicateUserError(ValueError):
    """Raised when registration tries to reuse an email address."""


def ensure_role(session: Session, name: str, description: str | None = None) -> Role:
    """Return an existing role or create it."""

    normalized_name = name.strip().lower()
    role = session.scalar(select(Role).where(Role.name == normalized_name))
    if role is not None:
        return role

    role = Role(name=normalized_name, description=description)
    session.add(role)
    session.flush()
    return role


def get_user_by_email(session: Session, email: str) -> User | None:
    """Find a user by normalized email address."""

    return session.scalar(select(User).where(User.email == normalize_email(email)))


def create_user(session: Session, payload: UserCreate) -> User:
    """Create a default-role user and an empty credit balance."""

    if get_user_by_email(session, payload.email) is not None:
        raise DuplicateUserError(payload.email)

    role = ensure_role(session, DEFAULT_USER_ROLE, "Default application user")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
    )
    user.credit_balance = CreditBalance(credits_available=0)
    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateUserError(payload.email) from exc

    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Return the user when credentials are valid."""

    user = get_user_by_email(session, email)
    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def update_user(user: User, payload: UserUpdate, session: Session) -> User:
    """Update fields the current user is allowed to manage."""

    if "full_name" in payload.model_fields_set:
        user.full_name = payload.full_name

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def user_to_read(user: User) -> UserRead:
    """Convert a database user to the public API shape."""

    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.name,
        is_active=user.is_active,
    )


__all__ = [
    "ADMIN_ROLE",
    "DEFAULT_USER_ROLE",
    "DuplicateUserError",
    "authenticate_user",
    "create_user",
    "ensure_role",
    "get_user_by_email",
    "update_user",
    "user_to_read",
]
