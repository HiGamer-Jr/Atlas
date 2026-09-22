from fastapi import APIRouter

from app.identity.routes import router as identity_router

router = APIRouter()
router.include_router(identity_router)


@router.get("/health")
def health():
    return {"status": "ok"}
