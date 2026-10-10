from decimal import Decimal
from importlib.util import find_spec
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import bindparam, inspect, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError, ProgrammingError


def test_payload_limits_and_exact_decimals():
    assert find_spec("app.procurement") is not None, (
        "Purchase request package is missing"
    )
    from app.procurement.requests.command_schemas import (
        ApprovalPolicyPatch,
        DraftPatch,
        FulfillmentCommand,
        RequestCreate,
    )
    from app.procurement.requests.schemas import ApprovalPolicyView

    unit, item = uuid4(), uuid4()
    assert RequestCreate(requesting_node_id=unit, title="Necessidade real").items == []
    valid = {
        "expected_version": 1,
        "item_id": item,
        "quantity": "0.000001",
        "evidence": "Recebimento documentado",
        "reason": "Atendimento real",
    }
    assert FulfillmentCommand(**valid).quantity == Decimal("0.000001")
    for quantity in [0.1, "0", "NaN", "1.0000001", "1000000000000.000000"]:
        with pytest.raises(ValidationError):
            FulfillmentCommand(**{**valid, "quantity": quantity})
    base = {"requesting_node_id": unit, "title": "Necessidade real"}
    for extra in [
        {"title": "a" * 201},
        {"items": [{}] * 101},
        {"tenant_id": uuid4()},
        {"contract_id": uuid4()},
        {"requester_user_id": uuid4()},
        {"requester_membership_id": uuid4()},
        {"role": "ADMIN"},
        {"status": "APPROVED"},
        {"approval_mode": "NOT_REQUIRED"},
        {"approval_decision_kind": "POLICY_WAIVER"},
    ]:
        with pytest.raises(ValidationError):
            RequestCreate(**{**base, **extra})
    for uom in ["CX", "PCT"]:
        with pytest.raises(ValidationError):
            RequestCreate(
                **base,
                items=[
                    {
                        "description": "Produto real",
                        "requested_quantity": "1",
                        "uom_code": uom,
                    }
                ],
            )
    for field in ["project_id", "cost_center_id"]:
        for schema, values in [
            (RequestCreate, base),
            (DraftPatch, {"expected_version": 1}),
        ]:
            with pytest.raises(ValidationError) as caught:
                schema(**{**values, field: uuid4()})
            assert caught.value.errors()[0]["type"] == "REFERENCE_DOMAIN_UNAVAILABLE"
            assert schema(**{**values, field: None})
    assert ApprovalPolicyView().approval_mode == "REQUIRED"
    assert ApprovalPolicyView().version == 0
    with pytest.raises(ValidationError):
        ApprovalPolicyPatch(
            expected_version=0, approval_mode="UNKNOWN", reason="Motivo real"
        )
    with pytest.raises(ValidationError):
        ApprovalPolicyView(approval_mode="UNKNOWN")


def test_scoped_foreign_keys_and_immutable_history(db_runtime):
    tables = inspect(db_runtime).get_table_names()
    assert "purchase_requests" in tables
    assert "contract_request_policies" in tables


def test_runtime_grants_and_migration_lifecycle(db_runtime):
    assert "request_command_receipts" in inspect(db_runtime).get_table_names()


@pytest.mark.parametrize(
    "table",
    [
        "purchase_request_events",
        "request_fulfillment_entries",
        "request_command_receipts",
    ],
)
def test_runtime_cannot_rewrite_evidence(db_runtime, table):
    with db_runtime.connect() as conn:
        for privilege in ["UPDATE", "DELETE"]:
            assert not conn.execute(
                text("SELECT has_table_privilege(current_user,:table,:privilege)"),
                {"table": table, "privilege": privilege},
            ).scalar_one()
        assert conn.execute(
            text("SELECT has_table_privilege(current_user,:table,'INSERT')"),
            {"table": table},
        ).scalar_one()
        with pytest.raises(ProgrammingError):
            conn.execute(text(f"UPDATE {table} SET id=id"))
        conn.rollback()
        with pytest.raises(ProgrammingError):
            conn.execute(text(f"DELETE FROM {table}"))


def test_purchase_request_capability_catalog_has_no_automatic_grants(db_runtime):
    from app.organization.modules import OPERATIONAL_MODULES
    from app.platform.capabilities import CATALOG

    for operation in [
        "create",
        "read_own",
        "read_unit",
        "triage",
        "approve",
        "assign",
        "fulfill",
        "cancel",
        "close",
        "comment",
    ]:
        code = f"procurement.requests.{operation}"
        assert code in CATALOG
        capability = CATALOG[code]
        assert capability.tenant_enabled and capability.tenant_role
        assert capability.domain == "procurement"
        assert capability.module_code == "PROCUREMENT"
        assert capability.read_only_safe == operation.startswith("read_")
        assert capability.mutates_business_state == (not operation.startswith("read_"))
    assert "PROCUREMENT" in OPERATIONAL_MODULES
    from app.procurement.requests.routes import router

    assert any(
        route.path == "/procurement/requests" and "POST" in route.methods
        for route in router.routes
    )
    with db_runtime.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM tenant_role_permissions WHERE capability LIKE 'procurement.requests.%'"
                )
            ).scalar_one()
            == 0
        )


def test_scoped_references_reject_cross_contract_and_cross_request(db, purchase_case):
    c = purchase_case
    values = {
        "tenant": c["tenant_a"],
        "contract": c["contract_a"],
        "user": c["user"],
        "member": c["member_a"],
        "node": c["node"],
        "request": c["request"],
        "item": c["item"],
        "audit": c["audit"],
        "role": c["role_basic"],
    }
    request_sql = "INSERT INTO purchase_requests(id,tenant_id,contract_id,requester_user_id,requester_membership_id,requesting_node_id,title,buyer_membership_id) VALUES (:id,:tenant,:contract,:user,:member,:node,'Real need',:buyer)"
    for bad in [
        {"member": c["member_b"]},
        {"node": c["foreign_node"]},
        {"buyer": c["member_b"]},
        {"user": uuid4()},
        {"contract": c["contract_a2"]},
    ]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(
                text(request_sql), {**values, "id": uuid4(), "buyer": None, **bad}
            )
    attachment_sql = "INSERT INTO request_attachments(id,tenant_id,contract_id,request_id,item_id,uploader_user_id,uploader_membership_id,filename,media_type,digest,size,content) VALUES (:id,:tenant,:contract,:request,:item,:user,:member,'evidence.txt','text/plain',:digest,1,:content)"
    for bad in [
        {"item": c["other_item"]},
        {"member": c["member_b"]},
        {"contract": c["contract_a2"]},
    ]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(
                text(attachment_sql),
                {**values, "id": uuid4(), "digest": "a" * 64, "content": b"x", **bad},
            )
    entry_sql = "INSERT INTO request_fulfillment_entries(id,tenant_id,contract_id,request_id,item_id,actor_user_id,actor_membership_id,quantity,uom_code,evidence,reason,aggregate_version) VALUES (:id,:tenant,:contract,:request,:item,:user,:member,0.000001,'UN','Actual receipt','Actual fulfillment',1)"
    for bad in [
        {"item": c["other_item"]},
        {"member": c["member_b"]},
        {"contract": c["contract_a2"]},
    ]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text(entry_sql), {**values, "id": uuid4(), **bad})
    event_sql = "INSERT INTO purchase_request_events(id,tenant_id,contract_id,request_id,sequence,aggregate_version,action,actor_user_id,actor_membership_id,tenant_role_id,tenant_role_code,payload,audit_event_id) VALUES (:id,:tenant,:contract,:request,1,1,'procurement.request.created',:user,:member,:role,'ACTUAL_ROLE','{}',:audit)"
    for bad in [
        {"member": c["member_b"]},
        {"role": c["role_b"]},
        {"contract": c["contract_a2"]},
    ]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text(event_sql), {**values, "id": uuid4(), **bad})
    db.execute(text(event_sql), {**values, "id": uuid4()})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(event_sql), {**values, "id": uuid4()})
    db.execute(text(entry_sql), {**values, "id": uuid4()})
    with pytest.raises(ProgrammingError), db.begin_nested():
        db.execute(text("DELETE FROM purchase_requests WHERE id=:request"), values)
    with pytest.raises(ProgrammingError), db.begin_nested():
        db.execute(
            text(
                "UPDATE purchase_requests SET requester_user_id=:user WHERE id=:request"
            ),
            values,
        )
    db.execute(
        text("UPDATE purchase_requests SET status='SUBMITTED' WHERE id=:request"),
        values,
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "UPDATE purchase_request_items SET requested_quantity=2 WHERE id=:item"
            ),
            values,
        )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("DELETE FROM purchase_request_items WHERE id=:item"), values)


def test_compensations_are_scoped_and_unique(db, purchase_case):
    c = purchase_case
    values = {
        "tenant": c["tenant_a"],
        "contract": c["contract_a"],
        "request": c["request"],
        "item": c["item"],
        "user": c["user"],
        "member": c["member_a"],
        "original": uuid4(),
    }
    sql = "INSERT INTO request_fulfillment_entries(id,tenant_id,contract_id,request_id,item_id,actor_user_id,actor_membership_id,quantity,uom_code,evidence,reason,aggregate_version,sign,original_entry_id) VALUES (:id,:tenant,:contract,:request,:item,:user,:member,0.1,'UN','Real receipt','Real reversal',1,:sign,:original)"
    db.execute(
        text(sql), {**values, "id": values["original"], "sign": 1, "original": None}
    )
    db.execute(text(sql), {**values, "id": uuid4(), "sign": -1})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(sql), {**values, "id": uuid4(), "sign": -1})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(sql),
            {
                **values,
                "id": uuid4(),
                "sign": -1,
                "item": c["other_item"],
                "original": uuid4(),
            },
        )


def test_policy_default_scoped_constraint_and_runtime_mutation(db, purchase_case):
    c = purchase_case
    values = {"tenant": c["tenant_a"], "contract": c["contract_a"]}
    db.execute(
        text(
            "INSERT INTO contract_request_policies(tenant_id,contract_id) VALUES (:tenant,:contract)"
        ),
        values,
    )
    assert db.execute(
        text(
            "SELECT approval_mode,version FROM contract_request_policies WHERE tenant_id=:tenant AND contract_id=:contract"
        ),
        values,
    ).one() == ("REQUIRED", 1)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE contract_request_policies SET approval_mode='UNKNOWN'"))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO contract_request_policies(tenant_id,contract_id) VALUES (:tenant,:contract)"
            ),
            {**values, "contract": c["contract_b"]},
        )
    db.execute(
        text(
            "UPDATE contract_request_policies SET approval_mode='NOT_REQUIRED',version=2"
        )
    )


def test_registered_purchase_models_match_migration(db_runtime):
    from app.db.models import Base

    inspector = inspect(db_runtime)
    for name in [
        "purchase_requests",
        "purchase_request_items",
        "purchase_request_events",
        "request_fulfillment_entries",
        "request_attachments",
        "request_command_receipts",
        "contract_request_policies",
    ]:
        assert set(Base.metadata.tables[name].columns.keys()) == {
            column["name"] for column in inspector.get_columns(name)
        }


def test_receipt_null_target_is_unique_and_context_scoped(db, purchase_case):
    c = purchase_case
    session, context = uuid4(), uuid4()
    values = {
        "tenant": c["tenant_a"],
        "contract": c["contract_a"],
        "actor": c["user"],
        "request": c["request"],
        "session": session,
        "context": context,
        "key": uuid4(),
        "digest": "a" * 64,
    }
    db.execute(
        text(
            "INSERT INTO auth_sessions(id,user_id,token_hash,csrf_hash,created_at,last_seen_at,expires_at) VALUES (:session,:actor,:digest,:digest,now(),now(),now()+interval '1 hour')"
        ),
        values,
    )
    db.execute(
        text(
            "INSERT INTO access_contexts(id,session_id,actor_id,tenant_id,contract_id,created_at,expires_at) VALUES (:context,:session,:actor,:tenant,:contract,now(),now()+interval '1 hour')"
        ),
        values,
    )
    result = {
        "schema_version": 1,
        "id": str(c["request"]),
        "tenant_id": str(c["tenant_a"]),
        "contract_id": str(c["contract_a"]),
        "version": 1,
        "status": "DRAFT",
    }
    statement = text(
        "INSERT INTO request_command_receipts(id,tenant_id,contract_id,request_id,actor_user_id,access_context_id,auth_session_id,route,target_id,idempotency_key,digest,result,response_status) VALUES (:id,:tenant,:contract,:request,:actor,:context,:session,'/api/procurement/requests',NULL,:key,:digest,:result,201)"
    ).bindparams(bindparam("result", type_=JSONB))
    db.execute(statement, {**values, "id": uuid4(), "result": result})
    for digest in ["a" * 64, "b" * 64]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(
                statement, {**values, "id": uuid4(), "result": result, "digest": digest}
            )
    for bad in [
        {"contract": c["contract_a2"]},
        {"actor": uuid4()},
        {"result": {}},
        *(
            {"result": {**result, field: None}}
            for field in [
                "schema_version",
                "id",
                "tenant_id",
                "contract_id",
                "version",
                "status",
            ]
        ),
    ]:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(
                statement,
                {**values, "id": uuid4(), "key": uuid4(), "result": result, **bad},
            )


def test_submitted_items_cannot_accept_new_insert(db, purchase_case):
    c = purchase_case
    db.execute(
        text("UPDATE purchase_requests SET status='SUBMITTED' WHERE id=:request"),
        {"request": c["request"]},
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(
                "INSERT INTO purchase_request_items(id,tenant_id,contract_id,request_id,position,description,requested_quantity,uom_code) VALUES (:id,:tenant,:contract,:request,2,'Additional actual item',1,'UN')"
            ),
            {
                "id": uuid4(),
                "tenant": c["tenant_a"],
                "contract": c["contract_a"],
                "request": c["request"],
            },
        )


def test_maximum_unicode_note_payload_is_storable(db, purchase_case):
    from sqlalchemy import bindparam
    from sqlalchemy.dialects.postgresql import JSONB

    from app.procurement.requests.schemas import RequestEventPayload

    c = purchase_case
    note = "🧾" * 4000
    payload = RequestEventPayload(
        text=note,
        from_status="SUBMITTED",
        to_status="SUBMITTED",
        item_id=c["item"],
        content_digest="a" * 64,
    ).model_dump(mode="json")
    statement = text(
        "INSERT INTO purchase_request_events(id,tenant_id,contract_id,request_id,sequence,aggregate_version,action,actor_user_id,actor_membership_id,tenant_role_id,tenant_role_code,payload,audit_event_id) VALUES (:id,:tenant,:contract,:request,1,1,'procurement.request.note_added',:user,:member,:role,'ACTUAL_ROLE',:payload,:audit)"
    ).bindparams(bindparam("payload", type_=JSONB))
    event_id = uuid4()
    db.execute(
        statement,
        {
            "id": event_id,
            "tenant": c["tenant_a"],
            "contract": c["contract_a"],
            "request": c["request"],
            "user": c["user"],
            "member": c["member_a"],
            "role": c["role_basic"],
            "payload": payload,
            "audit": c["audit"],
        },
    )
    assert (
        db.execute(
            text("SELECT payload->>'text' FROM purchase_request_events WHERE id=:id"),
            {"id": event_id},
        ).scalar_one()
        == note
    )


def test_approver_requires_explicit_human_decision(db, purchase_case):
    c = purchase_case
    statement = text(
        "UPDATE purchase_requests SET approval_mode=:mode,approval_policy_version=:version,approval_decision_kind=:kind,approver_membership_id=:member,approver_user_id=:user WHERE id=:request"
    )
    actor = {
        "member": c["member_internal"],
        "user": c["support_user"],
        "request": c["request"],
    }
    empty = {"member": None, "user": None, "request": c["request"]}
    invalid = [
        {**actor, "mode": "REQUIRED", "version": 0, "kind": None},
        {**empty, "mode": "REQUIRED", "version": None, "kind": None},
        {**empty, "mode": None, "version": 0, "kind": None},
        {**empty, "mode": "REQUIRED", "version": -1, "kind": None},
        {**empty, "mode": None, "version": None, "kind": "POLICY_WAIVER"},
        {**actor, "mode": "NOT_REQUIRED", "version": 0, "kind": "HUMAN"},
        {**empty, "mode": "REQUIRED", "version": 0, "kind": "POLICY_WAIVER"},
        {**empty, "mode": "REQUIRED", "version": 0, "kind": "HUMAN"},
        {
            **actor,
            "mode": "REQUIRED",
            "version": 0,
            "kind": "HUMAN",
            "member": c["member_a"],
            "user": c["user"],
        },
        {**actor, "mode": "REQUIRED", "version": 0, "kind": "HUMAN", "user": None},
    ]
    for values in invalid:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(statement, values)
    for values in [
        {**empty, "mode": None, "version": None, "kind": None},
        {**empty, "mode": "REQUIRED", "version": 0, "kind": None},
        {**actor, "mode": "REQUIRED", "version": 1, "kind": "HUMAN"},
        {**empty, "mode": "NOT_REQUIRED", "version": 2, "kind": "POLICY_WAIVER"},
    ]:
        db.execute(statement, values)


def test_item_position_constraint_deferrable_and_migration_roundtrip(
    db_runtime, db_owner, migration_config
):
    from alembic import command

    def state(conn):
        return conn.execute(
            text(
                "SELECT condeferrable, condeferred FROM pg_constraint WHERE conname='uq_purchase_request_item_position'"
            )
        ).one()

    with db_runtime.connect() as conn:
        assert state(conn) == (True, False)
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0014")
            assert state(conn) == (False, False)
            command.upgrade(migration_config, "head")
            assert state(conn) == (True, False)
    finally:
        migration_config.attributes.pop("connection", None)


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_item_order_migration_rejects_unsafe_runtime_before_ddl(
    db_owner, db_runtime, migration_config, unsafe
):
    from alembic import command

    good_role = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0014")
            migration_config.attributes["runtime_role"] = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "head")
            assert not conn.execute(
                text(
                    "SELECT condeferrable FROM pg_constraint WHERE conname='uq_purchase_request_item_position'"
                )
            ).scalar_one()
            migration_config.attributes["runtime_role"] = good_role
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good_role
