"""Phase8 browser harness: disposable attested PostgreSQL and fake email only."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from phase05_browser_fixture import create_browser_app as _create_browser_app
from phase05_browser_fixture import main as phase05_main
from phase06_browser_fixture import clean
from sqlalchemy import text
from tests.database_harness import open_test_engines


def create_browser_app():
    return _create_browser_app()


def controlled_action(action, identifier):
    owner, runtime = open_test_engines()
    try:
        with owner.begin() as connection:
            if action == "names":
                for email, name in [("admin@example.test", "Administrador de teste"), ("support@example.test", "Suporte de teste"), ("member@example.test", "Pessoa visualizada")]:
                    connection.execute(text("UPDATE users SET display_name=:name WHERE email_normalized=:email"), {"name": name, "email": email})
                connection.execute(text("UPDATE tenant_roles SET name=:name WHERE code=:code"), {"name": "Comprador de teste", "code": "ROLE_BASIC"})
            elif action == "expire":
                connection.execute(text("UPDATE support_sessions SET expires_at=started_at + interval '1 microsecond' WHERE id=:id"), {"id": UUID(identifier)})
            elif action == "revoke-context":
                connection.execute(text("UPDATE access_contexts SET revoked_at=:now WHERE id=:id"), {"id": UUID(identifier), "now": datetime.now(UTC)})
            else:
                raise ValueError("Unknown controlled action")
    finally:
        owner.dispose()
        runtime.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["seed", "clean", "names", "expire", "revoke-context"])
    parser.add_argument("--id")
    args = parser.parse_args()
    if args.action == "clean":
        clean()
    elif args.action == "seed":
        sys.argv = [sys.argv[0], "seed"]
        phase05_main()
        controlled_action("names", None)
    else:
        controlled_action(args.action, args.id)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- never leak fixture payload or credentials
        print("Controlled phase8 fixture failed; sensitive diagnostics suppressed", file=sys.stderr)
        raise SystemExit(1) from None
