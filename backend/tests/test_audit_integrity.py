from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def bootstrap_event(user_id, **overrides):
    from app.audit.schemas import AuditInput, IdentitySnapshot

    return AuditInput(
        actor_id=user_id,
        actor_role="PLATFORM_ADMIN",
        action="identity.bootstrap",
        entity_type="user",
        entity_id=user_id,
        after=IdentitySnapshot(
            user_id=user_id, active=True, blocked=False, platform_role="PLATFORM_ADMIN"
        ),
        **overrides,
    )


def seed_user(db):
    user_id = uuid4()
    db.execute(
        text(
            "INSERT INTO users (id,email_normalized,display_name) VALUES (:id,'audit@example.test','Actor')"
        ),
        {"id": user_id},
    )
    return user_id


def test_append_event_persists_without_committing(db_runtime):
    from app.audit.models import AuditEvent
    from app.audit.service import append_event

    with Session(db_runtime) as db, db.begin():
        actor = seed_user(db)
        event_id = append_event(db, bootstrap_event(actor))
        row = db.get(AuditEvent, event_id)
        assert row is not None
        assert row.after_state["platform_role"] == "PLATFORM_ADMIN"
        assert row.before_state is None
        assert row.actor_id == actor
        assert row.occurred_at.tzinfo is not None
        with db_runtime.connect() as other:
            assert (
                other.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
                == 0
            )
    with db_runtime.connect() as other:
        assert (
            other.execute(text("SELECT count(*) FROM audit_events")).scalar_one() == 1
        )


def test_audit_fk_failure_rolls_back_business_change(db_runtime):
    from app.audit.service import append_event

    tenant = uuid4()
    with pytest.raises(IntegrityError), Session(db_runtime) as db, db.begin():
        db.execute(
            text("INSERT INTO tenants (id,name) VALUES (:id,'Rollback')"),
            {"id": tenant},
        )
        append_event(db, bootstrap_event(uuid4()))
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM tenants WHERE id=:id"), {"id": tenant}
            ).scalar_one()
            == 0
        )


def test_audit_service_captures_environment_from_contract(db_runtime):
    from app.audit.models import AuditEvent
    from app.audit.service import append_event

    with Session(db_runtime) as db, db.begin():
        actor, tenant, contract = seed_user(db), uuid4(), uuid4()
        db.execute(
            text("INSERT INTO tenants (id,name) VALUES (:id,'Tenant')"), {"id": tenant}
        )
        db.execute(
            text(
                "INSERT INTO contracts (id,tenant_id,code,name,environment) "
                "VALUES (:id,:tenant,'AUD-001','Contract','STAGING')"
            ),
            {"id": contract, "tenant": tenant},
        )
        event_id = append_event(
            db, bootstrap_event(actor, tenant_id=tenant, contract_id=contract)
        )
        assert (
            db.scalar(select(AuditEvent.environment).where(AuditEvent.id == event_id))
            == "STAGING"
        )


@pytest.mark.parametrize("field", ["password", "password_hash", "token", "secret"])
def test_audit_snapshot_rejects_credentials(field):
    from app.audit.schemas import IdentitySnapshot

    with pytest.raises(ValidationError) as error:
        IdentitySnapshot(
            user_id=uuid4(), active=True, blocked=False, **{field: "sentinel-secret"}
        )
    assert "sentinel-secret" not in str(error.value)


@pytest.mark.parametrize(
    "extra",
    [
        {"action": "execute.sql"},
        {"occurred_at": "2026-01-01"},
        {"environment": "PRODUCTION"},
        {"tenant_id": uuid4()},
    ],
)
def test_audit_rejects_unknown_action_or_forged_metadata(extra):
    from app.audit.schemas import AuditInput

    payload = {
        "actor_id": uuid4(),
        "actor_role": "PLATFORM_ADMIN",
        "action": "identity.bootstrap",
        "entity_type": "user",
        "entity_id": uuid4(),
    }
    payload.update(extra)
    with pytest.raises(ValidationError):
        AuditInput(**payload)


def test_runtime_can_append_access_events(db):
    event = uuid4()
    db.execute(
        text(
            "INSERT INTO access_events (id,action,outcome,request_id) "
            "VALUES (:id,'auth.failed','DENIED',:request)"
        ),
        {"id": event, "request": uuid4()},
    )
    assert (
        db.execute(
            text("SELECT outcome FROM access_events WHERE id=:id"), {"id": event}
        ).scalar_one()
        == "DENIED"
    )
