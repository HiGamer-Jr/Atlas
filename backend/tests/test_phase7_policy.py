from inspect import signature
from uuid import UUID

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.schemas import Principal
from app.platform.policy import require_capability
from app.tenancy.models import AccessContext
from app.tenancy.schemas import AccessScope
from tests.helpers import CONTEXT_HEADER, select_context
from tests.test_organization_api import create_node


def context_values(db, header):
    row = db.scalar(
        select(AccessContext).where(AccessContext.id == UUID(header[CONTEXT_HEADER]))
    )
    return Principal(row.actor_id, row.session_id, None), AccessScope(
        row.id, row.tenant_id, row.contract_id, row.session_id, row.actor_id
    )


def test_policy_has_module_and_explicit_node_scope_switches():
    assert {"module_code", "organization_node_id"} <= set(
        signature(require_capability).parameters
    )


def test_policy_checks_capability_first_then_immediate_module_state(
    admin, scope_ids, db_runtime, monkeypatch
):
    assert "module_code" in signature(require_capability).parameters
    from app.organization import modules

    header = select_context(admin, scope_ids["contract_a"])
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        with pytest.raises(ApiError) as denied:
            require_capability(
                db, principal, scope, "finance.read", module_code="UNKNOWN"
            )
        assert denied.value.code == "CAPABILITY_DENIED"
        with pytest.raises(ApiError) as denied:
            require_capability(
                db, principal, scope, "modules.read", module_code="UNKNOWN"
            )
        assert denied.value.status == 403
        with pytest.raises(ApiError) as denied:
            require_capability(
                db, principal, scope, "modules.read", module_code="COMEX"
            )
        assert denied.value.code == "MODULE_UNAVAILABLE"
    result = admin.patch(
        "/api/contract/modules/COMEX",
        headers=header,
        json={
            "contracted": True,
            "active": True,
            "expected_version": 0,
            "module_id": None,
        },
    )
    assert result.status_code == 200
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        with pytest.raises(ApiError) as denied:
            require_capability(
                db, principal, scope, "modules.read", module_code="COMEX"
            )
        assert denied.value.code == "MODULE_UNAVAILABLE"  # unimplemented domain
    # Exercise future consumer availability through the same policy, never a fake route.
    monkeypatch.setattr(modules, "OPERATIONAL_MODULES", frozenset({"COMEX"}))
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        require_capability(db, principal, scope, "modules.read", module_code="COMEX")
    row = result.json()
    assert (
        admin.patch(
            "/api/contract/modules/COMEX",
            headers=header,
            json={
                "contracted": True,
                "active": False,
                "expected_version": 1,
                "module_id": row["id"],
            },
        ).status_code
        == 200
    )
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        with pytest.raises(ApiError) as denied:
            require_capability(
                db, principal, scope, "modules.read", module_code="COMEX"
            )
        assert denied.value.code == "MODULE_UNAVAILABLE"


def test_explicit_unit_policy_absence_denies_and_exact_scope_is_current(
    admin, member, scope_ids, db_runtime
):
    assert "organization_node_id" in signature(require_capability).parameters
    admin_scope = select_context(admin, scope_ids["contract_a"])
    node = create_node(admin, admin_scope).json()
    second = create_node(admin, admin_scope, "UNIT_B", parent_id=node["id"]).json()
    header = select_context(member, scope_ids["contract_a"])
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        with pytest.raises(ApiError) as denied:
            require_capability(
                db,
                principal,
                scope,
                "memberships.read",
                organization_node_id=UUID(node["id"]),
            )
        assert denied.value.code == "UNIT_SCOPE_DENIED"
    path = "/api/memberships/" + str(scope_ids["member_a"]) + "/unit-scope"
    assert (
        admin.put(
            path,
            headers=admin_scope,
            json={"node_ids": [node["id"]], "expected_version": 1},
        ).status_code
        == 200
    )
    header = select_context(member, scope_ids["contract_a"])
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        require_capability(
            db,
            principal,
            scope,
            "memberships.read",
            organization_node_id=UUID(node["id"]),
        )
        with pytest.raises(ApiError) as denied:
            require_capability(
                db,
                principal,
                scope,
                "memberships.read",
                organization_node_id=UUID(second["id"]),
            )
        assert denied.value.code == "UNIT_SCOPE_DENIED"
    with db_runtime.begin() as db:
        db.execute(
            text("UPDATE organization_nodes SET active=false WHERE id=:id"),
            {"id": node["id"]},
        )
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        with pytest.raises(ApiError) as denied:
            require_capability(
                db,
                principal,
                scope,
                "memberships.read",
                organization_node_id=UUID(node["id"]),
            )
        assert denied.value.code == "UNIT_SCOPE_DENIED"


def test_explicit_empty_module_code_is_denied(admin, scope_ids, db_runtime):
    header = select_context(admin, scope_ids["contract_a"])
    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        with pytest.raises(ApiError) as denied:
            require_capability(db, principal, scope, "modules.read", module_code="")
        assert denied.value.code == "MODULE_UNAVAILABLE"
