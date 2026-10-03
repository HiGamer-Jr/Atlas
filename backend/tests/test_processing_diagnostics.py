from sqlalchemy import text

from tests.helpers import select_context


def test_diagnostics_allowlist_no_reason_fingerprint_or_internal_payload(
    admin, processing_case, db_runtime
):
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE processing_runs SET reason='sentinel-secret' WHERE id=:id"),
            {"id": processing_case["run"]},
        )
    response = admin.get("/api/processings", headers=processing_case["parent"])
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["request_id"]
    assert set(item) == {
        "id",
        "action_code",
        "status",
        "result_code",
        "message_code",
        "request_id",
        "entity_id",
        "source_run_id",
        "created_at",
        "started_at",
        "finished_at",
        "version",
        "can_reprocess",
    }
    assert "sentinel-secret" not in response.text


def test_support_only_reduced_non_sensitive_diagnostics(
    support, scope_ids, processing_case, db_runtime
):
    scope = select_context(support, scope_ids["contract_a"])
    response = support.get("/api/processings", headers=scope)
    assert response.status_code == 200
    assert response.json()["items"][0]["entity_id"] is None
    assert response.json()["items"][0]["can_reprocess"] is False
    assert response.json()["items"][0]["request_id"]
    assert support.get("/api/maintenance", headers=scope).status_code == 403
    assert (
        support.post(
            f"/api/processings/{processing_case['run']}/reprocess",
            headers=scope,
            json=processing_case["retry"],
        ).status_code
        == 403
    )
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE processing_runs SET classification='SENSITIVE' WHERE id=:id"),
            {"id": processing_case["run"]},
        )
    assert support.get("/api/processings", headers=scope).json()["total"] == 0
    assert (
        support.get(
            f"/api/processings/{processing_case['run']}", headers=scope
        ).status_code
        == 404
    )


def test_foreign_context_cannot_list_or_read_run(admin, scope_ids, processing_case):
    for key in ("contract_a2", "contract_b"):
        scope = select_context(admin, scope_ids[key])
        assert admin.get("/api/processings", headers=scope).json()["total"] == 0
        assert (
            admin.get(
                f"/api/processings/{processing_case['run']}", headers=scope
            ).status_code
            == 404
        )


def test_support_unknown_and_financial_handler_hidden_even_when_stored_standard(
    support, scope_ids, processing_case, db_runtime, app
):
    from dataclasses import replace

    from app.grants.registry import MaintenanceActionRegistry

    scope = select_context(support, scope_ids["contract_a"])
    action = app.state.maintenance_registry.list()[0]
    app.state.maintenance_registry = MaintenanceActionRegistry(
        [replace(action, module_code="FINANCE", capability="finance.read")]
    )
    assert support.get("/api/processings", headers=scope).json()["total"] == 0
    assert (
        support.get(
            f"/api/processings/{processing_case['run']}", headers=scope
        ).status_code
        == 404
    )
    app.state.maintenance_registry = MaintenanceActionRegistry()
    assert support.get("/api/processings", headers=scope).json()["total"] == 0
    assert (
        support.get(
            f"/api/processings/{processing_case['run']}", headers=scope
        ).status_code
        == 404
    )


def test_read_only_support_workspace_can_only_read_reduced_diagnostics(
    support, scope_ids, processing_case
):
    from tests.helpers import CONTEXT_HEADER
    from tests.test_support_sessions import start

    response = start(support, scope_ids)[1]
    assert response.status_code == 201
    scope = {CONTEXT_HEADER: response.json()["context_id"]}
    diagnostics = support.get("/api/processings", headers=scope)
    assert diagnostics.status_code == 200
    assert diagnostics.json()["items"][0]["entity_id"] is None
    assert diagnostics.json()["items"][0]["can_reprocess"] is False
    assert support.get("/api/maintenance", headers=scope).status_code == 403
    assert (
        support.post(
            "/api/maintenance/preview", headers=scope, json=processing_case["payload"]
        ).status_code
        == 403
    )
    assert (
        support.post(
            f"/api/processings/{processing_case['run']}/reprocess",
            headers=scope,
            json=processing_case["retry"],
        ).status_code
        == 403
    )
