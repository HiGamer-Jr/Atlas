"""Prelock all identities before the existing authentication/context lock path."""

from sqlalchemy import select, text

from app.identity.operators import OPERATOR_LOCK
from app.identity.sessions import lock_users, session_candidate
from app.identity.tokens import lifecycle_lock
from app.procurement.requests import policy
from app.tenancy.contexts import authenticated, resolve_context
from app.tenancy.models import Membership


def prelock_identities(db, actor_id, buyer_membership_id=None):
    lifecycle_lock(db)
    db.execute(
        text("SELECT pg_advisory_xact_lock_shared(:key)"), {"key": OPERATOR_LOCK}
    )
    candidate_id = (
        db.scalar(
            select(Membership.user_id).where(Membership.id == buyer_membership_id)
        )
        if buyer_membership_id
        else None
    )
    lock_users(db, [actor_id] + ([candidate_id] if candidate_id else []))


def assignment_context(db, request, buyer_membership_id):
    session = session_candidate(db, request)
    if session:
        prelock_identities(db, session.user_id, buyer_membership_id)
    principal = authenticated(db, request)
    return resolve_context(db, request, principal)


def validate_candidate(db, principal, scope, node_id, membership_id):
    return policy.require_buyer_candidate(db, principal, scope, node_id, membership_id)
