from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.grants import services
from app.grants.gate import grant_control
from app.grants.schemas import (
    GrantEnd,
    GrantHistoryPage,
    GrantStart,
    GrantView,
    MaintenanceActions,
)
from app.identity.dependencies import Database

router = APIRouter()


@router.post("/grants", status_code=201, response_model=GrantView)
def start(payload: GrantStart, request: Request, db: Database):
    return services.start(db, request, payload)


@router.get("/grants", response_model=GrantHistoryPage)
def history(
    request: Request,
    db: Database,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
):
    return services.history(db, request, limit, offset)


@router.get("/grants/context", response_model=GrantView)
@grant_control("read")
def read_context(request: Request, db: Database):
    return services.read_context(db, request)


@router.get("/grants/maintenance-actions", response_model=MaintenanceActions)
def maintenance_actions(request: Request, db: Database):
    services.normal_admin(db, request, "maintenance.authorize")
    return {
        "items": [
            {
                "action_code": a.action_code,
                "label": a.label,
                "entity_type": a.entity_type,
            }
            for a in request.app.state.maintenance_registry.list()
        ]
    }


@router.post("/grants/{grant_id}/end", response_model=GrantView)
@grant_control("end")
def end(grant_id: UUID, payload: GrantEnd, request: Request, db: Database):
    return services.end(db, request, grant_id, payload.expected_version)
