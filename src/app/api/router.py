"""Top-level API router."""

from fastapi import APIRouter

from app.admin.router import router as admin_router
from app.api.health import router as health_router
from app.auth.router import router as auth_router
from app.billing.router import router as billing_router
from app.ml.router import router as models_router
from app.payments.router import router as payments_router
from app.predictions.router import router as predictions_router
from app.promo_codes.router import router as promo_codes_router
from app.users.router import router as users_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(billing_router)
api_router.include_router(health_router)
api_router.include_router(models_router)
api_router.include_router(payments_router)
api_router.include_router(predictions_router)
api_router.include_router(promo_codes_router)
api_router.include_router(users_router)

__all__ = ["api_router"]
