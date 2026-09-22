from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

TABLES = {
    "users",
    "platform_role_assignments",
    "tenants",
    "contracts",
    "audit_events",
    "access_events",
}


def test_migration_creates_foundation_tables(db_runtime):
    assert TABLES <= set(inspect(db_runtime).get_table_names())


def test_contract_cannot_reference_missing_tenant(db):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO contracts (id, tenant_id, code, name, environment) "
                "VALUES (:id,:tenant,'TEST-001','Contract','TEST')"
            ),
            {"id": uuid4(), "tenant": uuid4()},
        )


def test_valid_contract_persists_with_defaults(db):
    tenant, contract = uuid4(), uuid4()
    db.execute(
        text("INSERT INTO tenants (id,name) VALUES (:id,'Tenant')"), {"id": tenant}
    )
    db.execute(
        text(
            "INSERT INTO contracts (id,tenant_id,code,name,environment) "
            "VALUES (:id,:tenant,'TEST-002','Contract','TEST')"
        ),
        {"id": contract, "tenant": tenant},
    )
    row = db.execute(
        text("SELECT active, version, created_at FROM contracts WHERE id=:id"),
        {"id": contract},
    ).one()
    assert row.active is True
    assert row.version == 1
    assert row.created_at.tzinfo is not None


def test_normalized_email_is_unique(db):
    db.execute(
        text(
            "INSERT INTO users (id,email_normalized,display_name) "
            "VALUES (:id,'user@example.test','One')"
        ),
        {"id": uuid4()},
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO users (id,email_normalized,display_name) "
                "VALUES (:id,'user@example.test','Two')"
            ),
            {"id": uuid4()},
        )


@pytest.mark.parametrize("email", [" User@example.test", "USER@example.test", ""])
def test_database_rejects_unnormalized_email(db, email):
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO users (id,email_normalized,display_name) "
                "VALUES (:id,:email,'Name')"
            ),
            {"id": uuid4(), "email": email},
        )


def test_internal_role_is_closed_and_unique(db):
    user = uuid4()
    db.execute(
        text(
            "INSERT INTO users (id,email_normalized,display_name) "
            "VALUES (:id,'operator@example.test','Operator')"
        ),
        {"id": user},
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO platform_role_assignments (user_id,role) VALUES (:id,'DIRECTOR')"
            ),
            {"id": user},
        )
    db.execute(
        text(
            "INSERT INTO platform_role_assignments (user_id,role) VALUES (:id,'PLATFORM_SUPPORT')"
        ),
        {"id": user},
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO platform_role_assignments (user_id,role) VALUES (:id,'PLATFORM_ADMIN')"
            ),
            {"id": user},
        )


@pytest.mark.parametrize("table", ["audit_events", "access_events"])
def test_event_cannot_mix_tenant_and_contract(db, table):
    first, second, contract = uuid4(), uuid4(), uuid4()
    for tenant in (first, second):
        db.execute(
            text("INSERT INTO tenants (id,name) VALUES (:id,'Tenant')"), {"id": tenant}
        )
    db.execute(
        text(
            "INSERT INTO contracts (id,tenant_id,code,name,environment) "
            "VALUES (:id,:tenant,'TEST-003','Contract','TEST')"
        ),
        {"id": contract, "tenant": first},
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                f"INSERT INTO {table} (id,tenant_id,contract_id,action,outcome,request_id) "
                "VALUES (:id,:tenant,:contract,'identity.bootstrap','SUCCESS',:request)"
            ),
            {"id": uuid4(), "tenant": second, "contract": contract, "request": uuid4()},
        )


@pytest.mark.parametrize("table", ["audit_events", "access_events"])
def test_event_rejects_partial_context(db, table):
    tenant = uuid4()
    db.execute(
        text("INSERT INTO tenants (id,name) VALUES (:id,'Tenant')"), {"id": tenant}
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                f"INSERT INTO {table} (id,tenant_id,action,outcome,request_id) "
                "VALUES (:id,:tenant,'identity.bootstrap','SUCCESS',:request)"
            ),
            {"id": uuid4(), "tenant": tenant, "request": uuid4()},
        )


def test_contract_code_and_environment_are_validated(db):
    tenant = uuid4()
    db.execute(
        text("INSERT INTO tenants (id,name) VALUES (:id,'Tenant')"), {"id": tenant}
    )
    for code, environment in [("", "TEST"), ("TEST-004", "ANYWHERE")]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(
                text(
                    "INSERT INTO contracts (id,tenant_id,code,name,environment) "
                    "VALUES (:id,:tenant,:code,'Contract',:env)"
                ),
                {"id": uuid4(), "tenant": tenant, "code": code, "env": environment},
            )


def test_models_match_migrated_tables(db_runtime):
    # Inspect observable migrated shape against the ORM used by requests.
    from app.db.models import Base

    inspector = inspect(db_runtime)
    for name in TABLES:
        assert set(Base.metadata.tables[name].columns.keys()) == {
            column["name"] for column in inspector.get_columns(name)
        }
