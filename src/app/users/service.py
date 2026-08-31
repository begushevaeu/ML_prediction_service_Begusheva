"""User domain helpers."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.core.config import Settings
from app.db.models import CreditBalance, Role, User
from app.users.schemas import UserCreate, UserRead, UserUpdate, normalize_email

DEFAULT_USER_ROLE = "user"
ADMIN_ROLE = "admin"
LOCAL_ADMIN_ENVS = {"local", "dev", "development"}
LOCAL_DEMO_USERS = (
    ("user1@example.com", "user12345", "Demo User 1"),
    ("user2@example.com", "user12345", "Demo User 2"),
    ("user3@example.com", "user12345", "Demo User 3"),
)


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


def _local_admin_enabled(settings: Settings | None) -> bool:
    if settings is None or not settings.bootstrap_local_admin:
        return False
    return settings.app_env.strip().lower() in LOCAL_ADMIN_ENVS


def _resolve_login_email(identifier: str, settings: Settings | None) -> str:
    if (
        _local_admin_enabled(settings)
        and identifier.strip().lower() == settings.local_admin_username.strip().lower()
    ):
        return settings.local_admin_email
    return identifier


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


def authenticate_user(
    session: Session,
    email: str,
    password: str,
    settings: Settings | None = None,
) -> User | None:
    """Return the user when credentials are valid."""

    try:
        user = get_user_by_email(session, _resolve_login_email(email, settings))
    except ValueError:
        return None

    if user is None or not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def ensure_local_admin_user(session: Session, settings: Settings) -> User | None:
    """Create or refresh the local admin account when explicitly enabled."""

    if not _local_admin_enabled(settings):
        return None

    admin_email = normalize_email(settings.local_admin_email)
    admin_role = ensure_role(session, ADMIN_ROLE, "Administrator")
    admin_user = session.scalar(select(User).where(User.email == admin_email))

    if admin_user is None:
        admin_user = User(
            email=admin_email,
            password_hash=hash_password(settings.local_admin_password),
            full_name="Local Admin",
            is_active=True,
            role=admin_role,
        )
        admin_user.credit_balance = CreditBalance(credits_available=0)
        session.add(admin_user)
    else:
        admin_user.password_hash = hash_password(settings.local_admin_password)
        admin_user.full_name = admin_user.full_name or "Local Admin"
        admin_user.is_active = True
        admin_user.role = admin_role
        if admin_user.credit_balance is None:
            admin_user.credit_balance = CreditBalance(credits_available=0)

    session.commit()
    session.refresh(admin_user)
    return admin_user


def ensure_local_demo_users(session: Session, settings: Settings) -> list[User]:
    """Create or refresh local demo user accounts when bootstrap is enabled."""

    if not _local_admin_enabled(settings):
        return []

    user_role = ensure_role(session, DEFAULT_USER_ROLE, "Default application user")
    demo_users: list[User] = []
    for email, password, full_name in LOCAL_DEMO_USERS:
        normalized_email = normalize_email(email)
        user = session.scalar(select(User).where(User.email == normalized_email))
        if user is None:
            user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                full_name=full_name,
                is_active=True,
                role=user_role,
            )
            user.credit_balance = CreditBalance(credits_available=0)
            session.add(user)
        else:
            user.password_hash = hash_password(password)
            user.full_name = user.full_name or full_name
            user.is_active = True
            user.role = user_role
            if user.credit_balance is None:
                user.credit_balance = CreditBalance(credits_available=0)
        demo_users.append(user)

    session.commit()
    for user in demo_users:
        session.refresh(user)
    return demo_users


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
    "ensure_local_admin_user",
    "ensure_local_demo_users",
    "ensure_role",
    "get_user_by_email",
    "update_user",
    "user_to_read",
]
