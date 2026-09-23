from datetime import timedelta

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError

from app.audit.schemas import (
    AuditInput,
    ContextSnapshot,
    ContractSnapshot,
    TenantSnapshot,
)
from app.audit.service import append_event
from app.core.errors import ApiError
from app.identity.models import User
from app.identity.sessions import authenticate
from app.platform.policy import (
    effective_capabilities,
    require_capability,
    require_global,
)
from app.tenancy.contexts import contract_rows, membership_role, now, revalidate
from app.tenancy.models import AccessContext, Contract, Membership, Tenant, TenantRole
from app.tenancy.schemas import (
    AccessScope,
    ContextView,
    ContractView,
    MembershipView,
    TenantView,
)


def audit(
    db,
    request,
    principal,
    action,
    entity_type,
    entity_id,
    before=None,
    after=None,
    scope=None,
):
    append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role=principal.platform_role,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            tenant_id=scope.tenant_id if scope else None,
            contract_id=scope.contract_id if scope else None,
            request_id=request.state.request_id,
        ),
    )


def list_contracts(db, principal, search, limit, offset):
    query = (
        select(Contract, Tenant.name)
        .join(Tenant, Tenant.id == Contract.tenant_id)
        .where(Contract.active.is_(True), Tenant.active.is_(True))
    )
    if principal.platform_role is None:
        permitted = exists(
            select(Membership.id)
            .join(TenantRole, TenantRole.id == Membership.role_id)
            .where(
                Membership.user_id == principal.user_id,
                Membership.contract_id == Contract.id,
                Membership.tenant_id == Contract.tenant_id,
                Membership.active.is_(True),
                Membership.blocked.is_(False),
                TenantRole.active.is_(True),
            )
        )
        query = query.where(permitted)
    if search:
        user_query = (
            select(Membership.id)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.contract_id == Contract.id,
                Membership.tenant_id == Contract.tenant_id,
                User.email_normalized.contains(search.lower(), autoescape=True),
            )
        )
        if principal.platform_role is None:
            user_query = user_query.where(User.id == principal.user_id)
        query = query.where(
            or_(
                Tenant.name.icontains(search, autoescape=True),
                Contract.code.icontains(search, autoescape=True),
                exists(user_query),
            )
        )
    rows = db.execute(
        query.order_by(Contract.code, Contract.id).limit(limit).offset(offset)
    )
    return {
        "items": [
            ContractView(
                id=c.id,
                tenant_id=c.tenant_id,
                tenant_name=n,
                name=c.name,
                code=c.code,
                environment=c.environment,
            )
            for c, n in rows
        ]
    }


def create_tenant(db, request, principal, payload):
    require_global(principal, "tenants.create")
    tenant = Tenant(name=payload.name)
    db.add(tenant)
    db.flush()
    audit(
        db,
        request,
        principal,
        "tenant.created",
        "tenant",
        tenant.id,
        after=TenantSnapshot(name=tenant.name, active=tenant.active),
    )
    return TenantView(id=tenant.id, name=tenant.name)


def create_contract(db, request, principal, tenant_id, payload):
    require_global(principal, "contracts.create")
    tenant = db.scalar(
        select(Tenant)
        .where(Tenant.id == tenant_id, Tenant.active.is_(True))
        .with_for_update(read=True)
    )
    if tenant is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    principal, _, _ = authenticate(db, request, touch=False)
    require_global(principal, "contracts.create")
    contract = Contract(tenant_id=tenant.id, **payload.model_dump())
    db.add(contract)
    try:
        db.flush()
    except IntegrityError:
        raise ApiError(409, "CONFLICT", "Contrato não pôde ser criado.") from None
    scope = AccessScope(
        contract.id, tenant.id, contract.id, principal.session_id, principal.user_id
    )
    audit(
        db,
        request,
        principal,
        "contract.created",
        "contract",
        contract.id,
        after=ContractSnapshot(
            tenant_id=tenant.id,
            name=contract.name,
            code=contract.code,
            environment=contract.environment,
            active=contract.active,
        ),
        scope=scope,
    )
    return ContractView(
        id=contract.id,
        tenant_id=tenant.id,
        tenant_name=tenant.name,
        name=contract.name,
        code=contract.code,
        environment=contract.environment,
    )


def select_context(db, request, principal, contract_id):
    tenant, contract = contract_rows(db, contract_id)
    if not tenant.active or not contract.active:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    if principal.platform_role is None:
        _, role = membership_role(db, principal.user_id, tenant.id, contract.id)
        if role is None:
            raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    principal, _, session = authenticate(db, request, touch=False)
    clock = now(db)
    context = AccessContext(
        session_id=principal.session_id,
        actor_id=principal.user_id,
        tenant_id=tenant.id,
        contract_id=contract.id,
        created_at=clock,
        expires_at=min(
            session.expires_at,
            clock + timedelta(seconds=request.app.state.settings.context_seconds),
        ),
    )
    db.add(context)
    db.flush()
    scope = AccessScope(
        context.id, tenant.id, contract.id, principal.session_id, principal.user_id
    )
    audit(
        db,
        request,
        principal,
        "context.selected",
        "access_context",
        context.id,
        after=ContextSnapshot(revoked=False),
        scope=scope,
    )
    return context_view(db, principal, scope)


def context_view(db, principal, scope):
    _, context, tenant, contract, _ = revalidate(db, principal, scope)
    return ContextView(
        id=context.id,
        tenant_id=tenant.id,
        contract_id=contract.id,
        tenant_name=tenant.name,
        contract_name=contract.name,
        contract_code=contract.code,
        environment=contract.environment,
        expires_at=context.expires_at,
        capabilities=sorted(effective_capabilities(db, principal, scope)),
    )


def close_context(db, request, principal, context_id):
    query = select(AccessContext).where(
        AccessContext.id == context_id,
        AccessContext.session_id == principal.session_id,
        AccessContext.actor_id == principal.user_id,
    )
    candidate = db.scalar(query)
    if candidate is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    contract_rows(db, candidate.contract_id)
    context = db.scalar(
        query.with_for_update().execution_options(populate_existing=True)
    )
    if context is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    principal, _, _ = authenticate(db, request, touch=False)
    if context.revoked_at is None:
        context.revoked_at = now(db)
        scope = AccessScope(
            context.id,
            context.tenant_id,
            context.contract_id,
            context.session_id,
            context.actor_id,
        )
        audit(
            db,
            request,
            principal,
            "context.closed",
            "access_context",
            context.id,
            before=ContextSnapshot(revoked=False),
            after=ContextSnapshot(revoked=True),
            scope=scope,
        )


def get_membership(db, principal, scope, member_id):
    require_capability(db, principal, scope, "memberships.read")
    member = db.scalar(
        select(Membership).where(
            Membership.id == member_id,
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
        )
    )
    if member is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    return MembershipView(
        id=member.id,
        user_id=member.user_id,
        role_id=member.role_id,
        active=member.active,
        blocked=member.blocked,
        version=member.version,
    )
