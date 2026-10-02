"""Support lifecycle and projections. Principal always remains the real operator."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text

from app.audit.schemas import AuditInput, SupportSessionSnapshot
from app.audit.service import append_event
from app.core.errors import ApiError
from app.core.security import require_csrf
from app.identity.models import AuthSession, PlatformRoleAssignment, User
from app.identity.operators import OPERATOR_LOCK
from app.identity.schemas import Principal
from app.identity.sessions import (
    authenticate,
    current_role,
    lock_users,
    session_candidate,
)
from app.platform.capabilities import CATALOG, INTERNAL_GRANTS
from app.support.models import SupportSession
from app.support.schemas import SupportHistoryView, SupportSessionView
from app.tenancy.contexts import contract_rows, now, permissions, revalidate
from app.tenancy.models import AccessContext, Contract, Membership, Tenant, TenantRole
from app.tenancy.schemas import AccessScope

# No operational read capability exists yet. A capability must opt in explicitly
# and bind a delivered module before it can enter a support workspace.
SUPPORT_READ_LIMITS = frozenset()
EXCLUDED_DOMAINS = frozenset(
    {
        "finance",
        "fiscal",
        "platform",
        "access",
        "audit",
        "diagnostics",
        "maintenance",
        "contract",
        "support",
    }
)


def denied():
    return ApiError(403, "SUPPORT_CONTEXT_INVALID", "Sessão de suporte indisponível.")


def snapshot(row):
    return SupportSessionSnapshot(
        **{key: getattr(row, key) for key in SupportSessionSnapshot.model_fields}
    )


def audit(db, request, row, action, before=None):
    append_event(
        db,
        AuditInput(
            actor_id=row.operator_id,
            actor_role=row.operator_role,
            tenant_id=row.tenant_id,
            contract_id=row.contract_id,
            entity_type="support_session",
            entity_id=row.id,
            support_session_id=row.id,
            action=action,
            before=before,
            after=snapshot(row),
            reason=row.reason,
            reference=row.reference,
            request_id=getattr(request.state, "request_id", uuid4()),
        ),
    )


def terminal(db, request, row, status):
    if row.status != "ACTIVE":
        return
    before = snapshot(row)
    row.status, row.ended_at = status, now(db)
    child = db.get(AccessContext, row.context_id, populate_existing=True)
    if child is not None and child.revoked_at is None:
        child.revoked_at = row.ended_at
    audit(
        db,
        request,
        row,
        "support.session."
        + {"ENDED": "ended", "EXPIRED": "expired", "REVOKED": "revoked"}[status],
        before,
    )


def lock_bound(db, row):
    # Before all identity locks; consistent with operator population mutations.
    db.execute(
        text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": OPERATOR_LOCK}
    )
    users = {u.id: u for u in lock_users(db, [row.operator_id, row.viewed_user_id])}
    session = db.scalar(
        select(AuthSession)
        .where(
            AuthSession.id == row.operator_session_id,
            AuthSession.user_id == row.operator_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    tenant, contract = contract_rows(db, row.contract_id)
    contexts = {
        c.id: c
        for c in db.scalars(
            select(AccessContext)
            .where(AccessContext.id.in_([row.parent_context_id, row.context_id]))
            .order_by(AccessContext.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    member = db.scalar(
        select(Membership)
        .where(
            Membership.id == row.viewed_membership_id,
            Membership.user_id == row.viewed_user_id,
            Membership.tenant_id == row.tenant_id,
            Membership.contract_id == row.contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    role = (
        db.scalar(
            select(TenantRole)
            .where(
                TenantRole.id == member.role_id,
                TenantRole.tenant_id == row.tenant_id,
                TenantRole.contract_id == row.contract_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if member
        else None
    )
    row = db.scalar(
        select(SupportSession)
        .where(SupportSession.id == row.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    clock = now(db)  # Fresh after every lock; waiting can cross any deadline.
    parent, child = contexts.get(row.parent_context_id), contexts.get(row.context_id)
    operator, viewed = users.get(row.operator_id), users.get(row.viewed_user_id)
    idle = db.info["settings"].session_idle_seconds
    invalid_identity = (
        not operator
        or not operator.active
        or operator.blocked
        or not session
        or session.revoked_at is not None
        or current_role(db, row.operator_id) != row.operator_role
        or row.operator_role not in INTERNAL_GRANTS
    )
    expired = (
        clock >= row.expires_at
        or (
            session
            and (
                clock >= session.expires_at
                or clock >= session.last_seen_at + timedelta(seconds=idle)
            )
        )
        or (parent and parent.expires_at <= clock)
        or (child and child.expires_at <= clock)
    )
    invalid = (
        invalid_identity
        or not tenant.active
        or not contract.active
        or not viewed
        or not viewed.active
        or viewed.blocked
        or db.get(PlatformRoleAssignment, row.viewed_user_id) is not None
        or not member
        or not member.active
        or member.blocked
        or member.invitation_pending
        or not role
        or not role.active
        or not parent
        or parent.revoked_at is not None
        or not child
        or child.revoked_at is not None
    )
    return row, "REVOKED" if invalid else "EXPIRED" if expired else None, member, role


def support_for_context(db, context_id, active_only=False):
    query = select(SupportSession).where(
        or_(
            SupportSession.context_id == context_id,
            SupportSession.parent_context_id == context_id,
        )
    )
    if active_only:
        query = query.where(SupportSession.status == "ACTIVE")
    return db.scalar(
        query.order_by(
            SupportSession.started_at.desc(), SupportSession.id.desc()
        ).limit(1)
    )


def validate_bound(db, principal, row, *, allow_terminal=False):
    if (
        row.operator_id != principal.user_id
        or row.operator_session_id != principal.session_id
    ):
        raise denied()
    row, cause, member, role = lock_bound(db, row)
    if (row.status != "ACTIVE" or cause) and not allow_terminal:
        raise denied()
    return row, cause, member, role


def target_eligible(db, member, role, user):
    return bool(
        member
        and role
        and user
        and member.active
        and not member.blocked
        and not member.invitation_pending
        and role.active
        and user.active
        and not user.blocked
        and db.get(PlatformRoleAssignment, user.id) is None
    )


def start(db, request, payload):
    candidate = session_candidate(db, request)
    if candidate is None:
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    # Resolve exact target scope before locks without trusting client identity.
    try:
        parent_id = UUID(request.headers.get("X-HiAtlas-Context", ""))
    except ValueError:
        raise denied() from None
    parent = db.scalar(
        select(AccessContext).where(
            AccessContext.id == parent_id,
            AccessContext.actor_id == candidate.user_id,
            AccessContext.session_id == candidate.id,
        )
    )
    if parent is None:
        raise denied()
    member = db.scalar(
        select(Membership).where(
            Membership.id == payload.membership_id,
            Membership.tenant_id == parent.tenant_id,
            Membership.contract_id == parent.contract_id,
        )
    )
    if member is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    db.execute(
        text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": OPERATOR_LOCK}
    )
    lock_users(db, [candidate.user_id, member.user_id])
    principal, _, auth = authenticate(db, request, touch=False)
    require_csrf(request, auth.csrf_hash)
    if "support.session.start" not in INTERNAL_GRANTS.get(principal.platform_role, ()):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")
    scope = AccessScope(
        parent.id,
        parent.tenant_id,
        parent.contract_id,
        principal.session_id,
        principal.user_id,
    )
    revalidate(db, principal, scope)
    if support_for_context(db, parent.id, active_only=True) or db.scalar(
        select(SupportSession.id).where(SupportSession.context_id == parent.id)
    ):
        raise denied()
    member = db.scalar(
        select(Membership)
        .where(
            Membership.id == member.id,
            Membership.tenant_id == parent.tenant_id,
            Membership.contract_id == parent.contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    role = db.scalar(
        select(TenantRole)
        .where(
            TenantRole.id == member.role_id,
            TenantRole.tenant_id == parent.tenant_id,
            TenantRole.contract_id == parent.contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    user = db.get(User, member.user_id, populate_existing=True)
    if not target_eligible(db, member, role, user):
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    principal, parent, *_ = revalidate(db, principal, scope)
    clock = now(db)
    expiry = min(
        clock + timedelta(seconds=db.info["settings"].support_session_seconds),
        auth.expires_at,
        auth.last_seen_at + timedelta(seconds=db.info["settings"].session_idle_seconds),
        parent.expires_at,
    )
    child = AccessContext(
        session_id=principal.session_id,
        actor_id=principal.user_id,
        tenant_id=parent.tenant_id,
        contract_id=parent.contract_id,
        created_at=clock,
        expires_at=expiry,
    )
    db.add(child)
    db.flush()
    row = SupportSession(
        operator_id=principal.user_id,
        operator_session_id=principal.session_id,
        operator_role=principal.platform_role,
        tenant_id=parent.tenant_id,
        contract_id=parent.contract_id,
        parent_context_id=parent.id,
        context_id=child.id,
        viewed_membership_id=member.id,
        viewed_user_id=member.user_id,
        mode="READ_ONLY",
        reason=payload.reason,
        reference=payload.reference,
        started_at=clock,
        expires_at=expiry,
        status="ACTIVE",
    )
    db.add(row)
    db.flush()
    audit(db, request, row, "support.session.started")
    return project(db, row)


def owned(db, request, session_id):
    candidate = session_candidate(db, request)
    row = db.scalar(select(SupportSession).where(SupportSession.id == session_id))
    if (
        not candidate
        or not row
        or candidate.id != row.operator_session_id
        or candidate.user_id != row.operator_id
    ):
        raise denied()
    try:
        context_id = UUID(request.headers.get("X-HiAtlas-Context", ""))
    except ValueError:
        raise denied() from None
    if context_id not in {row.parent_context_id, row.context_id}:
        raise denied()
    return row, Principal(
        candidate.user_id, candidate.id, current_role(db, candidate.user_id)
    )


def read(db, request, session_id):
    row, principal = owned(db, request, session_id)
    row, *_ = validate_bound(db, principal, row)
    return project(db, row)


def end(db, request, session_id):
    row, principal = owned(db, request, session_id)
    # Exact authenticated HTTP owner plus CSRF remains mandatory for controls.
    _, _, auth = authenticate(db, request, touch=False)
    require_csrf(request, auth.csrf_hash)
    if row.status == "ACTIVE":
        row, cause, *_ = validate_bound(db, principal, row, allow_terminal=True)
        terminal(db, request, row, cause or "ENDED")


def project(db, row, history=False):
    operator = db.get(User, row.operator_id)
    viewed = db.get(User, row.viewed_user_id)
    member = db.get(Membership, row.viewed_membership_id)
    role = db.get(TenantRole, member.role_id)
    tenant = db.get(Tenant, row.tenant_id)
    contract = db.get(Contract, row.contract_id)
    data = {
        key: getattr(row, key)
        for key in (
            "id",
            "tenant_id",
            "contract_id",
            "mode",
            "reason",
            "reference",
            "started_at",
            "expires_at",
            "ended_at",
            "status",
        )
    }
    data.update(
        tenant_name=tenant.name,
        contract_code=contract.code,
        environment=contract.environment,
        operator={
            "user_id": operator.id,
            "display_name": operator.display_name,
            "platform_role": row.operator_role,
        },
        viewed={
            "membership_id": member.id,
            "user_id": viewed.id,
            "display_name": viewed.display_name,
            "role_id": role.id,
            "role_name": role.name,
        },
    )
    if history:
        return SupportHistoryView(**data)
    return SupportSessionView(
        **data, context_id=row.context_id, parent_context_id=row.parent_context_id
    )


def history(db, request, scope, limit, offset):
    principal = request.state.principal
    fresh, *_ = revalidate(db, principal, scope)
    if "support.history.read" not in INTERNAL_GRANTS.get(
        fresh.platform_role, ()
    ) or db.scalar(
        select(SupportSession.id).where(SupportSession.context_id == scope.id)
    ):
        raise denied()
    query = select(SupportSession).where(
        SupportSession.tenant_id == scope.tenant_id,
        SupportSession.contract_id == scope.contract_id,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(SupportSession.started_at.desc(), SupportSession.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return {
        "items": [project(db, row, history=True) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def effective_access(db, principal, row):
    from app.organization.models import ContractModule
    from app.organization.modules import OPERATIONAL_MODULES

    row, _, _, role = validate_bound(db, principal, row)
    target = permissions(db, role)
    enabled = {
        module.code
        for module in db.scalars(
            select(ContractModule)
            .where(
                ContractModule.tenant_id == row.tenant_id,
                ContractModule.contract_id == row.contract_id,
                ContractModule.active.is_(True),
                ContractModule.contracted.is_(True),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    result = {
        code
        for code in target & SUPPORT_READ_LIMITS
        if code in CATALOG
        and CATALOG[code].tenant_enabled
        and CATALOG[code].read_only_safe
        and not CATALOG[code].mutates_business_state
        and not CATALOG[code].sensitive
        and CATALOG[code].domain not in EXCLUDED_DOMAINS
        and CATALOG[code].module_code in enabled & OPERATIONAL_MODULES
    }
    validate_bound(db, principal, row)
    return result


def workspace(db, request, session_id):
    from app.organization.models import ContractModule
    from app.organization.modules import CONTRACT_MODULE_CATALOG, OPERATIONAL_MODULES

    row, principal = owned(db, request, session_id)
    capabilities = effective_access(db, principal, row)
    rows = {
        m.code: m
        for m in db.scalars(
            select(ContractModule)
            .where(
                ContractModule.tenant_id == row.tenant_id,
                ContractModule.contract_id == row.contract_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    validate_bound(db, principal, row)
    return {
        "effective_access": {"read_only": True, "capabilities": sorted(capabilities)},
        "modules": [
            {
                "code": code,
                "label": label,
                "contracted": bool(rows.get(code) and rows[code].contracted),
                "active": bool(rows.get(code) and rows[code].active),
                "enabled": bool(
                    rows.get(code) and rows[code].contracted and rows[code].active
                ),
                "operational_available": code in OPERATIONAL_MODULES,
            }
            for code, label in CONTRACT_MODULE_CATALOG.items()
            if code != "FINANCE"
        ],
    }


def revoke_owned(db, request, *, session_id=None, user_id=None):
    query = select(SupportSession).where(SupportSession.status == "ACTIVE")
    query = (
        query.where(SupportSession.operator_session_id == session_id)
        if session_id
        else query.where(
            or_(
                SupportSession.operator_id == user_id,
                SupportSession.viewed_user_id == user_id,
            )
        )
    )
    for row in db.scalars(
        query.order_by(SupportSession.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ):
        terminal(db, request, row, "REVOKED")


def record_denial(db, request, provenance, code):
    from app.audit.models import AccessEvent
    from app.support.schemas import SupportDenialEvent

    event = SupportDenialEvent(
        **provenance.model_dump(), request_id=request.state.request_id, reason=code
    )
    db.add(
        AccessEvent(
            **event.model_dump(),
            action="support.session.denied",
            outcome="DENIED",
            entity_type="support_session",
            entity_id=provenance.support_session_id,
        )
    )
    db.flush()
