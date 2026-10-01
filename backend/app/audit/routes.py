from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.audit import queries
from app.identity.dependencies import Database
from app.tenancy.dependencies import Context

router = APIRouter()


@router.get("/audit")
def audit_list(
    request: Request,
    db: Database,
    scope: Context,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
    action: str | None = Query(default=None, max_length=100),
    outcome: str | None = Query(default=None, pattern="^(SUCCESS|DENIED|FAILURE)$"),
    from_at: datetime | None = None,
    to_at: datetime | None = None,
):
    return queries.list_events(
        db,
        request.state.principal,
        scope,
        limit,
        cursor,
        action,
        outcome,
        from_at,
        to_at,
    )


@router.get("/audit/{event_id}")
def audit_detail(event_id: UUID, request: Request, db: Database, scope: Context):
    return queries.event_detail(db, request.state.principal, scope, event_id)


@router.get("/memberships/{member_id}/access-history")
def access_history(
    member_id: UUID,
    request: Request,
    db: Database,
    scope: Context,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
    action: str | None = Query(default=None, max_length=100),
    outcome: str | None = Query(default=None, pattern="^(SUCCESS|DENIED|FAILURE)$"),
    from_at: datetime | None = None,
    to_at: datetime | None = None,
):
    return queries.list_events(
        db,
        request.state.principal,
        scope,
        limit,
        cursor,
        action,
        outcome,
        from_at,
        to_at,
        member_id,
    )
