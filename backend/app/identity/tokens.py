from datetime import timedelta

from cryptography.fernet import Fernet
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.audit.schemas import AuditInput, SystemCancellationAuditInput
from app.audit.service import append_event
from app.core.errors import ApiError
from app.core.security import new_token, token_hash
from app.identity.models import (
    AuthRateLimit,
    AuthSession,
    EmailOutbox,
    SecurityToken,
    User,
)
from app.identity.rate_limits import record_failure
from app.identity.sessions import lock_users
from app.tenancy.models import AccessContext, Contract, Membership, Tenant, TenantRole

LIFECYCLE_LOCK = 720260925


def lifecycle_lock(db):
    # Always before identity/context locks; also serializes reissue against SMTP dispatch.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": LIFECYCLE_LOCK})


def access_limit(db, purpose, identifier, source, now, settings):
    keys = {
        token_hash(
            f"access:{purpose}:recipient:{identifier}"
        ): settings.access_request_limit,
        token_hash(f"access:{purpose}:source:{source}"): settings.access_source_limit,
    }
    buckets = []
    limited = False
    for key in sorted(keys):
        db.execute(
            insert(AuthRateLimit)
            .values(bucket_key=key, window_started_at=now, failures=0)
            .on_conflict_do_nothing()
        )
        bucket = db.scalar(
            select(AuthRateLimit)
            .where(AuthRateLimit.bucket_key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if now >= bucket.window_started_at + timedelta(
            seconds=settings.access_window_seconds
        ):
            bucket.window_started_at, bucket.failures = now, 0
        limited |= bucket.failures >= keys[key]
        buckets.append(bucket)
    if not limited:
        record_failure(buckets)
    return limited


def require_mail(settings, transport):
    if not settings.outbox_key or not transport.available:
        raise ApiError(
            503,
            "EMAIL_UNAVAILABLE",
            "Servico de e-mail indisponivel. Tente novamente mais tarde.",
        )


def event(
    db,
    user_id,
    action,
    request_id,
    role=None,
    member=None,
    actor_id=None,
    before=None,
    after=None,
):
    append_event(
        db,
        AuditInput(
            actor_id=actor_id or user_id,
            before=before,
            after=after,
            actor_role=role,
            action=action,
            entity_type="membership" if member else "user",
            entity_id=member.id if member else user_id,
            tenant_id=member.tenant_id if member else None,
            contract_id=member.contract_id if member else None,
            request_id=request_id,
        ),
    )


def queue_access_email(
    db,
    settings,
    user,
    purpose,
    now,
    request_id,
    member=None,
    issuer_role=None,
    actor_id=None,
):
    """Caller owns lifecycle/user locks and transaction. Returns only outbox ID."""
    from app.identity.mailboxes import single_mailbox

    single_mailbox(user.email_normalized)
    if purpose not in {"INVITE", "PASSWORD_RESET"}:
        raise ValueError("Invalid purpose")
    if purpose == "INVITE" and member is not None:
        if member.invite_requires_admin and issuer_role != "PLATFORM_ADMIN":
            raise ApiError(
                403,
                "INVITE_ADMIN_REQUIRED",
                "Convite exige reemissao pela administracao.",
            )
        if issuer_role == "PLATFORM_ADMIN":
            member.invite_requires_admin = False
    previous = list(
        db.scalars(
            select(SecurityToken)
            .where(
                SecurityToken.recipient_user_id == user.id,
                SecurityToken.purpose == purpose,
                SecurityToken.consumed_at.is_(None),
                SecurityToken.invalidated_at.is_(None),
                SecurityToken.expires_at > now,
            )
            .with_for_update()
        )
    )
    for row in previous:
        row.invalidated_at = now
    if previous:
        db.execute(
            update(EmailOutbox)
            .where(
                EmailOutbox.token_id.in_([row.id for row in previous]),
                EmailOutbox.status.in_(["QUEUED", "DISPATCHING"]),
            )
            .values(
                status="CANCELLED", ciphertext=None, failure_code="TOKEN_INVALIDATED"
            )
        )
    raw, hashed = new_token()
    token = SecurityToken(
        token_hash=hashed,
        purpose=purpose,
        recipient_user_id=user.id,
        recipient_email=user.email_normalized,
        membership_id=member.id if member else None,
        issuer_role=issuer_role,
        created_at=now,
        expires_at=now
        + timedelta(
            seconds=settings.invite_seconds
            if purpose == "INVITE"
            else settings.password_reset_seconds
        ),
    )
    db.add(token)
    db.flush()
    protected = (
        Fernet(settings.outbox_key.get_secret_value().encode())
        .encrypt(raw.encode())
        .decode()
    )
    outbox = EmailOutbox(
        token_id=token.id,
        message_type=purpose,
        recipient=user.email_normalized,
        status="QUEUED",
        attempts=0,
        ciphertext=protected,
        created_at=now,
        next_attempt_at=now,
    )
    db.add(outbox)
    db.flush()
    name = "invite" if purpose == "INVITE" else "reset"
    event(
        db,
        user.id,
        f"access.{name}.{'resent' if previous else 'requested'}",
        request_id,
        issuer_role,
        member,
        actor_id,
    )
    return outbox.id


def eligible_token(db, token, user, purpose, now):
    if (
        token is None
        or token.purpose != purpose
        or token.consumed_at is not None
        or token.invalidated_at is not None
        or user is None
        or not user.active
        or user.blocked
        or token.recipient_user_id != user.id
        or token.recipient_email != user.email_normalized
    ):
        raise ApiError(400, "TOKEN_INVALID", "Link invalido ou ja utilizado.")
    if token.expires_at <= now:
        raise ApiError(400, "TOKEN_EXPIRED", "Este link expirou. Solicite um novo.")
    if purpose == "PASSWORD_RESET" and not user.password_hash:
        raise ApiError(400, "TOKEN_INVALID", "Link invalido ou ja utilizado.")
    if token.membership_id:
        from app.tenancy.contexts import contract_rows

        member = db.get(Membership, token.membership_id)
        if member:
            contract_rows(db, member.contract_id)
        member = db.get(
            Membership,
            token.membership_id,
            populate_existing=True,
            with_for_update=True,
        )
        role = (
            db.get(
                TenantRole, member.role_id, populate_existing=True, with_for_update=True
            )
            if member
            else None
        )
        contract = (
            db.get(Contract, member.contract_id, populate_existing=True)
            if member
            else None
        )
        tenant = (
            db.get(Tenant, member.tenant_id, populate_existing=True) if member else None
        )
        if (
            not member
            or member.user_id != user.id
            or (purpose == "INVITE" and not member.invitation_pending)
            or (purpose == "PASSWORD_RESET" and member.invitation_pending)
            or member.blocked
            or not member.active
            or not role
            or not role.active
            or not contract
            or not contract.active
            or not tenant
            or not tenant.active
        ):
            raise ApiError(400, "TOKEN_INVALID", "Link invalido ou ja utilizado.")
        if token.issuer_role == "PLATFORM_SUPPORT":
            from app.platform.policy import role_sensitive, role_support_eligible
            from app.tenancy.contexts import permissions

            granted = permissions(db, role)
            allowed = (
                role_support_eligible(role, granted)
                if purpose == "INVITE"
                else not role_sensitive(role, granted)
            )
            if not allowed:
                if purpose == "INVITE":
                    cancel_member_invites(db, member, now, requires_admin=True)
                raise ApiError(400, "TOKEN_INVALID", "Link invalido ou ja utilizado.")
    return token


def load_token(db, raw, purpose, now, actor_id=None):
    token = db.scalar(
        select(SecurityToken).where(SecurityToken.token_hash == token_hash(raw))
    )
    if token is None:
        raise ApiError(400, "TOKEN_INVALID", "Link invalido ou ja utilizado.")
    lock_users(db, [token.recipient_user_id] + ([actor_id] if actor_id else []))
    user = db.get(User, token.recipient_user_id, populate_existing=True)
    token = db.scalar(
        select(SecurityToken)
        .where(SecurityToken.id == token.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    eligible_token(db, token, user, purpose, now)
    return token, user


def consume(db, token, now):
    result = db.execute(
        update(SecurityToken)
        .where(
            SecurityToken.id == token.id,
            SecurityToken.purpose == token.purpose,
            SecurityToken.consumed_at.is_(None),
            SecurityToken.invalidated_at.is_(None),
            SecurityToken.expires_at > now,
        )
        .values(consumed_at=now)
        .returning(SecurityToken.id)
    ).scalar_one_or_none()
    if result is None:
        raise ApiError(400, "TOKEN_INVALID", "Link invalido ou ja utilizado.")
    db.execute(
        update(EmailOutbox)
        .where(EmailOutbox.token_id == token.id)
        .values(ciphertext=None)
    )


def revoke_sessions(db, user_id, now):
    from app.support.services import revoke_owned

    request = db.info.get("request")
    if request is not None:
        revoke_owned(db, request, user_id=user_id)
        from app.grants.services import revoke_owned as revoke_grants
        revoke_grants(db, request, user_id=user_id)
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(AccessContext)
        .where(AccessContext.actor_id == user_id, AccessContext.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def cancel_member_invites(db, member, now, requires_admin=False):
    changed = requires_admin and not member.invite_requires_admin
    if requires_admin:
        member.invite_requires_admin = True
    rows = list(
        db.scalars(
            select(SecurityToken)
            .where(
                SecurityToken.membership_id == member.id,
                SecurityToken.purpose == "INVITE",
                SecurityToken.consumed_at.is_(None),
                SecurityToken.invalidated_at.is_(None),
            )
            .with_for_update()
        )
    )
    for token in rows:
        token.invalidated_at = now
    if rows:
        db.execute(
            update(EmailOutbox)
            .where(
                EmailOutbox.token_id.in_([row.id for row in rows]),
                EmailOutbox.status.in_(["QUEUED", "DISPATCHING"]),
            )
            .values(
                status="CANCELLED", ciphertext=None, failure_code="INVITE_INVALIDATED"
            )
        )

    if rows or changed:
        append_event(
            db,
            SystemCancellationAuditInput(
                entity_type="membership",
                entity_id=member.id,
                tenant_id=member.tenant_id,
                contract_id=member.contract_id,
            ),
        )
