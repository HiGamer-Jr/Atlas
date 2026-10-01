"""Thin HTTP adapters; lifecycle transactions/policy live in the command service."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.identity.dependencies import Database
from app.identity.email_schemas import InviteInput, MembershipStatusInput
from app.platform.policy import require_capability
from app.tenancy import member_commands as commands
from app.tenancy.member_queries import list_members
from app.tenancy.schemas import ManagedMembershipView

router = APIRouter()


@router.post("/memberships", status_code=202)
def invite(payload: InviteInput, request: Request, db: Database):
    return commands.invite(payload, request, db)


@router.post("/memberships/{member_id}/invite", status_code=202)
def resend_invite(member_id: UUID, request: Request, db: Database):
    return commands.resend_invite(member_id, request, db)


@router.post("/memberships/{member_id}/reset-password", status_code=202)
def request_reset(member_id: UUID, request: Request, db: Database):
    return commands.request_reset(member_id, request, db)


@router.patch("/memberships/{member_id}/status", response_model=ManagedMembershipView)
def change_status(
    member_id: UUID, payload: MembershipStatusInput, request: Request, db: Database
):
    return commands.change_status(member_id, payload, request, db)


@router.get("/memberships")
def list_memberships(
    request: Request,
    db: Database,
    search: str = Query(default="", max_length=128),
    status: str | None = Query(
        default=None, pattern="^(ACTIVE|INACTIVE|BLOCKED|PENDING)$"
    ),
    role_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
):
    principal, scope = commands.context(db, request)
    require_capability(db, principal, scope, "memberships.read")
    return list_members(db, principal, scope, search, status, role_id, limit, offset)
