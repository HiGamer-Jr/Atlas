from app.audit.schemas import (
    AuditInput,
    PartnerMembershipSnapshot,
    PartnerOrganizationSnapshot,
)
from app.audit.service import append_event


def organization_snapshot(organization):
    return PartnerOrganizationSnapshot(
        partner_org_id=organization.id,
        name=organization.name,
        category=organization.category,
        active=organization.active,
        version=organization.version,
    )


def membership_snapshot(membership, permissions):
    return PartnerMembershipSnapshot(
        partner_org_id=membership.organization_id,
        partner_membership_id=membership.id,
        user_id=membership.user_id,
        active=membership.active,
        blocked=membership.blocked,
        invitation_pending=membership.invitation_pending,
        version=membership.version,
        permissions=sorted(permissions),
    )


def record(
    db, principal, action, entity_type, entity_id, after, before=None, reason=None
):
    return append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role="PLATFORM_ADMIN",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            reason=reason,
        ),
    )
