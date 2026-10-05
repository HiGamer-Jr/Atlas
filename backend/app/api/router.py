from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.audit.routes import router as audit_router
from app.db.base import Base
from app.db.session import validate_runtime_connection
from app.grants.routes import router as grant_router
from app.identity.access_routes import router as access_router
from app.identity.routes import router as identity_router
from app.maintenance.routes import router as maintenance_router
from app.organization.routes import router as organization_router
from app.platform.routes import router as platform_router
from app.support.routes import router as support_router
from app.tenancy.memberships import router as membership_router
from app.tenancy.routes import router as tenancy_router

router = APIRouter()
router.include_router(grant_router)
router.include_router(maintenance_router)
router.include_router(support_router)
router.include_router(identity_router)
router.include_router(access_router)
router.include_router(membership_router)

router.include_router(tenancy_router)
router.include_router(platform_router)
router.include_router(audit_router)
router.include_router(organization_router)


@router.get("/health")
def health():
    return {"status": "ok"}


def validate_readiness(engine):
    with engine.connect() as connection:
        validate_runtime_connection(connection)
        for table in Base.metadata.tables.values():
            connection.execute(select(table).limit(0))


@router.get("/health/live")
def liveness():
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(request: Request):
    try:
        validate_readiness(request.app.state.database_engine)
    except (SQLAlchemyError, ValueError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
