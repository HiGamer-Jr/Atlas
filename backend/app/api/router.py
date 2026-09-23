from fastapi import APIRouter

from app.identity.routes import router as identity_router
from app.platform.routes import router as platform_router
from app.tenancy.routes import router as tenancy_router

router = APIRouter()
router.include_router(identity_router)

router.include_router(tenancy_router)
router.include_router(platform_router)


@router.get("/health")
def health():
    return {"status": "ok"}
