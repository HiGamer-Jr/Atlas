"""Phase6 browser fixture. Attested disposable PostgreSQL and fake email only."""

import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from phase05_browser_fixture import create_browser_app as _create_browser_app
from phase05_browser_fixture import main as phase05_main
from sqlalchemy import inspect, text
from tests.conftest import TABLES
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
                raise ValueError("Requires an empty attested disposable database")
        users = {
            "admin_user": seed_user(runtime, "admin@example.test", "PLATFORM_ADMIN"),
            "support_user": seed_user(
                runtime, "support@example.test", "PLATFORM_SUPPORT"
            ),
            "member_user": seed_user(runtime, "member@example.test"),
        }
        identifiers = seed_scope(runtime, users)
        with runtime.begin() as connection:
            for key, name in [
                ("role_basic", "Comprador Nacional"),
                ("role_opt_out", "Coordenação"),
                ("role_finance", "Financeiro"),
                ("role_admin", "Diretoria"),
                ("role_sensitive_cap", "Fiscal sensível"),
            ]:
                connection.execute(
                    text("UPDATE tenant_roles SET name=:name WHERE id=:id"),
                    {"name": name, "id": identifiers[key]},
                )
            connection.execute(
                text("UPDATE tenant_roles SET support_assignable=true WHERE id=:id"),
                {"id": identifiers["role_opt_out"]},
            )
            connection.execute(
                text("UPDATE users SET display_name='Usuário existente' WHERE id=:id"),
                {"id": users["member_user"]},
            )
        for index in range(22):
            page_user = seed_user(runtime, f"phase6-page-{index:02d}@example.test")
            with runtime.begin() as connection:
                connection.execute(
                    text("UPDATE users SET display_name=:name WHERE id=:id"),
                    {"id": page_user, "name": f"Pessoa de teste {index:02d}"},
                )
                connection.execute(
                    text(
                        "INSERT INTO memberships (id,user_id,tenant_id,contract_id,role_id) VALUES (:id,:user,:tenant,:contract,:role)"
                    ),
                    {
                        "id": uuid4(),
                        "user": page_user,
                        "tenant": identifiers["tenant_a"],
                        "contract": identifiers["contract_a"],
                        "role": identifiers["role_basic"],
                    },
                )
        print(json.dumps({key: str(value) for key, value in identifiers.items()}))
    finally:
        owner.dispose()
        runtime.dispose()


def clean():
    """Explicit test reset; only the harness-attested database's known tables."""
    owner, runtime = open_test_engines()
    try:
        with owner.begin() as connection:
            present = set(inspect(connection).get_table_names())
            names = [name for name in TABLES if name in present]
            if names:
                connection.execute(text("TRUNCATE " + ", ".join(names) + " CASCADE"))
        print("Attested disposable fixture reset")
    finally:
        owner.dispose()
        runtime.dispose()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 2 and sys.argv[1] == "seed":
            seed()
        elif len(sys.argv) == 2 and sys.argv[1] == "clean":
            clean()
        else:
            phase05_main()
    except Exception:  # noqa: BLE001 -- suppress sensitive fixture failures
        print(
            "Controlled phase6 fixture failed; sensitive diagnostics withheld",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
