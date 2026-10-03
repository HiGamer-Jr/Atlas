"""Phase10 browser infrastructure: attested disposable PostgreSQL, fake SMTP only.

Controlled action registrations live exclusively in the explicitly selected test
factory; create_app and the normal browser factory keep their registry empty.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from phase05_browser_fixture import create_browser_app as create_normal_browser_app
from phase06_browser_fixture import clean
from sqlalchemy import text

from app.identity.passwords import hash_password
from tests.database_harness import open_test_engines
from tests.helpers import seed_scope
from tests.identity_helpers import seed_user


def create_browser_app():
    application = create_normal_browser_app()
    if os.environ.get("HIATLAS_PHASE10_CONTROLLED") == "1":
        # Import only after the normal factory has attested the disposable DB.
        from tests.fixtures.correction_domain import register_fixture_action

        register_fixture_action(application)
    return application


def seed():
    owner, runtime = open_test_engines()
    try:
        with runtime.connect() as connection:
            if connection.scalar(text("SELECT count(*) FROM users")):
                raise ValueError("An empty attested disposable database is required")
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
                ("member_user", "Pessoa de teste"),
            ]:
                connection.execute(
                    text("UPDATE users SET display_name=:name,password_hash=:hash WHERE id=:id"),
                    {"id": users[key], "name": name, "hash": password_hash},
                )
            for suffix, tenant, contract in [
                ("a", "tenant_a", "contract_a"),
                ("a2", "tenant_a", "contract_a2"),
                ("b", "tenant_b", "contract_b"),
            ]:
                identifier = uuid4()
                identifiers["node_" + suffix] = identifier
                connection.execute(
                    text("INSERT INTO organization_nodes (id,tenant_id,contract_id,kind,name,code) VALUES (:id,:tenant,:contract,'COMPANY',:name,:code)"),
                    {"id": identifier, "tenant": identifiers[tenant], "contract": identifiers[contract], "name": "Unidade controlada " + suffix.upper(), "code": "TEST-" + suffix.upper()},
                )
        # IDs travel through subprocess memory, never browser evidence logs.
        print(json.dumps({key: str(value) for key, value in identifiers.items()}))
    finally:
        owner.dispose()
        runtime.dispose()


def conflict(identifier):
    owner, runtime = open_test_engines()
    try:
        with owner.begin() as connection:
            result = connection.execute(
                text("UPDATE organization_nodes SET name=:name,version=version+1,updated_at=now() WHERE id=:id"),
                {"id": UUID(identifier), "name": "Alteração concorrente controlada"},
            )
            if result.rowcount != 1:
                raise ValueError("Expected one controlled entity")
    finally:
        owner.dispose()
        runtime.dispose()



def seed_run(identifier, context_id):
    from tests.fixtures.correction_domain import seed_fixture_run

    owner, runtime = open_test_engines()
    try:
        with runtime.connect() as connection:
            node = connection.execute(
                text("SELECT tenant_id,contract_id FROM organization_nodes WHERE id=:id"),
                {"id": UUID(identifier)},
            ).one()
            context = connection.execute(
                text("SELECT tenant_id,contract_id FROM access_contexts WHERE id=:id"),
                {"id": UUID(context_id)},
            ).one()
            if tuple(node) != tuple(context):
                raise ValueError("Controlled scope mismatch")
        run_id = seed_fixture_run(runtime, {"tenant_a": node.tenant_id, "contract_a": node.contract_id}, UUID(identifier), UUID(context_id))
        print(json.dumps({"id": str(run_id)}))
    finally:
        owner.dispose()
        runtime.dispose()


def inspect_effect(identifier, source_id=None):
    owner, runtime = open_test_engines()
    try:
        with runtime.connect() as connection:
            node = connection.execute(
                text("SELECT name,version FROM organization_nodes WHERE id=:id"),
                {"id": UUID(identifier)},
            ).one()
            count = 0
            if source_id:
                count = connection.scalar(
                    text("SELECT count(*) FROM processing_runs WHERE source_run_id=:id"),
                    {"id": UUID(source_id)},
                )
            print(json.dumps({"name": node.name, "version": node.version, "reprocess_count": count}))
    finally:
        owner.dispose()
        runtime.dispose()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "clean", "conflict", "seed-run", "inspect"])
    parser.add_argument("--id")
    parser.add_argument("--context")
    parser.add_argument("--source")
    args = parser.parse_args()
    if args.action == "seed":
        seed()
    elif args.action == "clean":
        clean()
    elif args.action == "seed-run":
        seed_run(args.id, args.context)
    elif args.action == "inspect":
        inspect_effect(args.id, args.source)
    else:
        conflict(args.id)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- no raw SQL, payload, credentials or traceback
        print("Controlled phase10 fixture failed; sensitive diagnostics suppressed", file=sys.stderr)
        raise SystemExit(1) from None
