from contextlib import ExitStack
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.main import create_app
from tests.database_harness import open_test_engines
from tests.identity_helpers import Clock, login, seed_user

BACKEND = Path(__file__).resolve().parents[1]
TABLES = (
    "maintenance_grant_scopes",
    "temporary_privileged_grants",
    "support_sessions",
    "membership_unit_scopes",
    "contract_modules",
    "organization_nodes",
    "email_outbox",
    "security_tokens",
    "access_contexts",
    "memberships",
    "tenant_role_permissions",
    "tenant_roles",
    "auth_sessions",
    "auth_preauth",
    "auth_rate_limits",
    "access_events",
    "audit_events",
    "platform_role_assignments",
    "contracts",
    "tenants",
    "users",
)


@pytest.fixture(scope="session")
def engines():
    try:
        result = open_test_engines()
    except (ValueError, SQLAlchemyError):
        pytest.fail(
            "Disposable PostgreSQL test setup is missing or unsafe. See database/README.md.",
            pytrace=False,
        )
    yield result
    for engine in result:
        engine.dispose()


@pytest.fixture(scope="session")
def db_owner(engines):
    return engines[0]


@pytest.fixture(scope="session")
def migration_config(engines):
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.attributes["runtime_role"] = engines[1].url.username
    return config


@pytest.fixture(scope="session")
def migrated(db_owner, migration_config):
    with db_owner.begin() as connection:
        migration_config.attributes["connection"] = connection
        command.upgrade(migration_config, "head")
    migration_config.attributes.pop("connection", None)
    return True


@pytest.fixture
def clean_database(migrated, db_owner):
    yield
    with db_owner.begin() as conn:
        present = set(inspect(conn).get_table_names())
        names = [name for name in TABLES if name in present]
        if names:
            conn.execute(text("TRUNCATE " + ", ".join(names) + " CASCADE"))


@pytest.fixture
def db_runtime(engines, clean_database):
    return engines[1]


@pytest.fixture
def db(db_runtime):
    with Session(db_runtime) as session:
        yield session
        session.rollback()


@pytest.fixture
def settings(db_runtime):
    return Settings(
        database_url=db_runtime.url.render_as_string(hide_password=False),
        environment="test",
        public_origin="https://testserver",
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def clock(app):
    clock = Clock()
    app.state.clock = clock
    return clock


@pytest.fixture
def auth_users(db_runtime):
    return {
        "admin_user": seed_user(db_runtime, "admin@example.test", "PLATFORM_ADMIN"),
        "support_user": seed_user(
            db_runtime, "support@example.test", "PLATFORM_SUPPORT"
        ),
        "member_user": seed_user(db_runtime, "member@example.test"),
    }


@pytest.fixture
def ids(auth_users):
    return {**auth_users, "last_admin_user": auth_users["admin_user"]}


@pytest.fixture
def new_client(app, clock):
    with ExitStack() as stack:

        def factory(**kwargs):
            return stack.enter_context(
                TestClient(app, base_url="https://testserver", **kwargs)
            )

        yield factory


@pytest.fixture
def admin(new_client, auth_users):
    client = new_client()
    login(client)
    return client


@pytest.fixture
def support(new_client, auth_users):
    client = new_client()
    login(client, "support@example.test")
    return client


@pytest.fixture
def last_admin(admin):
    return admin


@pytest.fixture
def scope_ids(db_runtime, auth_users):
    from tests.helpers import seed_scope

    return seed_scope(db_runtime, auth_users)


@pytest.fixture
def member(new_client, scope_ids):
    browser = new_client()
    login(browser, "member@example.test")
    return browser


@pytest.fixture
def mail(app, settings, clock, db_runtime):
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    from app.identity.delivery import DeliveryWorker
    from app.identity.email_transport import FakeEmailTransport

    settings.outbox_key = SecretStr(Fernet.generate_key().decode())
    transport = FakeEmailTransport()
    app.state.email_transport = transport
    return transport, DeliveryWorker(db_runtime, settings, transport, clock)
