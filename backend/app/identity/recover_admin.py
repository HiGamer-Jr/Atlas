"""Offline recovery of an existing inaccessible administrator; never a web route."""

import getpass
import os
import sys
import warnings
from datetime import UTC, datetime
from typing import Literal
from unicodedata import category, normalize
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy import exists, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.audit.schemas import RecoveryAuditInput, RecoverySnapshot
from app.audit.service import append_event
from app.core.config import Settings
from app.core.errors import ApiError
from app.db import models as _models  # noqa: F401
from app.db.session import create_database_engine, validate_runtime_connection
from app.grants.models import TemporaryPrivilegedGrant
from app.identity.bootstrap import SafeArgumentParser
from app.identity.email_transport import SMTPEmailTransport
from app.identity.models import (
    AuthSession,
    EmailOutbox,
    PlatformRoleAssignment,
    SecurityToken,
    User,
)
from app.identity.operators import lock_operator_population, snapshot
from app.identity.passwords import hash_password, validate_password
from app.identity.sessions import lock_users
from app.identity.tokens import lifecycle_lock
from app.support.models import SupportSession
from app.tenancy.models import AccessContext


class RecoveryRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        hide_input_in_errors=True,
    )

    environment: Literal["TEST", "STAGING", "PRODUCTION"]

    user_id: UUID

    technical_operator: str = Field(min_length=3, max_length=200)

    reason: str = Field(min_length=3, max_length=1000)

    reference: str = Field(min_length=1, max_length=200)

    incident_evidence: str = Field(min_length=10, max_length=1000)

    verified_email: str = Field(min_length=3, max_length=320)

    confirmation: UUID

    credential_loss_attested: StrictBool = False

    @field_validator(
        "technical_operator",
        "reason",
        "reference",
        "incident_evidence",
        "verified_email",
        mode="before",
    )
    @classmethod
    def plain_text(cls, value):

        if not isinstance(value, str) or any(
            category(char).startswith("C") for char in value
        ):
            raise ValueError("Plain text required")

        return normalize("NFC", value).strip()


def validate_recovery_connection(db, settings, recovery_role):

    try:
        validate_runtime_connection(db.connection())

        role = db.scalar(text("SELECT current_user"))

        runtime_role = make_url(settings.database_url).username

        allowed = db.scalar(
            text(
                "SELECT has_table_privilege(current_user, 'users', 'SELECT') AND has_column_privilege(current_user, 'users', 'password_hash', 'UPDATE') AND has_table_privilege(current_user, 'audit_events', 'INSERT') AND NOT has_table_privilege(current_user, 'audit_events', 'UPDATE') AND NOT has_table_privilege(current_user, 'audit_events', 'DELETE') AND NOT has_table_privilege(current_user, 'users', 'INSERT') AND NOT has_table_privilege(current_user, 'users', 'DELETE') AND NOT has_table_privilege(current_user, 'users', 'UPDATE') AND NOT has_table_privilege(current_user, 'audit_events', 'TRUNCATE') AND NOT has_table_privilege(current_user, 'audit_events', 'SELECT')"
            )
        )

        if (
            not recovery_role
            or role != recovery_role
            or role == runtime_role
            or not allowed
        ):
            raise ValueError("Forbidden recovery identity")

    except ValueError:
        raise ApiError(
            403,
            "RECOVERY_CREDENTIAL_REQUIRED",
            "Credencial de recuperação exclusiva necessária.",
        ) from None

    return role


def recover_admin(db, request, password, settings, *, recovery_role):
    """Caller owns transaction. Any error, including auditing, must roll it all back."""

    role_name = validate_recovery_connection(db, settings, recovery_role)

    if request.environment != {
        "test": "TEST",
        "development": "TEST",
        "production": "PRODUCTION",
        "staging": "STAGING",
    }.get(settings.environment):
        raise ApiError(
            422,
            "RECOVERY_ENVIRONMENT_MISMATCH",
            "Ambiente não corresponde à configuração.",
        )

    validate_password(password, settings)

    lock_operator_population(db)

    lifecycle_lock(db)

    lock_users(db, [request.user_id])

    target = db.get(User, request.user_id, populate_existing=True)

    role = db.get(PlatformRoleAssignment, request.user_id, populate_existing=True)

    if target is None or role is None or role.role != "PLATFORM_ADMIN":
        raise ApiError(
            404, "RECOVERY_TARGET_INVALID", "Administrador existente necessário."
        )

    if (
        request.confirmation != target.id
        or request.verified_email != target.email_normalized
    ):
        raise ApiError(
            422,
            "RECOVERY_CONFIRMATION_MISMATCH",
            "Confirmação externa não corresponde ao alvo.",
        )

    repeated = db.scalar(
        select(
            exists(
                select(AuditEvent.id).where(
                    AuditEvent.action == "identity.admin.recovered",
                    AuditEvent.entity_id == target.id,
                    AuditEvent.reference == request.reference,
                )
            )
        )
    )

    if repeated and request.credential_loss_attested:
        raise ApiError(
            409,
            "RECOVERY_INCIDENT_ALREADY_USED",
            "Incidente já concluído para este alvo.",
        )

    normal_unavailable = not SMTPEmailTransport(settings).available

    usable = db.scalar(
        select(
            exists().where(
                User.id == PlatformRoleAssignment.user_id,
                User.active.is_(True),
                User.blocked.is_(False),
                User.password_hash.is_not(None),
                PlatformRoleAssignment.active.is_(True),
                PlatformRoleAssignment.role == "PLATFORM_ADMIN",
            )
        )
    )

    # Knowledge of the credential cannot be proven from its hash. The narrow

    # explicit attestation is trusted only at the privileged offline boundary;

    # configured normal delivery or any other usable admin still refuses it.

    other_usable = db.scalar(
        select(
            exists().where(
                User.id == PlatformRoleAssignment.user_id,
                User.id != target.id,
                User.active.is_(True),
                User.blocked.is_(False),
                User.password_hash.is_not(None),
                PlatformRoleAssignment.active.is_(True),
                PlatformRoleAssignment.role == "PLATFORM_ADMIN",
            )
        )
    )

    if other_usable or (
        usable and not (request.credential_loss_attested and normal_unavailable)
    ):
        raise ApiError(
            409,
            "RECOVERY_NOT_NECESSARY",
            "Administrador utilizável existente; use o fluxo normal.",
        )

    if repeated:
        raise ApiError(
            409,
            "RECOVERY_INCIDENT_ALREADY_USED",
            "Incidente já concluído para este alvo.",
        )
    before = snapshot(target, role)

    now = datetime.now(UTC)

    target.password_hash = hash_password(password)

    target.active, target.blocked, role.active = True, False, True

    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == target.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    db.execute(
        update(AccessContext)
        .where(AccessContext.actor_id == target.id, AccessContext.revoked_at.is_(None))
        .values(revoked_at=now)
    )

    db.execute(
        update(SupportSession)
        .where(
            SupportSession.operator_id == target.id, SupportSession.status == "ACTIVE"
        )
        .values(status="REVOKED", ended_at=now)
    )

    db.execute(
        update(TemporaryPrivilegedGrant)
        .where(
            TemporaryPrivilegedGrant.operator_id == target.id,
            TemporaryPrivilegedGrant.status == "ACTIVE",
        )
        .values(
            status="REVOKED",
            ended_at=now,
            revoked_at=now,
            version=TemporaryPrivilegedGrant.version + 1,
        )
    )

    token_ids = select(SecurityToken.id).where(
        SecurityToken.recipient_user_id == target.id
    )

    db.execute(
        update(EmailOutbox)
        .where(
            EmailOutbox.token_id.in_(token_ids),
            EmailOutbox.status.in_(["QUEUED", "DISPATCHING"]),
        )
        .values(status="CANCELLED", ciphertext=None, failure_code="ADMIN_RECOVERY")
    )

    db.execute(
        update(SecurityToken)
        .where(
            SecurityToken.recipient_user_id == target.id,
            SecurityToken.consumed_at.is_(None),
            SecurityToken.invalidated_at.is_(None),
        )
        .values(invalidated_at=now)
    )

    after = RecoverySnapshot(
        **snapshot(target, role).model_dump(),
        technical_operator=request.technical_operator,
        database_role=role_name,
        incident_evidence=request.incident_evidence,
        credential_loss_attested=request.credential_loss_attested,
        normal_recovery_unavailable=normal_unavailable,
    )

    append_event(
        db,
        RecoveryAuditInput(
            environment=request.environment,
            entity_id=target.id,
            reason=request.reason,
            reference=request.reference,
            before=before,
            after=after,
        ),
    )

    db.flush()

    return target.id


def main():

    parser = SafeArgumentParser(
        description="Recuperação administrativa offline auditada."
    )

    parser.add_argument("--environment", required=True, choices=["TEST", "PRODUCTION"])

    parser.add_argument("--user-id", required=True, type=UUID)

    parser.add_argument(
        "--credential-loss",
        action="store_true",
        help="Exige declaração protegida de perda e indisponibilidade do canal normal.",
    )

    parser.add_argument("--technical-operator", required=True)

    parser.add_argument("--reason", required=True)

    parser.add_argument("--reference", required=True)

    parser.add_argument("--incident-evidence", required=True)

    parser.add_argument("--verified-email", required=True)

    parser.add_argument("--confirm-user-id", required=True, type=UUID)

    args = parser.parse_args()

    engine = None

    try:
        request = RecoveryRequest(
            environment=args.environment,
            user_id=args.user_id,
            technical_operator=args.technical_operator,
            reason=args.reason,
            reference=args.reference,
            incident_evidence=args.incident_evidence,
            verified_email=args.verified_email,
            confirmation=args.confirm_user_id,
        )

        if not sys.stdin.isatty() or not sys.stderr.isatty():
            return 2

        url, role = (
            os.environ.get("RECOVERY_DATABASE_URL"),
            os.environ.get("RECOVERY_DATABASE_ROLE"),
        )

        if not url or not role:
            return 2

        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)

            if args.credential_loss:
                attestation = getpass.getpass(
                    "Atesto perda da credencial, identidade e aprovação verificadas fora de banda, canal normal indisponível. Confirme UUID do alvo: "
                )

                if attestation != str(request.user_id):
                    return 2

                request = request.model_copy(update={"credential_loss_attested": True})

            password = getpass.getpass("Nova senha: ")

            confirmation = getpass.getpass("Confirme a nova senha: ")

        if password != confirmation:
            return 2

        settings = Settings()

        engine = create_database_engine(url)

        with Session(engine) as db, db.begin():
            recover_admin(db, request, password, settings, recovery_role=role)

    except Exception:  # noqa: BLE001 -- never echo secret-bearing exceptions
        print(
            "Recuperação recusada ou não concluída; consulte o procedimento operacional.",
            file=sys.stderr,
        )

        return 1

    finally:
        if engine is not None:
            engine.dispose()

    print(
        "Administrador existente recuperado com auditoria; sessões anteriores revogadas."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
