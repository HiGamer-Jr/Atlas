"""Contextual member projections: no identity-wide state, credential, or token payload."""

from sqlalchemy import exists, func, or_, select

from app.core.errors import ApiError
from app.identity.models import EmailOutbox, PlatformRoleAssignment, SecurityToken, User
from app.platform.policy import (
    effective_capabilities,
    role_sensitive,
    safe_role_predicate,
)
from app.tenancy.contexts import now, permissions
from app.tenancy.models import Membership, TenantRole
from app.tenancy.schemas import ManagedMembershipView


def visible_query(scope, principal):
    query = (
        select(Membership)
        .join(TenantRole, TenantRole.id == Membership.role_id)
        .where(
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
            ~exists().where(PlatformRoleAssignment.user_id == Membership.user_id),
        )
    )
    if principal.platform_role == "PLATFORM_SUPPORT":
        query = query.where(safe_role_predicate())
    return query


def read_member(db, principal, scope, member_id):
    member = db.scalar(
        visible_query(scope, principal).where(Membership.id == member_id)
    )
    if member is None:
        raise ApiError(404, "NOT_FOUND", "Registro nao encontrado.")
    return member


def invitation_status(db, member):
    token = db.scalar(
        select(SecurityToken)
        .where(
            SecurityToken.membership_id == member.id, SecurityToken.purpose == "INVITE"
        )
        .order_by(SecurityToken.created_at.desc(), SecurityToken.id.desc())
        .limit(1)
    )
    if token is None:
        return None
    if token.consumed_at:
        return "CONSUMED"
    if token.invalidated_at:
        return "CANCELLED"
    if token.expires_at <= now(db):
        return "EXPIRED"
    status = db.scalar(
        select(EmailOutbox.status).where(EmailOutbox.token_id == token.id)
    )
    return "QUEUED" if status == "DISPATCHING" else status or "UNKNOWN"


def member_view(db, principal, scope, member):
    caps = effective_capabilities(db, principal, scope)
    user = db.get(User, member.user_id)
    role = db.get(TenantRole, member.role_id)
    actions = []
    internal = db.get(PlatformRoleAssignment, member.user_id) is not None
    protected = internal or (
        principal.platform_role == "PLATFORM_SUPPORT"
        and role_sensitive(role, permissions(db, role))
    )
    if (
        principal.platform_role in {"PLATFORM_ADMIN", "PLATFORM_SUPPORT"}
        and not protected
    ):
        if "users.status" in caps:
            actions += [
                "inactivate" if member.active else "activate",
                "unblock" if member.blocked else "block",
            ]
        if "roles.assign" in caps:
            actions.append("assign_role")
        available = member.active and not member.blocked and role.active
        if (
            available
            and member.invitation_pending
            and "users.invite" in caps
            and (
                not member.invite_requires_admin
                or principal.platform_role == "PLATFORM_ADMIN"
            )
        ):
            from app.platform.policy import role_support_eligible

            if principal.platform_role == "PLATFORM_ADMIN" or role_support_eligible(
                role, permissions(db, role)
            ):
                actions.append("invite")
        if (
            available
            and not member.invitation_pending
            and "users.password_reset" in caps
        ):
            actions.append("reset_password")
    return ManagedMembershipView(
        id=member.id,
        user_id=member.user_id,
        display_name=user.display_name,
        email=user.email_normalized,
        role_id=member.role_id,
        role_name=role.name,
        active=member.active,
        blocked=member.blocked,
        invitation_pending=member.invitation_pending,
        version=member.version,
        allowed_actions=actions,
        invitation_status=invitation_status(db, member),
        last_access_at=last_context_access(db, scope, member.user_id),
    )


def list_members(db, principal, scope, search, status, role_id, limit, offset):
    query = visible_query(scope, principal).join(User, User.id == Membership.user_id)
    if search:
        query = query.where(
            or_(
                User.email_normalized.icontains(search, autoescape=True),
                User.display_name.icontains(search, autoescape=True),
            )
        )
    if role_id:
        query = query.where(Membership.role_id == role_id)
    if status == "ACTIVE":
        query = query.where(
            Membership.active.is_(True),
            Membership.blocked.is_(False),
            Membership.invitation_pending.is_(False),
        )
    elif status == "INACTIVE":
        query = query.where(Membership.active.is_(False))
    elif status == "BLOCKED":
        query = query.where(Membership.blocked.is_(True))
    elif status == "PENDING":
        query = query.where(Membership.invitation_pending.is_(True))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = list(
        db.scalars(
            query.order_by(User.email_normalized, Membership.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return {
        "items": [member_view(db, principal, scope, member) for member in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def last_context_access(db, scope, user_id):
    """Context selection proves scoped access; global login evidence cannot."""
    from app.audit.models import AuditEvent

    return db.scalar(
        select(func.max(AuditEvent.occurred_at)).where(
            AuditEvent.tenant_id == scope.tenant_id,
            AuditEvent.contract_id == scope.contract_id,
            AuditEvent.actor_id == user_id,
            AuditEvent.action == "context.selected",
            AuditEvent.entity_type == "access_context",
            AuditEvent.outcome == "SUCCESS",
        )
    )
