"""Curated internal lifecycle. Caller owns commit; failures roll back command savepoint."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.models import AuthSession, User
from app.identity.operators import lock_operator_population
from app.identity.schemas import Principal
from app.identity.sessions import current_role, lock_users
from app.partners import audit
from app.partners.models import (
    PartnerMembership,
    PartnerMembershipPermission,
    PartnerOrganization,
)
from app.partners.schemas import (
    PartnerMembershipCreate,
    PartnerMembershipReplace,
    PartnerOrganizationCreate,
)
from app.platform.capabilities import INTERNAL_GRANTS
from app.tenancy.contexts import now


def revalidate(db, principal, capability):
    user = db.get(User, principal.user_id, populate_existing=True)
    session = db.get(AuthSession, principal.session_id, populate_existing=True)
    clock = now(db)
    idle = getattr(db.info.get("settings"), "session_idle_seconds", 1800)
    if (
        user is None
        or not user.active
        or user.blocked
        or session is None
        or session.user_id != principal.user_id
        or session.revoked_at is not None
        or session.expires_at <= clock
        or session.last_seen_at + timedelta(seconds=idle) <= clock
    ):
        raise ApiError(401, "SESSION_INVALID", "Autenticação necessária.")
    role = current_role(db, principal.user_id)
    if role != "PLATFORM_ADMIN" or capability not in INTERNAL_GRANTS.get(role, ()):
        raise ApiError(
            403, "PLATFORM_ADMIN_REQUIRED", "Operação restrita à administração HiAtlas."
        )


def identity_locks(db, principal, capability, target_user=None):
    lock_operator_population(db)
    lock_users(db, [principal.user_id] + ([target_user] if target_user else []))
    db.scalar(
        select(AuthSession)
        .where(AuthSession.id == principal.session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    revalidate(db, principal, capability)


def organization_lock(db, organization_id):
    organization = db.scalar(
        select(PartnerOrganization)
        .where(PartnerOrganization.id == organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if organization is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    return organization


def permission_rows(db, member):
    return list(
        db.scalars(
            select(PartnerMembershipPermission)
            .where(
                PartnerMembershipPermission.membership_id == member.id,
                PartnerMembershipPermission.organization_id == member.organization_id,
            )
            .order_by(PartnerMembershipPermission.code)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )


def replace_permissions(db, member, desired, rows):
    for row in rows:
        row.active = row.code in desired
    for code in sorted(desired - {row.code for row in rows}):
        db.add(
            PartnerMembershipPermission(
                organization_id=member.organization_id,
                membership_id=member.id,
                code=code,
                active=True,
            )
        )
    db.flush()


def create_partner_organization(
    db: Session, principal: Principal, command: PartnerOrganizationCreate
) -> PartnerOrganization:
    capability = "partners.organizations.manage"
    with db.begin_nested():
        identity_locks(db, principal, capability)
        organization = PartnerOrganization(name=command.name, category=command.category)
        db.add(organization)
        db.flush()
        revalidate(db, principal, capability)
        audit.record(
            db,
            principal,
            "partner.organization.created",
            "partner_organization",
            organization.id,
            audit.organization_snapshot(organization),
        )
        return organization


def create_partner_membership(
    db: Session, principal: Principal, command: PartnerMembershipCreate
) -> PartnerMembership:
    capability = "partners.memberships.manage"
    try:
        with db.begin_nested():
            identity_locks(db, principal, capability, command.user_id)
            organization = organization_lock(db, command.organization_id)
            if not organization.active or db.get(User, command.user_id) is None:
                raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
            revalidate(db, principal, capability)
            member = PartnerMembership(
                organization_id=organization.id, user_id=command.user_id
            )
            db.add(member)
            db.flush()
            desired = set(command.permissions)
            replace_permissions(db, member, desired, [])
            revalidate(db, principal, capability)
            audit.record(
                db,
                principal,
                "partner.membership.created",
                "partner_membership",
                member.id,
                audit.membership_snapshot(member, desired),
            )
            return member
    except IntegrityError:
        raise ApiError(409, "CONFLICT", "Vínculo já existente.") from None


def replace_partner_membership(
    db: Session,
    principal: Principal,
    membership_id: UUID,
    command: PartnerMembershipReplace,
) -> PartnerMembership:
    capability = "partners.memberships.manage"
    with db.begin_nested():
        # IDs discovered here are lock candidates; reload aggregate after identity locks.
        candidate = db.execute(
            select(PartnerMembership.organization_id, PartnerMembership.user_id).where(
                PartnerMembership.id == membership_id
            )
        ).first()
        identity_locks(
            db, principal, capability, candidate.user_id if candidate else None
        )
        if candidate is None:
            raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
        organization_lock(db, candidate.organization_id)
        member = db.scalar(
            select(PartnerMembership)
            .where(
                PartnerMembership.id == membership_id,
                PartnerMembership.organization_id == candidate.organization_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if member is None:
            raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
        rows = permission_rows(db, member)
        revalidate(db, principal, capability)
        if member.version != command.expected_version:
            raise ApiError(
                409,
                "VERSION_CONFLICT",
                "O registro mudou; atualize antes de confirmar.",
            )
        before = audit.membership_snapshot(
            member, {row.code for row in rows if row.active}
        )
        member.active, member.blocked = command.active, command.blocked
        member.version += 1
        desired = set(command.permissions)
        replace_permissions(db, member, desired, rows)
        audit.record(
            db,
            principal,
            "partner.membership.replaced",
            "partner_membership",
            member.id,
            audit.membership_snapshot(member, desired),
            before,
            command.reason,
        )
        return member
