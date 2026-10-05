from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.helpers import CONTEXT_HEADER, assert_internal_failure, select_context
from tests.test_grants import start


def preview(admin, case):
    return admin.post(
        "/api/maintenance/preview", headers=case["child"], json=case["payload"]
    )


def apply(admin, case, receipt):
    return admin.post(
        "/api/maintenance/corrections",
        headers=case["child"],
        json={**case["payload"], "preview_receipt": receipt},
    )


def name(db_runtime, case):
    with db_runtime.connect() as db:
        return db.execute(
            text("SELECT name,version FROM organization_nodes WHERE id=:id"),
            {"id": case["node"]},
        ).one()


def test_preview_no_domain_or_audit_mutation_and_apply_real_operator(
    admin, correction_case, db_runtime
):
    case = correction_case
    before = name(db_runtime, case)
    with db_runtime.connect() as db:
        count = db.execute(text("SELECT count(*) FROM audit_events")).scalar_one()
    result = preview(admin, case)
    assert result.status_code == 200
    assert result.json()["before"]["name"] == "Original"
    assert result.json()["after"]["name"] == "Corrected"
    assert name(db_runtime, case) == before
    with db_runtime.connect() as db:
        assert (
            db.execute(text("SELECT count(*) FROM audit_events")).scalar_one() == count
        )
    changed = apply(admin, case, result.json()["preview_receipt"])
    assert changed.status_code == 200
    assert name(db_runtime, case) == ("Corrected", 2)
    with db_runtime.connect() as db:
        audit = db.execute(
            text(
                "SELECT actor_id,actor_role,before_state,after_state FROM audit_events WHERE id=:id"
            ),
            {"id": changed.json()["audit_event_id"]},
        ).one()
        assert str(audit.actor_id) == case["grant"]["operator"]["user_id"]
        assert audit.actor_role == "PLATFORM_ADMIN"
        assert audit.before_state["name"] == "Original"
        assert audit.after_state["name"] == "Corrected"


def test_audit_failure_rolls_back_domain_change(
    admin, correction_case, db_runtime, monkeypatch
):
    from app.maintenance import corrections

    case = correction_case
    result = preview(admin, case)
    before = name(db_runtime, case)

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(corrections, "append_event", fail)
    response = apply(admin, case, result.json()["preview_receipt"])
    assert_internal_failure(response, "audit unavailable")
    assert name(db_runtime, case) == before


def test_missing_or_changed_receipt_and_concurrent_version_fail_closed(
    admin, correction_case, db_runtime
):
    case = correction_case
    result = preview(admin, case)
    assert (
        admin.post(
            "/api/maintenance/corrections", headers=case["child"], json=case["payload"]
        ).status_code
        == 422
    )
    assert apply(admin, case, "0" * 64).status_code == 409
    case["payload"]["proposed_input"]["name"] = "Another"
    assert apply(admin, case, result.json()["preview_receipt"]).status_code == 409
    case["payload"]["proposed_input"]["name"] = "Corrected"
    with db_runtime.begin() as db:
        db.execute(
            text(
                "UPDATE organization_nodes SET name='Concurrent',version=2 WHERE id=:id"
            ),
            {"id": case["node"]},
        )
    assert apply(admin, case, result.json()["preview_receipt"]).status_code == 409
    assert name(db_runtime, case) == ("Concurrent", 2)


@pytest.mark.parametrize(
    "field",
    [
        "sql",
        "table",
        "column",
        "actor",
        "before",
        "tenant_id",
        "contract_id",
        "domain_command",
    ],
)
@pytest.mark.parametrize("location", ["envelope", "input"])
def test_extra_authority_and_arbitrary_payload_are_rejected(
    admin, correction_case, field, location
):
    case = correction_case
    target = (
        case["payload"] if location == "envelope" else case["payload"]["proposed_input"]
    )
    target[field] = "sentinel-secret"
    result = preview(admin, case)
    assert result.status_code == 422
    assert "sentinel-secret" not in result.text


@pytest.mark.parametrize(
    "payload_change",
    [{"action_code": "UNKNOWN"}, {"expected_version": 2}, {"entity_id": str(uuid4())}],
)
def test_unknown_stale_or_foreign_entity_cannot_mutate(
    admin, correction_case, payload_change, db_runtime
):
    case = correction_case
    case["payload"].update(payload_change)
    assert preview(admin, case).status_code in (403, 404, 409)
    assert name(db_runtime, case) == ("Original", 1)


@pytest.mark.parametrize("mode", ["parent", "support", "financial", "expired"])
def test_only_current_exact_maintenance_grant_can_preview(
    admin, support, correction_case, scope_ids, clock, mode
):
    case = correction_case
    browser = admin
    if mode == "parent":
        case["child"] = case["parent"]
    elif mode == "support":
        browser = support
        case["child"] = select_context(support, scope_ids["contract_a"])
    elif mode == "financial":
        parent = select_context(admin, scope_ids["contract_a"])
        response = start(admin, scope_ids, parent)[1]
        case["child"] = {CONTEXT_HEADER: response.json()["context_id"]}
    else:
        clock.advance(seconds=1801)
    assert preview(browser, case).status_code == 403


def test_preview_flush_cannot_persist_any_domain_mutation(
    admin, correction_case, db_runtime, app
):
    from dataclasses import replace

    from sqlalchemy.orm import object_session

    from app.grants.registry import MaintenanceActionRegistry
    from tests.fixtures.correction_domain import preview as clean_preview

    action = app.state.maintenance_registry.list()[0]

    def broken_preview(entity, command):
        result = clean_preview(entity, command)
        entity.name = "Unexpected persistent preview mutation"
        object_session(entity).flush()
        return result

    app.state.maintenance_registry = MaintenanceActionRegistry(
        [replace(action, handler=replace(action.handler, preview=broken_preview))]
    )
    try:
        preview(admin, correction_case)
    except RuntimeError:
        pass
    assert name(db_runtime, correction_case) == ("Original", 1)


def test_changed_displayed_after_same_version_requires_new_preview(
    admin, correction_case, db_runtime, app
):
    from dataclasses import replace

    from app.grants.registry import MaintenanceActionRegistry
    from tests.fixtures.correction_domain import snapshot

    response = preview(admin, correction_case)
    action = app.state.maintenance_registry.list()[0]

    def changed_preview(entity, command):
        return snapshot(entity).model_copy(
            update={"name": "Unexpected new result", "version": entity.version + 1}
        )

    def changed_apply(entity, command):
        entity.name = "Unexpected new result"
        entity.version += 1

    app.state.maintenance_registry = MaintenanceActionRegistry(
        [
            replace(
                action,
                handler=replace(
                    action.handler, preview=changed_preview, apply=changed_apply
                ),
            )
        ]
    )
    assert (
        apply(admin, correction_case, response.json()["preview_receipt"]).status_code
        == 409
    )
    assert name(db_runtime, correction_case) == ("Original", 1)


@pytest.mark.parametrize("key", ["contract_a2", "contract_b"])
def test_real_foreign_scoped_entity_cannot_preview_or_read(
    admin, correction_case, scope_ids, db_runtime, key
):
    from uuid import uuid4

    node = uuid4()
    tenant = scope_ids["tenant_a"] if key == "contract_a2" else scope_ids["tenant_b"]
    with db_runtime.begin() as db:
        db.execute(
            text(
                "INSERT INTO organization_nodes(id,tenant_id,contract_id,kind,name,code) VALUES(:id,:tenant,:contract,'COMPANY','Foreign','PH10-FOREIGN')"
            ),
            {"id": node, "tenant": tenant, "contract": scope_ids[key]},
        )
    correction_case["payload"]["entity_id"] = str(node)
    assert preview(admin, correction_case).status_code == 403
    assert (
        admin.get(
            f"/api/maintenance/entities/FIXTURE_NODE_RENAME/{node}",
            headers=correction_case["parent"],
        ).status_code
        == 404
    )


def test_declared_operational_module_metadata_fails_closed_without_grant(
    admin, correction_case, app
):
    from dataclasses import replace

    from app.grants.registry import MaintenanceActionRegistry

    action = app.state.maintenance_registry.list()[0]
    app.state.maintenance_registry = MaintenanceActionRegistry(
        [replace(action, module_code="FINANCE")]
    )
    response = admin.get("/api/maintenance", headers=correction_case["parent"])
    assert response.status_code == 200 and response.json()["items"] == []
    assert (
        admin.get(
            f"/api/maintenance/entities/FIXTURE_NODE_RENAME/{correction_case['node']}",
            headers=correction_case["parent"],
        ).status_code
        == 403
    )


def test_malformed_json_is_sanitized_validation_error(admin, correction_case):
    result = admin.post(
        "/api/maintenance/preview",
        headers={**correction_case["child"], "Content-Type": "application/json"},
        content="{invalid-sentinel-secret",
    )
    assert result.status_code == 422
    assert "invalid-sentinel-secret" not in result.text
