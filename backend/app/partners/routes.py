from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.errors import ApiError
from app.core.security import require_csrf, require_origin
from app.identity.dependencies import Database
from app.identity.models import User
from app.identity.operators import lock_operator_population
from app.identity.sessions import authenticate
from app.identity.tokens import lifecycle_lock
from app.partners.availability import get_partner_availability
from app.partners.invitations import issue_partner_invitation
from app.partners.lifecycle import (
    create_partner_organization,
    create_partner_recipient_membership,
    replace_partner_membership,
)
from app.partners.models import PartnerMembership, PartnerMembershipPermission
from app.partners.receipts import (
    CREATE_MEMBER,
    CREATE_ORG,
    INVITE_MEMBER,
    PATCH_MEMBER,
    authorize_request,
    run_lifecycle_command,
)
from app.partners.schemas import (
    PartnerAvailability,
    PartnerContextInput,
    PartnerInviteInput,
    PartnerInviteView,
    PartnerMembershipInput,
    PartnerMembershipReplace,
    PartnerMembershipView,
    PartnerOrganizationCreate,
    PartnerOrganizationView,
)

router = APIRouter()
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def response(result):
    return JSONResponse(status_code=result.status_code, content=result.body)


def member_view(db, member):
    return PartnerMembershipView(
        id=member.id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        active=member.active,
        blocked=member.blocked,
        invitation_pending=member.invitation_pending,
        version=member.version,
        permissions=list(
            db.scalars(
                select(PartnerMembershipPermission.code)
                .where(
                    PartnerMembershipPermission.membership_id == member.id,
                    PartnerMembershipPermission.active.is_(True),
                )
                .order_by(PartnerMembershipPermission.code)
            )
        ),
    )


def mutation_principal(db, request, target_user=None, membership_id=None):
    # Advisory locks precede every identity lock, including authenticate().
    lifecycle_lock(db)
    lock_operator_population(db)
    if membership_id is not None:
        target_user = db.scalar(
            select(PartnerMembership.user_id).where(
                PartnerMembership.id == membership_id
            )
        )
    return authorize_request(db, request, target_user)


@router.get("/partner/availability", response_model=PartnerAvailability)
def availability(request: Request, db: Database):
    principal, _, _ = authenticate(db, request)
    return get_partner_availability(db, principal)


@router.get("/partner/access-options", response_model=list)
def access_options(request: Request, db: Database):
    authenticate(db, request)
    return []


@router.post("/partner/contexts")
def contexts(payload: PartnerContextInput, request: Request, db: Database):
    require_origin(request)
    principal, _, session = authenticate(db, request)
    require_csrf(request, session.csrf_hash)
    if principal.platform_role is not None:
        raise ApiError(
            403,
            "PARTNER_CONTEXT_FORBIDDEN",
            "Operador interno não pode selecionar contexto parceiro.",
        )
    raise ApiError(503, "PARTNER_DOMAIN_UNAVAILABLE", "Domínio parceiro indisponível.")


@router.post(CREATE_ORG, response_model=PartnerOrganizationView, status_code=201)
def organization_create(
    payload: PartnerOrganizationCreate, request: Request, db: Database, key: Key
):
    principal = mutation_principal(db, request)
    return response(
        run_lifecycle_command(
            db,
            principal,
            CREATE_ORG,
            None,
            key,
            payload,
            lambda: PartnerOrganizationView.model_validate(
                create_partner_organization(db, principal, payload)
            ),
        )
    )


@router.post(
    "/platform/partners/organizations/{organization_id}/memberships",
    response_model=PartnerMembershipView,
    status_code=201,
)
def membership_create(
    organization_id: UUID,
    payload: PartnerMembershipInput,
    request: Request,
    db: Database,
    key: Key,
):
    lifecycle_lock(db)
    lock_operator_population(db)
    target_user = payload.user_id
    if payload.recipient is not None:
        target_user = db.scalar(
            select(User.id).where(User.email_normalized == payload.recipient.email)
        )
    principal = mutation_principal(db, request, target_user)
    return response(
        run_lifecycle_command(
            db,
            principal,
            CREATE_MEMBER,
            organization_id,
            key,
            payload,
            lambda: member_view(
                db,
                create_partner_recipient_membership(
                    db, principal, organization_id, payload
                ),
            ),
        )
    )


@router.patch(
    "/platform/partners/memberships/{membership_id}",
    response_model=PartnerMembershipView,
)
def membership_replace(
    membership_id: UUID,
    payload: PartnerMembershipReplace,
    request: Request,
    db: Database,
    key: Key,
):
    principal = mutation_principal(db, request, membership_id=membership_id)
    return response(
        run_lifecycle_command(
            db,
            principal,
            PATCH_MEMBER,
            membership_id,
            key,
            payload,
            lambda: member_view(
                db, replace_partner_membership(db, principal, membership_id, payload)
            ),
        )
    )


@router.post(
    "/platform/partners/memberships/{membership_id}/invite",
    response_model=PartnerInviteView,
    status_code=202,
)
def membership_invite(
    membership_id: UUID,
    payload: PartnerInviteInput,
    request: Request,
    db: Database,
    key: Key,
):
    principal = mutation_principal(db, request, membership_id=membership_id)

    def execute():
        issue_partner_invitation(db, principal, membership_id)
        member = db.get(PartnerMembership, membership_id, populate_existing=True)
        return PartnerInviteView(membership_id=member.id, version=member.version)

    return response(
        run_lifecycle_command(
            db, principal, INVITE_MEMBER, membership_id, key, payload, execute
        )
    )
