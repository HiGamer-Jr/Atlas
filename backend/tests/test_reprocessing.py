import pytest
from sqlalchemy import text

from tests.test_correction_handlers import name


def retry(admin, case):
    return admin.post(
        f"/api/processings/{case['run']}/reprocess",
        headers=case["child"],
        json=case["retry"],
    )


def test_reprocess_same_key_one_persisted_run_one_domain_effect(
    admin, processing_case, db_runtime
):
    case = processing_case
    first = retry(admin, case)
    assert first.status_code == 200
    assert first.json()["status"] == "SUCCEEDED"
    second = retry(admin, case)
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert name(db_runtime, case) == ("Reprocessed controlled node", 2)
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM processing_runs WHERE source_run_id=:id"),
                {"id": case["run"]},
            ).scalar_one()
            == 1
        )


def test_reprocess_same_key_different_command_conflicts(
    admin, processing_case, db_runtime
):
    assert retry(admin, processing_case).status_code == 200
    processing_case["retry"]["reason"] = "Changed command"
    assert retry(admin, processing_case).status_code == 409
    assert name(db_runtime, processing_case).version == 2


@pytest.mark.parametrize("status", ["PENDING", "RUNNING", "SUCCEEDED", "UNKNOWN"])
def test_default_only_failed_runs_are_eligible(
    admin, processing_case, db_runtime, status
):
    case = processing_case
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE processing_runs SET status=:status WHERE id=:id"),
            {"status": status, "id": case["run"]},
        )
    assert retry(admin, case).status_code == 409
    assert name(db_runtime, case).version == 1


@pytest.mark.parametrize("change", ["expired", "foreign", "session", "handler"])
def test_replay_always_requires_current_exact_authority(
    admin, processing_case, db_runtime, scope_ids, clock, app, change
):
    case = processing_case
    assert retry(admin, case).status_code == 200
    if change == "expired":
        clock.advance(seconds=1801)
    elif change == "foreign":
        from tests.helpers import select_context

        case["child"] = select_context(admin, scope_ids["contract_a2"])
    elif change == "session":
        with db_runtime.begin() as db:
            db.execute(
                text("UPDATE auth_sessions SET revoked_at=now() WHERE user_id=:id"),
                {"id": scope_ids["admin_user"]},
            )
    else:
        from app.grants.registry import MaintenanceActionRegistry

        app.state.maintenance_registry = MaintenanceActionRegistry()
    assert retry(admin, case).status_code in (401, 403, 404)
    assert name(db_runtime, case).version == 2


def test_reprocess_audit_failure_rolls_back_domain_and_reservation(
    admin, processing_case, db_runtime, monkeypatch
):
    from app.maintenance import processing

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(processing, "append_event", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        retry(admin, processing_case)
    assert name(db_runtime, processing_case).version == 1
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM processing_runs WHERE source_run_id=:id"),
                {"id": processing_case["run"]},
            ).scalar_one()
            == 0
        )


@pytest.mark.parametrize("missing", ["idempotency_key", "command_fingerprint"])
def test_physical_retry_constraint_requires_non_null_key_and_fingerprint(
    admin, processing_case, db_runtime, missing
):
    from uuid import UUID, uuid4

    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from app.maintenance.models import ProcessingRun

    response = retry(admin, processing_case)
    assert response.status_code == 200
    with Session(db_runtime) as db:
        existing = db.get(ProcessingRun, UUID(response.json()["id"]))
        values = {
            column.name: getattr(existing, column.name)
            for column in ProcessingRun.__table__.columns
        }
        values.update(id=uuid4(), idempotency_key="physical-null-check")
        values[missing] = None
        db.rollback()
        with pytest.raises(IntegrityError), db.begin():
            db.add(ProcessingRun(**values))
            db.flush()


def test_handler_failure_rolls_domain_back_and_persists_sanitized_failed_run(
    admin, processing_case, db_runtime, app
):
    from dataclasses import replace

    from app.grants.registry import MaintenanceActionRegistry

    action = app.state.maintenance_registry.list()[0]

    def failed(db, entity, source):
        entity.name = "Partial domain mutation"
        entity.version += 1
        db.flush()
        raise RuntimeError("sentinel-secret")

    app.state.maintenance_registry = MaintenanceActionRegistry(
        [replace(action, handler=replace(action.handler, reprocess=failed))]
    )
    response = retry(admin, processing_case)
    assert response.status_code == 200
    assert response.json()["status"] == "FAILED"
    assert response.json()["message_code"] == "HANDLER_FAILED"
    assert "sentinel-secret" not in response.text
    assert name(db_runtime, processing_case) == ("Original", 1)
    repeated = retry(admin, processing_case)
    assert repeated.json()["id"] == response.json()["id"]
    with db_runtime.connect() as db:
        event = db.execute(
            text(
                "SELECT outcome,after_state FROM audit_events WHERE action='maintenance.processing.failed' ORDER BY occurred_at DESC LIMIT 1"
            )
        ).one()
        assert event.outcome == "FAILURE"
        assert event.after_state["status"] == "FAILED"
        assert "sentinel-secret" not in str(event)


@pytest.mark.parametrize(
    "case,state",
    [
        ("tenant", "23503"),
        ("contract", "23503"),
        ("actor", "23503"),
        ("context", "23503"),
        ("action", "23503"),
        ("status", "23514"),
        ("entity_type", "23514"),
        ("fingerprint", "23514"),
        ("duplicate_key", "23505"),
        ("grant_type", "23514"),
    ],
)
def test_processing_physical_scope_actor_source_and_codes_constraints(
    admin, processing_case, db_runtime, scope_ids, case, state
):
    from uuid import UUID, uuid4

    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from app.maintenance.models import ProcessingRun

    response = retry(admin, processing_case)
    assert response.status_code == 200
    with Session(db_runtime) as db:
        existing = db.get(ProcessingRun, UUID(response.json()["id"]))
        values = {
            column.name: getattr(existing, column.name)
            for column in ProcessingRun.__table__.columns
        }
        originalkey = values["idempotency_key"]
        values.update(id=uuid4(), idempotency_key="physical-constraint")
        changes = {
            "tenant": {"tenant_id": scope_ids["tenant_b"]},
            "contract": {"contract_id": scope_ids["contract_a2"]},
            "actor": {"operator_id": scope_ids["support_user"]},
            "context": {
                "context_id": UUID(processing_case["parent"]["X-HiAtlas-Context"])
            },
            "action": {"action_code": "WRONG_SCOPE"},
            "status": {"status": "UNREGISTERED"},
            "entity_type": {"entity_type": "arbitrary_table"},
            "fingerprint": {"command_fingerprint": "invalid"},
            "duplicate_key": {"idempotency_key": originalkey},
            "grant_type": {"grant_type": "FINANCIAL_FISCAL"},
        }
        values.update(changes[case])
        db.rollback()
        with pytest.raises(IntegrityError) as error, db.begin():
            db.add(ProcessingRun(**values))
            db.flush()
        assert error.value.orig.sqlstate == state


def test_failure_audit_error_rolls_back_failed_run_and_domain(
    admin, processing_case, db_runtime, app, monkeypatch
):
    from dataclasses import replace

    from app.grants.registry import MaintenanceActionRegistry
    from app.maintenance import processing

    action = app.state.maintenance_registry.list()[0]

    def failed(db, entity, source):
        entity.name = "Partial domain mutation"
        db.flush()
        raise RuntimeError("sentinel-secret")

    app.state.maintenance_registry = MaintenanceActionRegistry(
        [replace(action, handler=replace(action.handler, reprocess=failed))]
    )

    def audit_failed(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(processing, "append_event", audit_failed)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        retry(admin, processing_case)
    assert name(db_runtime, processing_case) == ("Original", 1)
    with db_runtime.connect() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM processing_runs WHERE source_run_id=:id"),
                {"id": processing_case["run"]},
            ).scalar_one()
            == 0
        )


def test_committed_run_cannot_repeat_original_with_new_key(
    admin, processing_case, db_runtime
):
    first = retry(admin, processing_case)
    assert first.status_code == 200
    processing_case["retry"]["idempotency_key"] = "reload-new-key"
    assert retry(admin, processing_case).status_code == 409
    assert name(db_runtime, processing_case) == ("Reprocessed controlled node", 2)
    processing_case["retry"]["idempotency_key"] = "retry-01"
    assert retry(admin, processing_case).json()["id"] == first.json()["id"]


@pytest.mark.parametrize("status", ["RUNNING", "PENDING", "UNKNOWN"])
def test_original_source_with_uncertain_child_never_starts_new_key(
    admin, processing_case, db_runtime, status
):
    response = retry(admin, processing_case)
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE processing_runs SET status=:status WHERE id=:id"),
            {"status": status, "id": response.json()["id"]},
        )
    processing_case["retry"]["idempotency_key"] = "fresh-decision"
    assert retry(admin, processing_case).status_code == 409
    assert name(db_runtime, processing_case).version == 2
