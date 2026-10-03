import pytest

from app.core.config import Settings
from app.grants.registry import MaintenanceAction, MaintenanceActionRegistry
from app.main import create_app


def test_untyped_mapping_handler_cannot_register_executable_maintenance():
    action = MaintenanceAction(
        "UNSAFE",
        "Unsafe",
        "organization_node",
        "maintenance.authorize",
        "PROCUREMENT",
        lambda *a: True,
        lambda *a: True,
        {"sql": "unsafe"},
    )
    with pytest.raises(ValueError, match="typed"):
        MaintenanceActionRegistry([action])


def test_normal_app_exposes_maintenance_boundary_but_no_fixture_route():
    app = create_app(Settings(environment="test"))
    paths = set(app.openapi()["paths"])
    assert "/api/maintenance/preview" in paths
    assert "/api/maintenance/entities/{action_code}/{entity_id}" in paths
    assert "/api/processings/{run_id}/reprocess" in paths
    assert all("fixture" not in path for path in paths)
    assert app.state.maintenance_registry.list() == ()


@pytest.mark.parametrize(
    "value", ["line\nbreak", "line\tbreak", "nul\x00byte", "\u202eoverride", 12]
)
def test_reason_rejects_controls_and_non_text(value):
    from pydantic import ValidationError

    from app.maintenance.schemas import ReasonCommand

    with pytest.raises(ValidationError):
        ReasonCommand(reason=value)


def test_reason_normalizes_unicode_and_trims_reference():
    from app.maintenance.schemas import ReasonCommand

    value = ReasonCommand(reason="  Cafe\u0301 auditado  ", reference="  SUP-1  ")
    assert value.reason == "Café auditado"
    assert value.reference == "SUP-1"


@pytest.mark.parametrize("annotation", ["any", "list-any", "dict-any"])
def test_registered_handler_rejects_open_nested_payload(annotation):
    from typing import Any

    from pydantic import create_model

    from app.maintenance.registry import closed_schema
    from app.maintenance.schemas import ClosedModel

    types = {"any": Any, "list-any": list[Any], "dict-any": dict[str, Any]}
    schema = create_model(
        "OpenNested", __base__=ClosedModel, payload=(types[annotation], ...)
    )
    with pytest.raises(ValueError, match="closed"):
        closed_schema(schema)


def test_registered_handler_accepts_concrete_closed_nested_model():
    from typing import Literal

    from app.maintenance.registry import closed_schema
    from app.maintenance.schemas import ClosedModel

    class Child(ClosedModel):
        code: Literal["A", "B"]

    class Parent(ClosedModel):
        children: list[Child]

    closed_schema(Parent)


def test_disabled_registered_action_fails_closed():
    from app.core.errors import ApiError

    action = MaintenanceAction(
        "DISABLED",
        "Disabled",
        "organization_node",
        "maintenance.authorize",
        "PROCUREMENT",
        lambda *args: True,
        lambda *args: True,
    )
    object.__setattr__(action, "enabled", False)
    registry = MaintenanceActionRegistry([action])
    with pytest.raises(ApiError):
        registry.get("DISABLED")
    assert registry.list() == ()
