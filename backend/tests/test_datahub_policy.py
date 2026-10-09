from importlib.util import find_spec
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.schemas import Principal
from app.platform.capabilities import CATALOG, INTERNAL_GRANTS
from app.tenancy.models import AccessContext
from app.tenancy.schemas import AccessScope
from tests.helpers import select_context

CAPS = (
    "datahub.read",
    "datahub.template.download",
    "datahub.import",
    "datahub.export",
    "datahub.products.read",
    "datahub.products.import",
    "datahub.products.export",
    "datahub.partners.read",
    "datahub.partners.import",
    "datahub.demands.read",
    "datahub.demands.import",
    "datahub.stock_positions.read",
    "datahub.stock_positions.import",
)


def authorize():
    assert find_spec("app.datahub.policy"), "Contextual Data Hub policy missing"
    from app.datahub.policy import authorize_selection

    return authorize_selection


def context_values(db, header):
    row = db.scalar(
        select(AccessContext).where(
            AccessContext.id == UUID(header["X-HiAtlas-Context"])
        )
    )
    return Principal(row.actor_id, row.session_id, None), AccessScope(
        row.id, row.tenant_id, row.contract_id, row.session_id, row.actor_id
    )


def invoke(engine, header, template="COORDENACAO", operation="IMPORT", nodes=()):
    with Session(engine) as db, db.begin():
        principal, scope = context_values(db, header)
        return authorize()(db, principal, scope, operation, template, 1, nodes)


@pytest.fixture
def configured(db_runtime, scope_ids):
    ids = scope_ids
    with db_runtime.begin() as c:
        for module in ("DATAHUB", "PROCUREMENT", "COMEX", "INVENTORY", "FINANCE"):
            c.execute(
                text(
                    "INSERT INTO contract_modules (tenant_id,contract_id,code,contracted,active) VALUES (:t,:c,:code,true,true)"
                ),
                {"t": ids["tenant_a"], "c": ids["contract_a"], "code": module},
            )
        ids["datahub_unit"] = uuid4()
        c.execute(
            text(
                "INSERT INTO organization_nodes (id,tenant_id,contract_id,kind,name,code) VALUES (:n,:t,:c,'STORE','Unidade sintética','DH-UNIT')"
            ),
            {"n": ids["datahub_unit"], "t": ids["tenant_a"], "c": ids["contract_a"]},
        )
        c.execute(
            text(
                "INSERT INTO membership_unit_scopes (tenant_id,contract_id,membership_id,node_id) VALUES (:t,:c,:m,:n)"
            ),
            {
                "t": ids["tenant_a"],
                "c": ids["contract_a"],
                "m": ids["member_a"],
                "n": ids["datahub_unit"],
            },
        )
    return ids


def grant_caps(engine, ids):
    assert set(CAPS) <= CATALOG.keys(), "Closed Data Hub tenant capabilities missing"
    with engine.begin() as c:
        for cap in CAPS:
            c.execute(
                text(
                    "INSERT INTO tenant_role_permissions (tenant_id,contract_id,role_id,capability) VALUES (:t,:c,:role,:cap)"
                ),
                {
                    "t": ids["tenant_a"],
                    "c": ids["contract_a"],
                    "role": ids["role_basic"],
                    "cap": cap,
                },
            )


def test_admin_role_alone_never_grants_datahub_access(admin, configured, db_runtime):
    header = select_context(admin, configured["contract_a"])
    with pytest.raises(ApiError) as e:
        invoke(db_runtime, header)
    assert e.value.status == 403
    assert not any(
        cap.startswith("datahub.") for cap in INTERNAL_GRANTS["PLATFORM_ADMIN"]
    )


def test_profile_name_never_grants_access(member, configured, db_runtime):
    header = select_context(member, configured["contract_a"])
    with db_runtime.begin() as c:
        c.execute(
            text("UPDATE tenant_roles SET name='Comprador Nacional' WHERE id=:id"),
            {"id": configured["role_basic"]},
        )
    with pytest.raises(ApiError) as e:
        invoke(db_runtime, header, "COMPRADOR_NACIONAL")
    assert e.value.status == 403


def test_explicit_tenant_capabilities_allow_only_selected_datasets(
    member, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])
    selection = invoke(db_runtime, header, "COMPRADOR_NACIONAL")
    assert selection.datasets == ("PRODUCTS", "PARTNERS", "DEMANDS")
    assert selection.role_name == "role_basic"


def test_financial_template_fails_closed(member, configured, db_runtime):
    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])
    with pytest.raises(ApiError) as e:
        invoke(db_runtime, header, "FINANCEIRO")
    assert e.value.status == 403


def test_support_cannot_import_even_with_tenant_membership(
    support, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    header = select_context(support, configured["contract_a"])
    with pytest.raises(ApiError) as e:
        invoke(db_runtime, header)
    assert e.value.status == 403


def test_admin_needs_explicit_tenant_membership_and_capabilities(
    admin, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    with db_runtime.begin() as c:
        c.execute(
            text(
                "INSERT INTO memberships (id,user_id,tenant_id,contract_id,role_id) VALUES (:id,:user,:t,:c,:role)"
            ),
            {
                "id": uuid4(),
                "user": configured["admin_user"],
                "t": configured["tenant_a"],
                "c": configured["contract_a"],
                "role": configured["role_basic"],
            },
        )
        c.execute(
            text(
                "INSERT INTO membership_unit_scopes (tenant_id,contract_id,membership_id,node_id) SELECT tenant_id,contract_id,id,:n FROM memberships WHERE user_id=:u AND contract_id=:c"
            ),
            {
                "n": configured["datahub_unit"],
                "u": configured["admin_user"],
                "c": configured["contract_a"],
            },
        )
    header = select_context(admin, configured["contract_a"])
    assert invoke(db_runtime, header, "COMPRADOR_NACIONAL").datasets == (
        "PRODUCTS",
        "PARTNERS",
        "DEMANDS",
    )
    with db_runtime.begin() as c:
        c.execute(
            text("UPDATE memberships SET blocked=true WHERE user_id=:user"),
            {"user": configured["admin_user"]},
        )
    with pytest.raises(ApiError):
        invoke(db_runtime, header)


def test_inventory_information_does_not_enable_inventory_operations(
    member, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])
    from app.platform.policy import require_capability

    with Session(db_runtime) as db, db.begin():
        principal, scope = context_values(db, header)
        with pytest.raises(ApiError) as e:
            require_capability(
                db, principal, scope, "datahub.read", module_code="INVENTORY"
            )
        assert e.value.code == "MODULE_UNAVAILABLE"


@pytest.mark.parametrize("kind", ["foreign", "inactive", "not_assigned"])
def test_foreign_or_inactive_unit_is_hidden(member, configured, db_runtime, kind):
    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])
    unit = uuid4()
    with db_runtime.begin() as c:
        c.execute(
            text(
                "INSERT INTO organization_nodes (id,tenant_id,contract_id,kind,name,code,active) VALUES (:id,:t,:c,'STORE','Loja sintética','STORE1',:active)"
            ),
            {
                "id": unit,
                "t": configured["tenant_a"],
                "c": configured["contract_a2"]
                if kind == "foreign"
                else configured["contract_a"],
                "active": kind != "inactive",
            },
        )
        if kind == "inactive":
            c.execute(
                text(
                    "INSERT INTO membership_unit_scopes (tenant_id,contract_id,membership_id,node_id) VALUES (:t,:c,:m,:n)"
                ),
                {
                    "t": configured["tenant_a"],
                    "c": configured["contract_a"],
                    "m": configured["member_a"],
                    "n": unit,
                },
            )
    with pytest.raises(ApiError) as e:
        invoke(db_runtime, header, nodes=(unit,))
    assert e.value.status == 404


@pytest.mark.parametrize("module", ["DATAHUB", "PROCUREMENT"])
def test_module_deactivation_removes_information_immediately(
    member, configured, db_runtime, module
):
    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])
    assert "DEMANDS" in invoke(db_runtime, header, "COMPRADOR_NACIONAL").datasets
    with db_runtime.begin() as c:
        c.execute(
            text(
                "UPDATE contract_modules SET active=false WHERE code=:code AND contract_id=:c"
            ),
            {"code": module, "c": configured["contract_a"]},
        )
    if module == "DATAHUB":
        with pytest.raises(ApiError) as error:
            invoke(db_runtime, header)
        assert error.value.status == 403
    else:
        assert invoke(db_runtime, header, "COMPRADOR_NACIONAL").datasets == (
            "PRODUCTS",
            "PARTNERS",
        )


def test_import_permission_does_not_grant_read_projection(
    member, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])
    with db_runtime.begin() as c:
        c.execute(
            text(
                "UPDATE tenant_role_permissions SET active=false WHERE role_id=:r AND capability LIKE 'datahub.%.read'"
            ),
            {"r": configured["role_basic"]},
        )
    with pytest.raises(ApiError) as error:
        invoke(db_runtime, header)
    assert error.value.code == "DATASET_DENIED"


@pytest.mark.parametrize("contract", ["contract_a2", "contract_b"])
def test_contract_capabilities_never_cross_contexts(
    member, admin, configured, db_runtime, contract
):
    grant_caps(db_runtime, configured)
    if contract == "contract_b":
        with db_runtime.begin() as c:
            c.execute(
                text(
                    "INSERT INTO memberships (user_id,tenant_id,contract_id,role_id) VALUES (:u,:t,:c,:r)"
                ),
                {
                    "u": configured["member_user"],
                    "t": configured["tenant_b"],
                    "c": configured["contract_b"],
                    "r": configured["role_b"],
                },
            )
    header = select_context(member, configured[contract])
    with pytest.raises(ApiError) as error:
        invoke(db_runtime, header)
    assert error.value.status == 403


def test_unassigned_scope_does_not_become_contract_wide(member, configured, db_runtime):
    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])
    with db_runtime.begin() as c:
        c.execute(
            text(
                "UPDATE membership_unit_scopes SET active=false WHERE membership_id=:m"
            ),
            {"m": configured["member_a"]},
        )
    result = invoke(db_runtime, header, "COMPRADOR_NACIONAL")
    assert result.units == ()
    assert result.datasets == ("PRODUCTS", "PARTNERS")


def test_sensitive_history_remains_ineligible_after_permission_removal(
    member, configured, db_runtime
):
    from app.platform.policy import role_support_eligible
    from app.tenancy.models import TenantRole

    grant_caps(db_runtime, configured)
    with db_runtime.begin() as c:
        c.execute(
            text(
                "UPDATE tenant_roles SET sensitivity_locked=true, support_assignable=true WHERE id=:r"
            ),
            {"r": configured["role_basic"]},
        )
    with Session(db_runtime) as db:
        role = db.get(TenantRole, configured["role_basic"])
        assert not role_support_eligible(role, CAPS)
    assert CATALOG["datahub.financial_forecasts.read"].sensitive
    assert not CATALOG["datahub.financial_forecasts.read"].tenant_enabled


@pytest.mark.parametrize("cause", ["module_deactivated", "context_expired"])
def test_waiting_module_rechecks_state_and_time(
    member, configured, db_runtime, clock, cause
):
    from concurrent.futures import ThreadPoolExecutor

    from tests.test_phase7_races import wait_for_lock

    grant_caps(db_runtime, configured)
    header = select_context(member, configured["contract_a"])

    def waiting():
        with Session(db_runtime) as db, db.begin():
            db.info["clock"] = clock
            principal, scope = context_values(db, header)
            return authorize()(
                db, principal, scope, "IMPORT", "COMPRADOR_NACIONAL", 1, ()
            )

    with db_runtime.connect() as holder:
        tx = holder.begin()
        holder.execute(
            text(
                "SELECT id FROM contract_modules WHERE contract_id=:c AND code='DATAHUB' FOR UPDATE"
            ),
            {"c": configured["contract_a"]},
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(waiting)
            try:
                wait_for_lock(db_runtime)
                if cause == "module_deactivated":
                    holder.execute(
                        text(
                            "UPDATE contract_modules SET active=false WHERE contract_id=:c AND code='DATAHUB'"
                        ),
                        {"c": configured["contract_a"]},
                    )
                else:
                    clock.advance(seconds=1801)
                tx.commit()
                with pytest.raises(ApiError) as error:
                    future.result(timeout=20)
                assert error.value.status in (401, 403)
            finally:
                if tx.is_active:
                    tx.rollback()


def test_permission_catalog_constraint_rejects_arbitrary_datahub_code(
    db_runtime, configured
):
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError) as error, db_runtime.begin() as c:
        c.execute(
            text(
                "INSERT INTO tenant_role_permissions (tenant_id,contract_id,role_id,capability) VALUES (:t,:c,:r,'datahub.admin.bypass')"
            ),
            {
                "t": configured["tenant_a"],
                "c": configured["contract_a"],
                "r": configured["role_basic"],
            },
        )
    assert error.value.orig.sqlstate == "23514"


def test_scope_migration_roundtrip_and_unit_foreign_key(
    db_owner, db_runtime, migration_config
):
    from sqlalchemy import inspect

    from alembic import command

    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0011")
            assert "unit_id" not in {
                c["name"] for c in inspect(conn).get_columns("datahub_import_rows")
            }
            command.upgrade(migration_config, "head")
            fks = inspect(conn).get_foreign_keys("datahub_import_rows")
            assert any(
                f["name"] == "fk_dh_row_unit"
                and f["constrained_columns"] == ["tenant_id", "contract_id", "unit_id"]
                for f in fks
            )
    finally:
        migration_config.attributes.pop("connection", None)


def test_explicit_all_policy_without_grants_uses_real_nodes(
    member, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    with db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE memberships SET unit_scope_mode='ALL' WHERE id=:m"),
            {"m": configured["member_a"]},
        )
        conn.execute(
            text(
                "UPDATE membership_unit_scopes SET active=false WHERE membership_id=:m"
            ),
            {"m": configured["member_a"]},
        )
    headers = select_context(member, configured["contract_a"])
    result = invoke(db_runtime, headers, "COMPRADOR_NACIONAL")
    assert {unit.id for unit in result.units} == {configured["datahub_unit"]}
    with db_runtime.begin() as conn:
        conn.execute(
            text("UPDATE memberships SET unit_scope_mode='RESTRICTED' WHERE id=:m"),
            {"m": configured["member_a"]},
        )
    with pytest.raises(ApiError) as error:
        invoke(
            db_runtime,
            headers,
            "COMPRADOR_NACIONAL",
            nodes=(configured["datahub_unit"],),
        )
    assert error.value.status == 404


def test_stale_capability_summary_cannot_enable_uncontracted_module(
    member, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    headers = select_context(member, configured["contract_a"])
    assert (
        member.get("/api/context/operational-scope", headers=headers).status_code == 200
    )
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE contract_modules SET active=false,contracted=false WHERE code='DATAHUB' AND contract_id=:c"
            ),
            {"c": configured["contract_a"]},
        )
    with pytest.raises(ApiError) as error:
        invoke(db_runtime, headers, "COMPRADOR_NACIONAL")
    assert error.value.code == "MODULE_UNAVAILABLE"


def test_explicit_node_operation_does_not_depend_on_discovery_graph_limit(
    member, configured, db_runtime
):
    grant_caps(db_runtime, configured)
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organization_nodes (tenant_id,contract_id,kind,name,code,active) SELECT :t,:c,'UNIT','Unit','MORE_' || n,false FROM generate_series(1,1000) n"
            ),
            {"t": configured["tenant_a"], "c": configured["contract_a"]},
        )
    headers = select_context(member, configured["contract_a"])
    assert (
        member.get("/api/context/operational-scope", headers=headers).status_code == 503
    )
    selected = invoke(
        db_runtime, headers, "COMPRADOR_NACIONAL", nodes=(configured["datahub_unit"],)
    )
    assert {u.id for u in selected.units} == {configured["datahub_unit"]}
