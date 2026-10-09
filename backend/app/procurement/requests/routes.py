"""Authenticated private reads for purchase needs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.identity.dependencies import Database
from app.procurement.requests import queries
from app.procurement.requests.schemas import (
    BuyerCandidatePage,
    RequestFilters,
    RequestHistoryPage,
    RequestPage,
    RequestView,
)
from app.tenancy.dependencies import Context

router = APIRouter(prefix="/procurement/requests", tags=["purchase-requests"])


def private(response):
    response.headers["Cache-Control"] = "no-store"


@router.get("", response_model=RequestPage)
def list_requests(
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    filters: Annotated[RequestFilters, Query()],
):
    private(response)
    return queries.list_requests(db, request.state.principal, scope, filters)


@router.get("/buyer-candidates", response_model=BuyerCandidatePage)
def buyer_candidates(
    requesting_node_id: UUID,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
):
    private(response)
    return queries.buyer_candidates(
        db, request.state.principal, scope, requesting_node_id, limit, cursor
    )


@router.get("/{request_id}", response_model=RequestView)
def get_request(
    request_id: UUID, request: Request, response: Response, db: Database, scope: Context
):
    private(response)
    return queries.get_request(db, request.state.principal, scope, request_id)


@router.get("/{request_id}/history", response_model=RequestHistoryPage)
def request_history(
    request_id: UUID,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=2048),
):
    private(response)
    return queries.request_history(
        db, request.state.principal, scope, request_id, limit, cursor
    )
