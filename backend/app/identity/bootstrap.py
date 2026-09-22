"""Local, one-time creation of the first platform administrator. Never an HTTP route."""

import argparse
import getpass
import sys
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.audit.models import AccessEvent, AuditEvent
from app.audit.schemas import AuditInput, IdentitySnapshot
from app.audit.service import append_event
from app.core.config import Settings
from app.core.errors import ApiError
from app.db import models as _models  # noqa: F401 -- standalone CLI registry
from app.db.session import create_database_engine, validate_runtime_connection
from app.identity.models import PlatformRoleAssignment, User
from app.identity.operators import lock_operator_population
from app.identity.passwords import hash_password
from app.identity.schemas import LoginInput


def bootstrap_admin(db, email: str, password: str):
    try:
        identity = LoginInput(email=email, password=password)
    except ValidationError:
        raise ApiError(422, "BOOTSTRAP_INVALID", "Dados inválidos.") from None
    if len(password) < 12:
        raise ApiError(
            422, "BOOTSTRAP_INVALID", "A senha deve ter entre 12 e 1024 caracteres."
        )
    lock_operator_population(db)
    initialized = db.scalar(
        select(exists().where(AuditEvent.action == "identity.bootstrap"))
    )
    any_admin = db.scalar(
        select(exists().where(PlatformRoleAssignment.role == "PLATFORM_ADMIN"))
    )
    if initialized or any_admin:
        raise ApiError(409, "BOOTSTRAP_CLOSED", "O bootstrap inicial já foi realizado.")
    if (
        db.scalar(select(User.id).where(User.email_normalized == identity.email))
        is not None
    ):
        raise ApiError(409, "IDENTITY_EXISTS", "O bootstrap exige uma identidade nova.")
    user = User(
        email_normalized=identity.email,
        display_name=identity.email[:200],
        password_hash=hash_password(password),
        active=True,
        blocked=False,
    )
    db.add(user)
    db.flush()
    db.add(PlatformRoleAssignment(user_id=user.id, role="PLATFORM_ADMIN", active=True))
    append_event(
        db,
        AuditInput(
            actor_id=user.id,
            actor_role="PLATFORM_ADMIN",
            action="identity.bootstrap",
            entity_type="user",
            entity_id=user.id,
            after=IdentitySnapshot(
                user_id=user.id,
                active=True,
                blocked=False,
                platform_role="PLATFORM_ADMIN",
            ),
        ),
    )
    return user.id


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        # argparse's default echoes unrecognized arguments, potentially a pasted secret.
        self.exit(
            2,
            "Argumentos inválidos. Use --help; senha somente por entrada protegida.\n",
        )


def main():
    parser = SafeArgumentParser(
        description="Bootstrap local do primeiro Administrador HiAtlas."
    )
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        print("Use um terminal interativo com entrada protegida.", file=sys.stderr)
        return 2
    password = getpass.getpass("Senha (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirme a senha: ")
    if password != confirmation:
        print("A confirmação não corresponde.", file=sys.stderr)
        return 2
    engine = None
    try:
        engine = create_database_engine(Settings().database_url)
        with Session(engine) as db, db.begin():
            validate_runtime_connection(db.connection())
            bootstrap_admin(db, args.email, password)
    except ApiError as error:
        if engine is not None:
            with Session(engine) as db, db.begin():
                validate_runtime_connection(db.connection())
                db.add(
                    AccessEvent(
                        action="identity.bootstrap",
                        outcome="DENIED",
                        request_id=uuid4(),
                        reason=error.code,
                    )
                )
        print("Bootstrap recusado: " + error.code, file=sys.stderr)
        return 1
    except Exception:  # noqa: BLE001 -- CLI boundary must not print credentials in tracebacks
        print(
            "Bootstrap não concluído; confira configuração e migrações.",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    print("Administrador inicial criado com auditoria.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
