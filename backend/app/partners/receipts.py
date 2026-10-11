"""Current authorization precedes receipt lookup; caller owns outer commit."""

import json
from collections.abc import Callable
from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import require_csrf, require_origin
from app.identity.operators import lock_operator_population
from app.identity.schemas import Principal
from app.identity.sessions import authenticate, lock_users, session_candidate
from app.identity.tokens import lifecycle_lock
from app.partners.lifecycle import organization_lock, revalidate
from app.partners.models import (
    PartnerLifecycleReceipt,
    PartnerMembership,
    PartnerOrganization,
)

CREATE_ORG = "/platform/partners/organizations"
CREATE_MEMBER = "/platform/partners/organizations/{id}/memberships"
PATCH_MEMBER = "/platform/partners/memberships/{id}"
INVITE_MEMBER = "/platform/partners/memberships/{id}/invite"
CAPABILITIES = {
    CREATE_ORG: "partners.organizations.manage",
    CREATE_MEMBER: "partners.memberships.manage",
    PATCH_MEMBER: "partners.memberships.manage",
    INVITE_MEMBER: "partners.memberships.manage",
}
STATUS = {CREATE_ORG: 201, CREATE_MEMBER: 201, PATCH_MEMBER: 200, INVITE_MEMBER: 202}


class LifecycleCommandResult(BaseModel):
    status_code: int
    body: dict


def authorize_request(db, request, target_user=None):
    require_origin(request)
    lifecycle_lock(db)
    lock_operator_population(db)
    candidate = session_candidate(db, request)
    if candidate is None:
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    lock_users(db, [candidate.user_id] + ([target_user] if target_user else []))
    principal, _, session = authenticate(db, request, touch=False)
    require_csrf(request, session.csrf_hash)
    if principal.platform_role != "PLATFORM_ADMIN":
        raise ApiError(
            403, "PLATFORM_ADMIN_REQUIRED", "Operação restrita à administração HiAtlas."
        )
    if (
        session.reauthenticated_at is None
        or request.app.state.clock()
        >= session.reauthenticated_at + timedelta(minutes=5)
    ):
        raise ApiError(403, "REAUTH_REQUIRED", "Confirme sua senha novamente.")
    return principal


def lock_target(db, route, target_id):
    if route == CREATE_ORG:
        if target_id is not None:
            raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
        return
    if route == CREATE_MEMBER:
        organization_lock(db, target_id)
        return
    candidate = db.scalar(
        select(PartnerMembership).where(PartnerMembership.id == target_id)
    )
    if candidate is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    organization_lock(db, candidate.organization_id)
    db.scalar(
        select(PartnerMembership)
        .where(PartnerMembership.id == target_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def revalidate_response(db, route, target_id, body):
    if route == CREATE_ORG:
        row = db.get(PartnerOrganization, UUID(body["id"]), populate_existing=True)
    else:
        identifier = body["membership_id"] if route == INVITE_MEMBER else body["id"]
        row = db.get(PartnerMembership, UUID(identifier), populate_existing=True)
        if row is not None and (
            route == CREATE_MEMBER
            and row.organization_id != target_id
            or route in {PATCH_MEMBER, INVITE_MEMBER}
            and row.id != target_id
            or route != INVITE_MEMBER
            and (
                str(row.user_id) != body["user_id"]
                or str(row.organization_id) != body["organization_id"]
            )
        ):
            row = None
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")


def run_lifecycle_command(
    db: Session,
    principal: Principal,
    route: str,
    target_id: UUID | None,
    key: UUID,
    payload: BaseModel,
    execute: Callable[[], BaseModel],
) -> LifecycleCommandResult:
    if route not in CAPABILITIES:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    request = db.info.get("request")
    if request is None:
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    with db.begin_nested():
        current = authorize_request(db, request)
        if (current.user_id, current.session_id) != (
            principal.user_id,
            principal.session_id,
        ):
            raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
        lock_target(db, route, target_id)
        # A lock wait can cross idle expiry, role revocation or the reauthentication window.
        current = authorize_request(db, request)
        revalidate(db, current, CAPABILITIES[route])
        digest = sha256(
            json.dumps(
                payload.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        receipt = db.scalar(
            select(PartnerLifecycleReceipt).where(
                PartnerLifecycleReceipt.user_id == current.user_id,
                PartnerLifecycleReceipt.session_id == current.session_id,
                PartnerLifecycleReceipt.route == route,
                PartnerLifecycleReceipt.target_id == target_id,
                PartnerLifecycleReceipt.key == key,
            )
        )
        if receipt is not None:
            if receipt.digest != digest:
                raise ApiError(
                    409,
                    "IDEMPOTENCY_CONFLICT",
                    "A chave já foi usada com outro conteúdo.",
                )
            revalidate_response(db, route, target_id, receipt.response_json)
            authorize_request(db, request)
            return LifecycleCommandResult(
                status_code=receipt.status_code, body=receipt.response_json
            )
        body = execute().model_dump(mode="json")
        authorize_request(db, request)
        revalidate(db, current, CAPABILITIES[route])
        db.add(
            PartnerLifecycleReceipt(
                user_id=current.user_id,
                session_id=current.session_id,
                route=route,
                target_id=target_id,
                key=key,
                digest=digest,
                response_json=body,
                status_code=STATUS[route],
            )
        )
        db.flush()
        return LifecycleCommandResult(status_code=STATUS[route], body=body)
