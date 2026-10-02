from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.identity.dependencies import Database
from app.support import services
from app.support.gate import support_control
from app.support.schemas import (
    SupportHistoryPage,
    SupportSessionView,
    SupportStart,
    SupportWorkspace,
)
from app.tenancy.dependencies import Context

router = APIRouter()


@router.post("/support-sessions", status_code=201, response_model=SupportSessionView)
def start(payload: SupportStart, request: Request, db: Database):
    return services.start(db, request, payload)


@router.get("/support-sessions", response_model=SupportHistoryPage)
@support_control("history")
def history(
    request: Request,
    db: Database,
    scope: Context,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
):
    return services.history(db, request, scope, limit, offset)


@router.get("/support-sessions/{session_id}", response_model=SupportSessionView)
@support_control("read")
def read(session_id: UUID, request: Request, db: Database):
    return services.read(db, request, session_id)


@router.post("/support-sessions/{session_id}/end", status_code=204)
@support_control("end")
def end(session_id: UUID, request: Request, db: Database):
    services.end(db, request, session_id)
    return Response(status_code=204)


@router.get("/support-sessions/{session_id}/workspace", response_model=SupportWorkspace)
@support_control("workspace")
def workspace(session_id: UUID, request: Request, db: Database):
    return services.workspace(db, request, session_id)
