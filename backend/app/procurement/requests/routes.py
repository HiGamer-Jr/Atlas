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


@router.patch("/{request_id}/draft", response_model=RequestView)
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


@router.post("/{request_id}/assignment", response_model=RequestView)
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


@router.post("/{request_id}/attachments", response_model=RequestView)
async def add_attachment(
    request_id: UUID,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
    key: Key,
):
    from pydantic import ValidationError
    from starlette.concurrency import run_in_threadpool
    from starlette.datastructures import UploadFile
    from starlette.exceptions import HTTPException
    from starlette.requests import Request as MultipartRequest

    from app.core.errors import ApiError
    from app.procurement.requests import attachments

    private(response)
    await run_in_threadpool(
        attachments.prepare_upload, db, request.state.principal, scope, request_id, key
    )
    # Read a bounded body before multipart parsing; Content-Length is never trusted.
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > attachments.MAX_BODY_BYTES:
            raise attachments.too_large()
        body.extend(chunk)

    async def receive():
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    multipart = MultipartRequest(request.scope, receive)
    try:
        async with multipart.form(
            max_files=1, max_fields=2, max_part_size=1024
        ) as form:
            fields = form.multi_items()
            names = [name for name, _ in fields]
            if (
                set(names) - {"file", "expected_version", "item_id"}
                or len(names) != len(set(names))
                or "file" not in names
                or "expected_version" not in names
            ):
                raise ApiError(422, "VALIDATION_ERROR", "Campos de anexo inválidos.")
            uploaded = form["file"]
            if (
                not isinstance(uploaded, UploadFile)
                or isinstance(form["expected_version"], UploadFile)
                or isinstance(form.get("item_id"), UploadFile)
            ):
                raise attachments.invalid_file()
            try:
                version_text = form["expected_version"]
                if not version_text.isascii() or not version_text.isdecimal():
                    raise ValueError()
                version = VersionCommand(
                    expected_version=int(version_text)
                ).expected_version
                item_id = UUID(form["item_id"]) if form.get("item_id") else None
            except (ValueError, ValidationError) as error:
                raise ApiError(
                    422, "VALIDATION_ERROR", "Versão ou item inválido."
                ) from error
            content = bytearray()
            while chunk := await uploaded.read(65536):
                if len(content) + len(chunk) > attachments.MAX_BYTES:
                    raise attachments.too_large()
                content.extend(chunk)
            validated = await run_in_threadpool(
                attachments.validate_attachment, bytes(content), uploaded.filename or ""
            )
            if uploaded.content_type != validated.media_type:
                raise attachments.invalid_file()
            return await run_in_threadpool(
                attachments.add_attachment,
                db,
                request,
                request.state.principal,
                scope,
                request_id,
                version,
                item_id,
                uploaded.filename or "",
                bytes(content),
                key,
            )
    except HTTPException as error:
        raise ApiError(422, "VALIDATION_ERROR", "Multipart inválido.") from error


@router.get("/{request_id}/attachments/{attachment_id}/download")
def download_attachment(
    request_id: UUID,
    attachment_id: UUID,
    request: Request,
    db: Database,
    scope: Context,
):
    from urllib.parse import quote

    from app.procurement.requests import attachments

    result = attachments.download_attachment(
        db, request.state.principal, scope, request_id, attachment_id
    )
    name = attachments.sanitize_filename(result.filename)
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(name, safe=""),
        },
    )


@router.delete("/{request_id}/attachments/{attachment_id}", response_model=RequestView)
def remove_attachment(
    request_id: UUID,
    attachment_id: UUID,
    payload: VersionCommand,
    request: Request,
    response: Response,
    db: Database,
    scope: Context,
):
    from app.procurement.requests import attachments

    private(response)
    return attachments.remove_draft_attachment(
        db,
        request,
        request.state.principal,
        scope,
        request_id,
        attachment_id,
        payload.expected_version,
    )
