"""Browser fixtures restricted to the attested disposable test database."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text

from tests.database_harness import open_test_engines
from tests.helpers import seed_scope
from tests.identity_helpers import seed_user

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["seed", "expire", "invalidate"])
parser.add_argument("--context-id")
args = parser.parse_args()
owner, runtime = open_test_engines()
try:
    if args.action == "seed":
        with runtime.connect() as connection:
            exists = connection.scalar(text("SELECT count(*) FROM users"))
        if exists:
            raise SystemExit(
                "Seed requires an empty disposable database; run pytest first."
            )
        users = {
            "admin_user": seed_user(runtime, "admin@example.test", "PLATFORM_ADMIN"),
            "support_user": seed_user(
                runtime, "support@example.test", "PLATFORM_SUPPORT"
            ),
            "member_user": seed_user(runtime, "member@example.test"),
        }
        ids = seed_scope(runtime, users)
        with runtime.begin() as connection:
            connection.execute(
                text("UPDATE users SET display_name='Junior' WHERE id=:id"),
                {"id": users["admin_user"]},
            )
            connection.execute(
                text("UPDATE tenants SET name='GDSUL' WHERE id=:id"),
                {"id": ids["tenant_a"]},
            )
            connection.execute(
                text(
                    "UPDATE contracts SET code='CTR-2026-001', environment='PRODUCTION' WHERE id=:id"
                ),
                {"id": ids["contract_a"]},
            )
    elif args.action == "expire":
        with owner.begin() as connection:
            connection.execute(
                text("UPDATE auth_sessions SET expires_at=now()-interval '1 second'")
            )
    else:
        if not args.context_id:
            raise SystemExit("--context-id is required")
        with owner.begin() as connection:
            connection.execute(
                text("UPDATE access_contexts SET revoked_at=now() WHERE id=:id"),
                {"id": args.context_id},
            )
finally:
    owner.dispose()
    runtime.dispose()
print("Disposable browser fixture action completed.")
