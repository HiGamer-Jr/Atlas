from app.core.config import Settings
from app.main import create_app


def test_grant_duration_is_centrally_configured():
    assert "grant_seconds" in Settings.model_fields
    assert Settings().grant_seconds == 1800


def test_closed_grant_control_routes_exist_without_operational_handlers():
    application = create_app(Settings())
    paths = application.openapi()["paths"]
    assert "/api/grants" in paths
    assert "/api/grants/context" in paths
    assert "/api/grants/maintenance-actions" in paths
    assert "/api/grants/{grant_id}/end" in paths


def test_maintenance_scope_rejects_duplicate_action_for_different_entities():
    from uuid import uuid4

    import pytest
    from pydantic import ValidationError

    from app.grants.schemas import GrantStart

    with pytest.raises(ValidationError):
        GrantStart(
            grant_type="MAINTENANCE",
            reason="Verificação controlada",
            reference="INC-1",
            scopes=[
                {
                    "action_code": "CONTROLLED_ACTION",
                    "entity_type": "organization_node",
                    "entity_id": uuid4(),
                },
                {
                    "action_code": "CONTROLLED_ACTION",
                    "entity_type": "organization_node",
                    "entity_id": uuid4(),
                },
            ],
        )
