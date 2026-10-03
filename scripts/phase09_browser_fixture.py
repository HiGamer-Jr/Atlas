"""Phase9 controlled browser harness, only attested disposable PostgreSQL.

All credentials stay in temporary environment or subprocess memory.
No maintenance action or operational handler is registered by this fixture.
"""
import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.identity.passwords import hash_password
from phase05_browser_fixture import create_browser_app as _create_browser_app
from phase06_browser_fixture import clean
from sqlalchemy import text
from tests.database_harness import open_test_engines
from tests.helpers import seed_scope
from tests.identity_helpers import seed_user


def create_browser_app():
    return _create_browser_app()


def seed():
    owner, runtime = open_test_engines()
    try:
        with runtime.connect() as connection:
            if connection.scalar(text("SELECT count(*) FROM users")):
                raise ValueError("Only an empty attested test database is allowed")
        users = {
            "admin_user": seed_user(runtime, "admin@example.test", "PLATFORM_ADMIN"),
            "support_user": seed_user(runtime, "support@example.test", "PLATFORM_SUPPORT"),
            "member_user": seed_user(runtime, "member@example.test"),
        }
        identifiers = seed_scope(runtime, users)
        password_hash = hash_password(os.environ["HIATLAS_E2E_PASSWORD"])
        with runtime.begin() as connection:
            for key, name in [
                ("admin_user", "Administrador de teste"),
                ("support_user", "Suporte de teste"),
                ("member_user", "Pessoa visualizada"),
            ]:
                connection.execute(
                    text("UPDATE users SET display_name=:name,password_hash=:hash WHERE id=:id"),
                    {"id": users[key], "name": name, "hash": password_hash},
                )
            connection.execute(
                text("UPDATE tenant_roles SET name=:name WHERE id=:id"),
                {"id": identifiers["role_basic"], "name": "Comprador de teste"},
            )
        # Consumed only through a subprocess pipe by the browser harness.
        print(json.dumps({key: str(value) for key, value in identifiers.items()}))
    finally:
        owner.dispose()
        runtime.dispose()


def controlled_action(action, identifier):
    owner, runtime = open_test_engines()
    try:
        with owner.begin() as connection:
            if action == "stale-reauth":
                connection.execute(
                    text("UPDATE auth_sessions SET reauthenticated_at=now()-interval '10 minutes'"),
                )
            elif action == "revoke-context":
                connection.execute(
                    text("UPDATE access_contexts SET revoked_at=:now WHERE id=:id"),
                    {"id": UUID(identifier), "now": datetime.now(UTC)},
                )
            elif action == "expire":
                # Clock is real. Keep the physical lifetime check valid.
                connection.execute(
                    text("UPDATE temporary_privileged_grants SET expires_at=started_at+interval '1 microsecond' WHERE id=:id"),
                    {"id": UUID(identifier)},
                )
            else:
                raise ValueError("Unknown controlled action")
    finally:
        owner.dispose()
        runtime.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "clean", "expire", "revoke-context", "stale-reauth"])
    parser.add_argument("--id")
    args = parser.parse_args()
    if args.action == "seed":
        seed()
    elif args.action == "clean":
        clean()
    else:
        controlled_action(args.action, args.id)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- do not expose SQL, credentials or payloads
        print("Controlled phase9 fixture failed; sensitive diagnostics suppressed", file=sys.stderr)
        raise SystemExit(1) from None
