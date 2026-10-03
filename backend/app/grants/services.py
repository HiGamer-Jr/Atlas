"""Transactional privileged authorization; no impersonation or operational handlers."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, text

from app.audit.schemas import AuditInput, PrivilegedGrantSnapshot
from app.audit.service import append_event
from app.core.errors import ApiError
from app.core.security import require_csrf
from app.grants.models import MaintenanceGrantScope, TemporaryPrivilegedGrant
from app.grants.schemas import GrantHistoryView, GrantView, MaintenanceScope
from app.identity.models import AuthSession, User
from app.identity.operators import OPERATOR_LOCK
from app.identity.sessions import (
    authenticate,
    current_role,
    lock_users,
    session_candidate,
)
from app.platform.capabilities import CATALOG, INTERNAL_GRANTS
from app.tenancy.contexts import contract_rows, now, resolve_context, revalidate
from app.tenancy.models import AccessContext, Contract, Tenant

FINANCIAL_CAPABILITIES = frozenset({"finance.read", "fiscal.read"})


def denied():
    return ApiError(403, "GRANT_CONTEXT_INVALID", "Acesso temporário indisponível.")


def scopes_for(db, row):
    return [
        MaintenanceScope(
            action_code=s.action_code, entity_type=s.entity_type, entity_id=s.entity_id
        )
        for s in db.scalars(
            select(MaintenanceGrantScope)
            .where(MaintenanceGrantScope.grant_id == row.id)
            .order_by(MaintenanceGrantScope.action_code)
        )
    ]


def snapshot(db, row):
    return PrivilegedGrantSnapshot(
        operator_id=row.operator_id,
        operator_role=row.operator_role,
        grant_type=row.grant_type,
        status=row.status,
        started_at=row.started_at,
        expires_at=row.expires_at,
        ended_at=row.ended_at,
        revoked_at=row.revoked_at,
        version=row.version,
        scopes=[scope.model_dump(mode="json") for scope in scopes_for(db, row)],
    )


def audit(db, request, row, action, before=None):
    append_event(
        db,
        AuditInput(
            actor_id=row.operator_id,
            actor_role=row.operator_role,
            tenant_id=row.tenant_id,
            contract_id=row.contract_id,
            entity_type="privileged_grant",
            entity_id=row.id,
            action=action,
            before=before,
            after=snapshot(db, row),
            reason=row.reason,
            reference=row.reference,
            request_id=getattr(request.state, "request_id", uuid4()),
        ),
    )


def terminal(db, request, row, status):
    if row.status != "ACTIVE":
        return
    before = snapshot(db, row)
    clock = now(db)
    row.status = status
    row.ended_at = row.updated_at = clock
    row.revoked_at = clock if status == "REVOKED" else None
    row.version += 1
    child = db.get(AccessContext, row.context_id, populate_existing=True)
    if child and child.revoked_at is None:
        child.revoked_at = clock
    audit(
        db,
        request,
        row,
        "privileged_grant."
        + {"ENDED": "ended", "EXPIRED": "expired", "REVOKED": "revoked"}[status],
        before,
    )


def lock_bound(db, row):
    db.execute(
        text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": OPERATOR_LOCK}
    )
    users = lock_users(db, [row.operator_id])
    auth = db.scalar(
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
        ctx.id: ctx
        for ctx in db.scalars(
            select(AccessContext)
            .where(AccessContext.id.in_([row.parent_context_id, row.context_id]))
            .order_by(AccessContext.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    }
    row = db.scalar(
        select(TemporaryPrivilegedGrant)
        .where(TemporaryPrivilegedGrant.id == row.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    clock = now(db)
    parent, child = contexts.get(row.parent_context_id), contexts.get(row.context_id)
    operator = users[0] if users else None
    invalid = (
        not operator
        or not operator.active
        or operator.blocked
        or not auth
        or auth.revoked_at is not None
        or current_role(db, row.operator_id) != "PLATFORM_ADMIN"
        or not tenant.active
        or not contract.active
        or not parent
        or parent.revoked_at is not None
        or not child
        or child.revoked_at is not None
    )
    expired = (
        clock >= row.expires_at
        or (
            auth
            and (
                auth.expires_at <= clock
                or auth.last_seen_at
                + timedelta(seconds=db.info["settings"].session_idle_seconds)
                <= clock
            )
        )
        or (parent and parent.expires_at <= clock)
        or (child and child.expires_at <= clock)
    )
    return row, "REVOKED" if invalid else "EXPIRED" if expired else None


def validate_bound(db, principal, row):
    if (
        row.operator_id != principal.user_id
        or row.operator_session_id != principal.session_id
        or principal.platform_role != "PLATFORM_ADMIN"
    ):
        raise denied()
    row, cause = lock_bound(db, row)
    if row.status != "ACTIVE" or cause:
        raise denied()
    return row


def normal_admin(db, request, capability="grants.request"):
    db.execute(
        text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": OPERATOR_LOCK}
    )
    principal, _, auth = authenticate(db, request, touch=False)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_csrf(request, auth.csrf_hash)
    scope = resolve_context(db, request, principal)
    principal, parent, *_ = revalidate(db, principal, scope)
    if principal.platform_role != "PLATFORM_ADMIN":
        raise ApiError(
            403, "PLATFORM_ADMIN_REQUIRED", "Operação restrita à administração HiAtlas."
        )
    if capability not in INTERNAL_GRANTS.get(principal.platform_role, ()):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")
    from app.support.services import support_for_context

    if support_for_context(db, parent.id, active_only=True) or db.scalar(
        select(TemporaryPrivilegedGrant.id).where(
            TemporaryPrivilegedGrant.context_id == parent.id
        )
    ):
        raise denied()
    return principal, scope, parent, auth


def require_control(principal, capability):
    if capability not in INTERNAL_GRANTS.get(principal.platform_role, ()):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")


def recent(db, auth):
    clock = now(db)
    if (
        auth.reauthenticated_at is None
        or auth.reauthenticated_at > clock
        or auth.reauthenticated_at
        + timedelta(seconds=db.info["settings"].reauthentication_seconds)
        <= clock
    ):
        raise ApiError(403, "REAUTH_REQUIRED", "Confirme sua senha novamente.")


def validate_scopes(db, request, principal, scope, payload):
    registry = request.app.state.maintenance_registry
    for value in payload.scopes:
        action = registry.get(value.action_code)
        if action.entity_type != value.entity_type or not action.resolve_entity(
            db, scope, value.entity_id
        ):
            raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
        if not action.authorize_domain(db, principal, scope, value.entity_id):
            raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")


def start(db, request, payload):
    principal, scope, parent, auth = normal_admin(db, request)
    recent(db, auth)
    if (
        payload.grant_type == "MAINTENANCE"
        and "maintenance.authorize"
        not in INTERNAL_GRANTS.get(principal.platform_role, ())
    ):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")
    validate_scopes(db, request, principal, scope, payload)
    principal, parent, *_ = revalidate(db, principal, scope)
    recent(db, auth)  # Re-check after all registry/domain locks.
    if principal.platform_role != "PLATFORM_ADMIN":
        raise denied()
    require_control(principal, "grants.request")
    if payload.grant_type == "MAINTENANCE":
        require_control(principal, "maintenance.authorize")
    previous = db.scalar(
        select(TemporaryPrivilegedGrant).where(
            TemporaryPrivilegedGrant.parent_context_id == parent.id,
            TemporaryPrivilegedGrant.status == "ACTIVE",
        )
    )
    if previous:
        previous, cause = lock_bound(db, previous)
        if cause:
            terminal(db, request, previous, cause)
            db.flush()
        elif previous.status == "ACTIVE":
            raise ApiError(
                409,
                "GRANT_ALREADY_ACTIVE",
                "Já existe um acesso temporário neste contexto.",
            )
    clock = now(db)
    expiry = min(
        clock + timedelta(seconds=db.info["settings"].grant_seconds),
        auth.expires_at,
        auth.last_seen_at + timedelta(seconds=db.info["settings"].session_idle_seconds),
        parent.expires_at,
    )
    if expiry <= clock:
        raise denied()
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
    row = TemporaryPrivilegedGrant(
        operator_id=principal.user_id,
        operator_session_id=principal.session_id,
        operator_role=principal.platform_role,
        tenant_id=parent.tenant_id,
        contract_id=parent.contract_id,
        parent_context_id=parent.id,
        context_id=child.id,
        grant_type=payload.grant_type,
        status="ACTIVE",
        reason=payload.reason,
        reference=payload.reference,
        started_at=clock,
        expires_at=expiry,
        created_at=clock,
        updated_at=clock,
        version=1,
    )
    db.add(row)
    db.flush()
    for value in payload.scopes:
        db.add(
            MaintenanceGrantScope(
                grant_id=row.id,
                tenant_id=row.tenant_id,
                contract_id=row.contract_id,
                **value.model_dump(),
            )
        )
    db.flush()
    audit(db, request, row, "privileged_grant.started")
    return project(db, row)


def owned(db, request, grant_id=None):
    candidate = session_candidate(db, request)
    try:
        context_id = UUID(request.headers.get("X-HiAtlas-Context", ""))
    except ValueError:
        raise denied() from None
    query = select(TemporaryPrivilegedGrant)
    query = (
        query.where(TemporaryPrivilegedGrant.id == grant_id)
        if grant_id
        else query.where(TemporaryPrivilegedGrant.context_id == context_id)
    )
    row = db.scalar(query)
    if (
        not candidate
        or not row
        or row.operator_id != candidate.user_id
        or row.operator_session_id != candidate.id
        or context_id not in {row.context_id, row.parent_context_id}
    ):
        raise denied()
    principal, _, auth = authenticate(db, request, touch=False)
    if principal.platform_role != "PLATFORM_ADMIN":
        raise denied()
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_csrf(request, auth.csrf_hash)
    return row, principal


def read_context(db, request):
    row, principal = owned(db, request)
    require_control(principal, "grants.read")
    validate_bound(db, principal, row)
    return project(db, row)


def end(db, request, grant_id, expected_version):
    row, principal = owned(db, request, grant_id)
    require_control(principal, "grants.end")
    row, cause = lock_bound(db, row)
    if row.status != "ACTIVE":
        return project(db, row)
    if row.version != expected_version:
        raise ApiError(
            409,
            "VERSION_CONFLICT",
            "Este registro foi alterado enquanto você o editava.",
        )
    terminal(db, request, row, cause or "ENDED")
    return project(db, row)


def project(db, row, history=False):
    operator = db.get(User, row.operator_id)
    tenant, contract = db.get(Tenant, row.tenant_id), db.get(Contract, row.contract_id)
    data = {
        key: getattr(row, key)
        for key in (
            "id",
            "tenant_id",
            "contract_id",
            "grant_type",
            "status",
            "reason",
            "reference",
            "started_at",
            "expires_at",
            "ended_at",
            "revoked_at",
            "version",
        )
    }
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.astimezone(UTC)
    data.update(
        tenant_name=tenant.name,
        contract_code=contract.code,
        environment=contract.environment,
        operator={
            "user_id": operator.id,
            "display_name": operator.display_name,
            "platform_role": row.operator_role,
        },
        scopes=scopes_for(db, row),
    )
    if history:
        return GrantHistoryView(**data)
    return GrantView(
        **data, context_id=row.context_id, parent_context_id=row.parent_context_id
    )


def history(db, request, limit, offset):
    _, scope, _, _ = normal_admin(db, request, "grants.read")
    query = select(TemporaryPrivilegedGrant).where(
        TemporaryPrivilegedGrant.tenant_id == scope.tenant_id,
        TemporaryPrivilegedGrant.contract_id == scope.contract_id,
    )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(
            TemporaryPrivilegedGrant.started_at.desc(),
            TemporaryPrivilegedGrant.id.desc(),
        )
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
    validate_bound(db, principal, row)
    if row.grant_type != "FINANCIAL_FISCAL":
        return set()
    return {code for code in FINANCIAL_CAPABILITIES if code in CATALOG}


def require_maintenance(
    db, request, principal, scope, action_code, entity_type, entity_id=None
):
    row = db.scalar(
        select(TemporaryPrivilegedGrant).where(
            TemporaryPrivilegedGrant.context_id == scope.id
        )
    )
    if row is None or row.grant_type != "MAINTENANCE":
        raise denied()
    if (
        scope.actor_id != row.operator_id
        or scope.session_id != row.operator_session_id
        or scope.tenant_id != row.tenant_id
        or scope.contract_id != row.contract_id
    ):
        raise denied()
    validate_bound(db, principal, row)
    action = request.app.state.maintenance_registry.get(action_code)
    allowed = any(
        s.action_code == action_code
        and s.entity_type == entity_type
        and s.entity_id == entity_id
        for s in scopes_for(db, row)
    )
    if (
        not allowed
        or action.entity_type != entity_type
        or not action.resolve_entity(db, scope, entity_id)
        or not action.authorize_domain(db, principal, scope, entity_id)
    ):
        raise denied()
    if action.handler is None:
        raise ApiError(
            403,
            "MAINTENANCE_HANDLER_UNAVAILABLE",
            "Operação de manutenção indisponível.",
        )
    # Registered domain handlers must enforce their own optimistic version and business integrity.
    # Maintenance capabilities are never injected as a blanket set into context RBAC.
    if action.capability not in INTERNAL_GRANTS.get(principal.platform_role, ()):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")
    require_module(db, principal, scope, action.module_code)
    validate_bound(db, principal, row)
    return action


def require_module(db, principal, scope, code):
    from app.organization.models import ContractModule
    from app.organization.modules import CONTRACT_MODULE_CATALOG, OPERATIONAL_MODULES

    if code not in CONTRACT_MODULE_CATALOG:
        raise denied()
    module = db.scalar(
        select(ContractModule)
        .where(
            ContractModule.tenant_id == scope.tenant_id,
            ContractModule.contract_id == scope.contract_id,
            ContractModule.code == code,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    row = db.scalar(
        select(TemporaryPrivilegedGrant).where(
            TemporaryPrivilegedGrant.context_id == scope.id
        )
    )
    validate_bound(db, principal, row)
    if (
        not module
        or not module.active
        or not module.contracted
        or code not in OPERATIONAL_MODULES
    ):
        raise ApiError(
            403, "MODULE_UNAVAILABLE", "Módulo operacional ainda indisponível."
        )


def revoke_owned(db, request, *, session_id=None, user_id=None):
    query = select(TemporaryPrivilegedGrant).where(
        TemporaryPrivilegedGrant.status == "ACTIVE"
    )
    query = (
        query.where(TemporaryPrivilegedGrant.operator_session_id == session_id)
        if session_id
        else query.where(TemporaryPrivilegedGrant.operator_id == user_id)
    )
    for row in db.scalars(
        query.order_by(TemporaryPrivilegedGrant.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ):
        terminal(db, request, row, "REVOKED")
