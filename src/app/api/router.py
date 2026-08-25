"""Top-level API router."""

from fastapi import APIRouter

from app.api.health import router as health_router
from app.auth.router import router as auth_router
from app.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(users_router)

__all__ = ["api_router"]
