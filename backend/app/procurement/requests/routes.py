"""Authenticated private reads for purchase needs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from app.identity.dependencies import Database
from app.platform.policy import require_capability
from app.procurement.requests import assignment, commands, fulfillment, queries
from app.procurement.requests.approval_policy import (
    effective_approval_policy,
    patch_approval_policy,
)
from app.procurement.requests.command_schemas import (
    ApprovalPolicyPatch,
    AssignmentCommand,
    DraftPatch,
    FulfillmentCommand,
    NoteCommand,
    ReasonCommand,
    RequestCreate,
    VersionCommand,
)
from app.procurement.requests.schemas import (
    ApprovalPolicyView,
    BuyerCandidatePage,
    RequestFilters,
    RequestHistoryPage,
    RequestPage,
    RequestView,
)
from app.tenancy.dependencies import Context
from app.tenancy.schemas import AccessScope

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


Key = Annotated[UUID, Header(alias="Idempotency-Key")]
policy_router = APIRouter(
    prefix="/contract/purchase-request-policy", tags=["purchase-requests"]
)


@policy_router.get("", response_model=ApprovalPolicyView)
def get_policy(request: Request, response: Response, db: Database, scope: Context):
    private(response)
    require_capability(db, request.state.principal, scope, "modules.read")
    result = effective_approval_policy(db, scope)
    require_capability(db, request.state.principal, scope, "modules.read")
    return result


@policy_router.patch("", response_model=ApprovalPolicyView)
def patch_policy(
    payload: ApprovalPolicyPatch,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
):
    private(response)
    return patch_approval_policy(db, request, request.state.principal, scope, payload)


@router.post("", response_model=RequestView, status_code=201)
def create_request(
    payload: RequestCreate,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    key: Key,
):
    private(response)
    return commands.create_request(
        db, request, request.state.principal, scope, payload, key
    )


@router.patch("/{request_id}", response_model=RequestView)
def update_draft(
    request_id: UUID,
    payload: DraftPatch,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
):
    private(response)
    return commands.update_draft(
        db, request, request.state.principal, scope, request_id, payload
    )


def require_assignment_context(
    payload: AssignmentCommand, request: Request, db: Database
):
    return assignment.assignment_context(db, request, payload.buyer_membership_id)


@router.post("/{request_id}/assign", response_model=RequestView)
def assign_buyer(
    request_id: UUID,
    payload: AssignmentCommand,
    request: Request,
    response: Response,
    db: Database,
    key: Key,
    scope: Annotated[AccessScope, Depends(require_assignment_context)],
):
    private(response)
    return commands.assign_buyer(
        db, request, request.state.principal, scope, request_id, payload, key
    )


@router.post("/{request_id}/notes", response_model=RequestView)
def add_note(
    request_id: UUID,
    payload: NoteCommand,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    key: Key,
):
    private(response)
    return commands.add_note(
        db, request, request.state.principal, scope, request_id, payload, key
    )


@router.post("/{request_id}/submit", response_model=RequestView)
def submit_request(
    request_id: UUID,
    payload: ReasonCommand | VersionCommand,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    key: Key,
):
    private(response)
    return commands.transition_request(
        db, request, request.state.principal, scope, request_id, "submit", payload, key
    )


def version_transition(command):
    def endpoint(
        request_id: UUID,
        payload: VersionCommand,
        request: Request,
        response: Response,
        db: Database,
        scope: Context,
        key: Key,
    ):
        private(response)
        return commands.transition_request(
            db,
            request,
            request.state.principal,
            scope,
            request_id,
            command,
            payload,
            key,
        )

    return endpoint


def reason_transition(command):
    def endpoint(
        request_id: UUID,
        payload: ReasonCommand,
        request: Request,
        response: Response,
        db: Database,
        scope: Context,
        key: Key,
    ):
        private(response)
        return commands.transition_request(
            db,
            request,
            request.state.principal,
            scope,
            request_id,
            command,
            payload,
            key,
        )

    return endpoint


for action in (
    "start-triage",
    "request-approval",
    "approve",
    "start-fulfillment",
    "close",
):
    router.add_api_route(
        "/{request_id}/" + action,
        version_transition(action),
        methods=["POST"],
        response_model=RequestView,
    )
for action in ("reject", "cancel"):
    router.add_api_route(
        "/{request_id}/" + action,
        reason_transition(action),
        methods=["POST"],
        response_model=RequestView,
    )


@router.post("/{request_id}/fulfillments", response_model=RequestView)
def record_fulfillment(
    request_id: UUID,
    payload: FulfillmentCommand,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    key: Key,
):
    private(response)
    return fulfillment.record_fulfillment(
        db, request, request.state.principal, scope, request_id, payload, key
    )


@router.post(
    "/{request_id}/fulfillments/{entry_id}/reverse", response_model=RequestView
)
def reverse_fulfillment(
    request_id: UUID,
    entry_id: UUID,
    payload: ReasonCommand,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    key: Key,
):
    private(response)
    return fulfillment.reverse_fulfillment(
        db, request, request.state.principal, scope, request_id, entry_id, payload, key
    )
