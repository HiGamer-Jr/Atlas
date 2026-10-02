"""Fail-closed API gate and atomic observation boundary for support sessions."""

from datetime import timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import SESSION_COOKIE
from app.identity.models import User
from app.identity.sessions import session_candidate
from app.identity.tokens import lifecycle_lock
from app.support.models import SupportSession
from app.support.schemas import SupportDenialProvenance
from app.support.services import denied, lock_bound, terminal
from app.tenancy.contexts import now
from app.tenancy.models import AccessContext, Contract, Tenant


# Explicit endpoint metadata; no inference from an HTTP GET or URL naming.
def support_control(kind):
    def decorate(endpoint):
        endpoint.support_control = kind
        return endpoint

    return decorate


def parse_id(value):
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


def independent(db, request, candidate, supplied):
    if not supplied or not candidate:
        return False
    context = db.scalar(
        select(AccessContext).where(
            AccessContext.id == supplied,
            AccessContext.actor_id == candidate.user_id,
            AccessContext.session_id == candidate.id,
        )
    )
    valid_scope = context and db.scalar(
        select(Contract.id)
        .join(Tenant, Tenant.id == Contract.tenant_id)
        .where(
            Contract.id == context.contract_id,
            Contract.tenant_id == context.tenant_id,
            Contract.active.is_(True),
            Tenant.active.is_(True),
        )
    )
    valid_actor = candidate and db.scalar(
        select(User.id).where(
            User.id == candidate.user_id, User.active.is_(True), User.blocked.is_(False)
        )
    )
    clock = now(db)
    return bool(
        valid_scope
        and valid_actor
        and context
        and context.revoked_at is None
        and context.expires_at > clock
        and candidate.revoked_at is None
        and candidate.expires_at > clock
        and candidate.last_seen_at
        + timedelta(seconds=db.info["settings"].session_idle_seconds)
        > clock
        and not db.scalar(
            select(SupportSession.id).where(SupportSession.context_id == supplied)
        )
    )


def check_request(db, request):
    # Global lifecycle lock precedes route-specific population/identity locks.
    # Normal/unrelated requests acquire NO shared OPERATOR or identity row lock;
    # operator management is free to take its required exclusive lock first.
    lifecycle_lock(db)
    supplied = parse_id(request.headers.get("X-HiAtlas-Context"))
    candidate = session_candidate(db, request)
    bound = (
        list(
            db.scalars(
                select(SupportSession)
                .where(
                    or_(
                        SupportSession.context_id == supplied,
                        SupportSession.parent_context_id == supplied,
                    )
                )
                .order_by(SupportSession.started_at.desc())
            )
        )
        if supplied
        else []
    )
    selected = [r for r in bound if r.status == "ACTIVE" or r.context_id == supplied]
    if selected and (
        not candidate
        or any(
            r.operator_session_id != candidate.id or r.operator_id != candidate.user_id
            for r in selected
        )
    ):
        return denied()
    own = (
        list(
            db.scalars(
                select(SupportSession).where(
                    SupportSession.operator_session_id == candidate.id,
                    SupportSession.operator_id == candidate.user_id,
                    SupportSession.status == "ACTIVE",
                )
            )
        )
        if candidate
        else []
    )
    active = selected or own
    if not active:
        return None
    endpoint = request.scope.get("endpoint")
    control = getattr(endpoint, "support_control", None)
    target_context = parse_id(request.path_params.get("context_id"))
    target_active = any(
        r.parent_context_id == target_context or r.context_id == target_context
        for r in own
    )
    if (
        not selected
        and not target_active
        and independent(db, request, candidate, supplied)
    ):
        return None
    request.state.support_no_touch = True
    proven = active[0]
    contract = db.get(Contract, proven.contract_id)
    request.state.support_denial = SupportDenialProvenance(
        actor_id=proven.operator_id,
        actor_role=proven.operator_role,
        tenant_id=proven.tenant_id,
        contract_id=proven.contract_id,
        environment=contract.environment,
        support_session_id=proven.id,
    )
    for candidate_row in active:
        row, cause, *_ = lock_bound(db, candidate_row)
        if row.status == "ACTIVE" and cause:
            terminal(db, request, row, cause)
        if (row.status != "ACTIVE" or cause) and control not in {"end", "logout"}:
            return denied()
    # Own end binds the path session/context in the service. No other mutation
    # including auth recovery/context creation is treated as a safe control.
    if control in {"identity", "csrf", "logout"}:
        return None
    if control == "context" and selected:
        return None
    if control in {"read", "workspace", "end"} and selected:
        return None
    if (
        request.method == "GET"
        and control == "history"
        and selected
        and all(r.parent_context_id == supplied for r in selected)
    ):
        # History is a management read; suspended parent cannot query it.
        return ApiError(403, "SUPPORT_READ_ONLY", "Sessão de suporte somente leitura.")
    return ApiError(403, "SUPPORT_READ_ONLY", "Sessão de suporte somente leitura.")


def observe_request(request: Request):
    if not request.cookies.get(SESSION_COOKIE) and not request.headers.get(
        "X-HiAtlas-Context"
    ):
        return
    from app.db.session import validate_runtime_connection

    # Commit terminal state and audit BEFORE rejecting outside the transaction.
    with Session(request.app.state.database_engine) as db, db.begin():
        validate_runtime_connection(db.connection())
        db.info.update(
            clock=request.app.state.clock,
            settings=request.app.state.settings,
            request=request,
        )
        error = check_request(db, request)
    if error:
        raise error
