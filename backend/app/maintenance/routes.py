from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.core.errors import ApiError
from app.identity.dependencies import Database
from app.maintenance import corrections, processing
from app.maintenance.schemas import (
    CorrectionResult,
    ProcessingPage,
    ProcessingView,
    ReprocessCommand,
)
from app.support.gate import support_control
from app.tenancy.dependencies import Context

router = APIRouter()


def maintenance_control(endpoint):
    endpoint.maintenance_control = True
    return endpoint


@router.get("/maintenance")
@maintenance_control
def catalog(request: Request, db: Database, scope: Context):
    return corrections.catalog(db, request, request.state.principal, scope)


@router.get("/maintenance/entities/{action_code}/{entity_id}")
@maintenance_control
def entity(
    action_code: str, entity_id: UUID, request: Request, db: Database, scope: Context
):
    return corrections.entity_view(
        db, request, request.state.principal, scope, action_code, entity_id
    )


@router.post("/maintenance/preview")
@maintenance_control
async def preview(request: Request, db: Database, scope: Context):
    try:
        payload = await request.json()
    except ValueError:
        raise ApiError(422, "VALIDATION_ERROR", "Dados inválidos.") from None
    action, cmd = corrections.command(request, payload)
    return corrections.preview_correction(
        db, request, request.state.principal, scope, action, cmd
    )


@router.post("/maintenance/corrections", response_model=CorrectionResult)
@maintenance_control
async def apply(request: Request, db: Database, scope: Context):
    try:
        payload = await request.json()
    except ValueError:
        raise ApiError(422, "VALIDATION_ERROR", "Dados inválidos.") from None
    action, cmd = corrections.command(request, payload, apply=True)
    return corrections.apply_correction(
        db, request, request.state.principal, scope, action, cmd
    )


@router.get("/processings", response_model=ProcessingPage)
@support_control("read")
@maintenance_control
def processings(
    request: Request,
    db: Database,
    scope: Context,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
):
    return processing.list_runs(
        db, request, request.state.principal, scope, limit, offset
    )


@router.get("/processings/{run_id}", response_model=ProcessingView)
@support_control("read")
@maintenance_control
def processing_detail(run_id: UUID, request: Request, db: Database, scope: Context):
    return processing.detail(db, request, request.state.principal, scope, run_id)


@router.post("/processings/{run_id}/reprocess", response_model=ProcessingView)
@maintenance_control
def reprocess(
    run_id: UUID,
    payload: ReprocessCommand,
    request: Request,
    db: Database,
    scope: Context,
):
    return processing.request_reprocess(
        db, request, request.state.principal, scope, run_id, payload
    )
