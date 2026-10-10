"""Manual external fulfillment, immutable compensation and real PostgreSQL races."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.core.errors import ApiError
from app.organization.models import MembershipUnitScope
from app.procurement.requests import command_schemas as schemas
from app.procurement.requests import commands, queries
from app.procurement.requests.models import (
    PurchaseRequest,
    PurchaseRequestEvent,
    RequestCommandReceipt,
    RequestFulfillmentEntry,
)
from app.tenancy.models import TenantRolePermission
from tests.fixtures.purchase_request_policy import request_permissions
from tests.helpers import select_context
from tests.test_purchase_request_commands import act, fail, payload, request
from tests.test_purchase_request_commands import (
    command_case as _command_case,  # noqa: F401
)


def ready(db, case, *, multiple=False):
    ids, actor, scope, _, _ = case
    data = payload(ids["node"])
    data["items"][0]["requested_quantity"] = "2.000000"
    if multiple:
        data["items"].append(
            {
                "description": "Second real item",
                "requested_quantity": "0.300000",
                "uom_code": "KG",
            }
        )
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**data), uuid4()
    )
    row = act(db, case, row, "submit")
    row = act(db, case, row, "start-triage")
    row = act(db, case, row, "request-approval")
    row = act(db, case, row, "approve", who="buyer")
    row = commands.assign_buyer(
        db,
        request(),
        actor,
        scope,
        row.id,
        schemas.AssignmentCommand(
            expected_version=row.version, buyer_membership_id=ids["buyer_member"]
        ),
        uuid4(),
    )
    return act(db, case, row, "start-fulfillment", who="buyer")


def body(row, quantity="1.000000", item=None):
    return schemas.FulfillmentCommand(
        expected_version=row.version,
        item_id=item or row.items[0].id,
        quantity=quantity,
        evidence="Signed delivery received on site",
        reason="Actual external delivery",
    )


def record(db, case, row, quantity="1.000000", item=None, key=None):
    from app.procurement.requests.fulfillment import record_fulfillment

    return record_fulfillment(
        db,
        request(),
        case[3],
        case[4],
        row.id,
        body(row, quantity, item),
        key or uuid4(),
    )


def reverse(db, case, row, entry, key=None):
    from app.procurement.requests.fulfillment import reverse_fulfillment

    return reverse_fulfillment(
        db,
        request(),
        case[3],
        case[4],
        row.id,
        entry,
        schemas.ReasonCommand(
            expected_version=row.version, reason="Incorrect delivery attribution"
        ),
        key or uuid4(),
    )


def entries(db, row):
    return list(
        db.scalars(
            select(RequestFulfillmentEntry)
            .where(RequestFulfillmentEntry.request_id == row.id)
            .order_by(RequestFulfillmentEntry.aggregate_version)
        )
    )


def test_http_manual_fulfillment_route(member, db, command_case):
    ids, actor, scope, *_ = command_case
    request_permissions(db, ids, ids["role_basic"], ["fulfill"])
    row = ready(db, command_case)
    row = commands.assign_buyer(
        db,
        request(),
        actor,
        scope,
        row.id,
        schemas.AssignmentCommand(
            expected_version=row.version, buyer_membership_id=ids["member_a"]
        ),
        uuid4(),
    )
    db.commit()
    headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    path = f"/api/procurement/requests/{row.id}/fulfillments"
    response = member.post(
        path, headers=headers, json=body(row).model_dump(mode="json")
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["fulfilled_quantity"] == "1.000000"
    assert response.headers["Cache-Control"] == "no-store"
    entry = entries(db, row)[0]
    response = member.post(
        f"{path}/{entry.id}/reverse",
        headers=headers | {"Idempotency-Key": str(uuid4())},
        json={"expected_version": row.version + 1, "reason": "Incorrect attribution"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["fulfillment_state"] == "NONE"


def test_multi_item_partial_complete_close(db, command_case):
    row = ready(db, command_case, multiple=True)
    partial = record(db, command_case, row)
    assert partial.status == "IN_FULFILLMENT" and partial.fulfillment_state == "PARTIAL"
    assert partial.items[0].remaining_quantity == "1.000000"
    row = record(db, command_case, partial)
    row = record(db, command_case, row, "0.100000", row.items[1].id)
    before = row.version
    complete = record(db, command_case, row, "0.200000", row.items[1].id)
    assert complete.status == "FULFILLED" and complete.fulfillment_state == "COMPLETE"
    assert complete.version == before + 1 and complete.fulfilled_at is not None
    events = list(
        db.scalars(
            select(PurchaseRequestEvent)
            .where(
                PurchaseRequestEvent.request_id == row.id,
                PurchaseRequestEvent.aggregate_version == complete.version,
            )
            .order_by(PurchaseRequestEvent.sequence)
        )
    )
    assert [e.action for e in events] == [
        "procurement.request.fulfillment_recorded",
        "procurement.request.fulfilled",
    ]
    assert events[1].sequence == events[0].sequence + 1
    for event in events:
        audit = db.get(AuditEvent, event.audit_event_id)
        assert "Signed delivery" not in str(audit.after_state)
        assert "Actual external delivery" not in str(audit.after_state)
    fail(
        lambda: reverse(db, command_case, complete, entries(db, row)[0].id),
        "INVALID_TRANSITION",
    )
    fail(lambda: record(db, command_case, complete), "INVALID_TRANSITION")
    closed = act(db, command_case, complete, "close")
    assert closed.status == "CLOSED" and closed.fulfillment_state == "COMPLETE"


def test_compensation_once_preserves_original(db, command_case):
    row = record(db, command_case, ready(db, command_case))
    original = entries(db, row)[0]
    immutable = (
        original.quantity,
        original.sign,
        original.evidence,
        original.reason,
        original.aggregate_version,
        original.occurred_at,
    )
    before = row
    key = uuid4()
    reversed_row = reverse(db, command_case, row, original.id, key)
    assert (
        reversed_row.fulfillment_state == "NONE"
        and reversed_row.items[0].fulfilled_quantity == "0.000000"
    )
    compensation = entries(db, row)[1]
    assert compensation.sign == -1 and compensation.quantity == Decimal(1)
    assert (
        compensation.original_entry_id == original.id
        and compensation.evidence == original.evidence
    )
    db.refresh(original)
    assert (
        original.quantity,
        original.sign,
        original.evidence,
        original.reason,
        original.aggregate_version,
        original.occurred_at,
    ) == immutable
    assert reverse(db, command_case, before, original.id, key).model_dump(
        mode="json"
    ) == reversed_row.model_dump(mode="json")
    fail(
        lambda: reverse(db, command_case, reversed_row, original.id),
        "FULFILLMENT_ALREADY_REVERSED",
    )
    fail(
        lambda: reverse(db, command_case, reversed_row, compensation.id),
        "INVALID_FULFILLMENT_ENTRY",
    )
    fail(lambda: reverse(db, command_case, reversed_row, uuid4()), "NOT_FOUND")
    assert len(entries(db, row)) == 2


def test_partial_cancel_keeps_quantities(db, command_case):
    row = record(db, command_case, ready(db, command_case))
    row = act(db, command_case, row, "cancel", reason="Remaining need cancelled")
    assert row.status == "CANCELLED" and row.fulfillment_state == "PARTIAL"
    assert (
        row.items[0].fulfilled_quantity == "1.000000"
        and row.items[0].remaining_quantity == "1.000000"
    )
    fail(
        lambda: reverse(db, command_case, row, entries(db, row)[0].id),
        "INVALID_TRANSITION",
    )


def test_decimal_overdelivery_and_foreign_item(db, command_case):
    row = ready(db, command_case)
    other = ready(db, command_case)
    fail(
        lambda: record(db, command_case, row, "2.000001"),
        "FULFILLMENT_EXCEEDS_REMAINING",
    )
    fail(lambda: record(db, command_case, row, item=other.items[0].id), "NOT_FOUND")
    foreign = record(db, command_case, other)
    fail(
        lambda: reverse(db, command_case, row, entries(db, foreign)[0].id), "NOT_FOUND"
    )
    assert len(entries(db, row)) == 0
    row = record(db, command_case, row, "0.000001")
    assert row.items[0].remaining_quantity == "1.999999"
    fail(lambda: record(db, command_case, row, "2"), "FULFILLMENT_EXCEEDS_REMAINING")


@pytest.mark.parametrize(
    "bad", [1.1, "NaN", "Infinity", "-1", "0", "0.0000001", "1000000000000"]
)
def test_exact_decimal_command_rejects_bad_quantity(bad):
    with pytest.raises(ValidationError):
        schemas.FulfillmentCommand(
            expected_version=1,
            item_id=uuid4(),
            quantity=bad,
            evidence="Delivery",
            reason="Actual",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence", " "),
        ("reason", " "),
        ("sign", -1),
        ("source_kind", "STOCK"),
        ("quantity", "1.0000001"),
    ],
)
def test_closed_fulfillment_command_requires_real_evidence(field, value):
    data = {
        "expected_version": 1,
        "item_id": uuid4(),
        "quantity": "1",
        "evidence": "Real delivery",
        "reason": "Actual",
    }
    with pytest.raises(ValidationError):
        schemas.FulfillmentCommand(**(data | {field: value}))


@pytest.mark.parametrize("revocation", ["fulfill", "read_unit", "grant", "assignment"])
@pytest.mark.parametrize("command", ["record", "reverse"])
def test_fulfillment_replay_rechecks_current_authority(
    db, command_case, revocation, command
):
    row = ready(db, command_case)
    before, key = row, uuid4()
    row = record(db, command_case, before, key=key)
    entry_id = entries(db, row)[0].id
    if command == "reverse":
        before, key = row, uuid4()
        row = reverse(db, command_case, before, entry_id, key)
    ids = command_case[0]
    if revocation in {"fulfill", "read_unit"}:
        target = db.scalar(
            select(TenantRolePermission).where(
                TenantRolePermission.role_id == ids["buyer_role"],
                TenantRolePermission.capability == f"procurement.requests.{revocation}",
            )
        )
        target.active = False
    elif revocation == "grant":
        target = db.scalar(
            select(MembershipUnitScope).where(
                MembershipUnitScope.membership_id == ids["buyer_member"],
                MembershipUnitScope.node_id == ids["node"],
            )
        )
        target.active = False
    else:
        db.get(PurchaseRequest, row.id).buyer_membership_id = ids["member_a"]
    db.flush()
    retry = lambda: (
        record(db, command_case, before, key=key)
        if command == "record"
        else reverse(db, command_case, before, entry_id, key)
    )
    with pytest.raises(ApiError) as denied:
        retry()
    assert getattr(denied.value, "code", None) in {
        "CAPABILITY_DENIED",
        "UNIT_SCOPE_DENIED",
    }
    assert len(entries(db, row)) == (1 if command == "record" else 2)


def test_original_receipt_after_later_commands_and_conflict(db, command_case):
    original, key = ready(db, command_case), uuid4()
    first = record(db, command_case, original, key=key)
    complete = record(db, command_case, first)
    assert record(db, command_case, original, key=key).model_dump(
        mode="json"
    ) == first.model_dump(mode="json")
    fail(
        lambda: record(db, command_case, original, "0.5", key=key),
        "IDEMPOTENCY_CONFLICT",
    )
    assert (
        queries.get_request(db, command_case[3], command_case[4], complete.id).status
        == "FULFILLED"
    )


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_and_idempotent_fulfillment(db, db_runtime, command_case, same_key):
    row = ready(db, command_case)
    db.commit()
    barrier, key = Barrier(2), uuid4()

    def run():
        with Session(db_runtime) as worker:
            worker.execute(text("SET LOCAL lock_timeout='8s'"))
            barrier.wait(timeout=5)
            try:
                result = record(
                    worker,
                    command_case,
                    row,
                    "1.500000",
                    key=key if same_key else uuid4(),
                )
                worker.commit()
                return result.model_dump(mode="json")
            except ApiError as error:
                worker.rollback()
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    if same_key:
        assert results[0] == results[1] and isinstance(results[0], dict)
    else:
        assert sum(isinstance(result, dict) for result in results) == 1
        assert "VERSION_CONFLICT" in results
    with Session(db_runtime) as verify:
        stored = queries.get_request(verify, command_case[3], command_case[4], row.id)
        assert (
            stored.items[0].fulfilled_quantity == "1.500000"
            and stored.version == row.version + 1
        )
        assert len(entries(verify, row)) == 1
        assert (
            verify.scalar(
                select(func.count())
                .select_from(RequestCommandReceipt)
                .where(
                    RequestCommandReceipt.request_id == row.id,
                    RequestCommandReceipt.route == "fulfillments",
                )
            )
            == 1
        )


@pytest.mark.parametrize("command", ["record", "reverse"])
def test_fulfillment_audit_failure_is_atomic(db, command_case, monkeypatch, command):
    from app.procurement.requests import events

    row = ready(db, command_case)
    if command == "reverse":
        row = record(db, command_case, row)
    count = len(entries(db, row))
    events_before = db.scalar(
        select(func.count())
        .select_from(PurchaseRequestEvent)
        .where(PurchaseRequestEvent.request_id == row.id)
    )
    receipts_before = db.scalar(
        select(func.count())
        .select_from(RequestCommandReceipt)
        .where(RequestCommandReceipt.request_id == row.id)
    )

    def unavailable(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(events, "append_event", unavailable)
    with pytest.raises(RuntimeError), db.begin_nested():
        if command == "record":
            record(db, command_case, row)
        else:
            reverse(db, command_case, row, entries(db, row)[0].id)
    assert len(entries(db, row)) == count
    assert db.get(PurchaseRequest, row.id).version == row.version
    assert (
        db.scalar(
            select(func.count())
            .select_from(PurchaseRequestEvent)
            .where(PurchaseRequestEvent.request_id == row.id)
        )
        == events_before
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(RequestCommandReceipt)
            .where(RequestCommandReceipt.request_id == row.id)
        )
        == receipts_before
    )


@pytest.mark.parametrize("same_key", [False, True])
def test_concurrent_compensation_once(db, db_runtime, command_case, same_key):
    row = record(db, command_case, ready(db, command_case))
    entry_id = entries(db, row)[0].id
    db.commit()
    barrier, key = Barrier(2), uuid4()

    def run():
        with Session(db_runtime) as worker:
            worker.execute(text("SET LOCAL lock_timeout='8s'"))
            barrier.wait(timeout=5)
            try:
                result = reverse(
                    worker, command_case, row, entry_id, key if same_key else uuid4()
                )
                worker.commit()
                return result.model_dump(mode="json")
            except ApiError as error:
                worker.rollback()
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    if same_key:
        assert results[0] == results[1] and isinstance(results[0], dict)
    else:
        assert sum(isinstance(result, dict) for result in results) == 1
        assert "VERSION_CONFLICT" in results
    with Session(db_runtime) as verify:
        stored = queries.get_request(verify, command_case[3], command_case[4], row.id)
        assert stored.items[0].fulfilled_quantity == "0.000000"
        assert stored.version == row.version + 1 and len(entries(verify, row)) == 2


def test_request_owner_needs_read_unit_to_record(db, command_case):
    from app.procurement.requests.fulfillment import record_fulfillment

    ids, actor, scope, *_ = command_case
    request_permissions(db, ids, ids["role_basic"], ["fulfill"])
    row = ready(db, command_case)
    row = commands.assign_buyer(
        db,
        request(),
        actor,
        scope,
        row.id,
        schemas.AssignmentCommand(
            expected_version=row.version, buyer_membership_id=ids["member_a"]
        ),
        uuid4(),
    )
    read_unit = db.scalar(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["role_basic"],
            TenantRolePermission.capability == "procurement.requests.read_unit",
        )
    )
    read_unit.active = False
    db.flush()
    fail(
        lambda: record_fulfillment(
            db, request(), actor, scope, row.id, body(row), uuid4()
        ),
        "CAPABILITY_DENIED",
    )
    assert len(entries(db, row)) == 0


def test_complementary_audit_failure_rolls_back_completed_delivery(
    db, command_case, monkeypatch
):
    from app.procurement.requests import events

    row = ready(db, command_case)
    original = events.append_event

    def fail_completion(db, payload):
        if payload.action == "procurement.request.fulfilled":
            raise RuntimeError("Completion audit unavailable")
        return original(db, payload)

    monkeypatch.setattr(events, "append_event", fail_completion)
    with pytest.raises(RuntimeError), db.begin_nested():
        record(db, command_case, row, "2.000000")
    stored = db.get(PurchaseRequest, row.id)
    assert stored.version == row.version and stored.status == "IN_FULFILLMENT"
    assert stored.fulfilled_at is None and len(entries(db, row)) == 0
    assert (
        db.scalar(
            select(func.count())
            .select_from(PurchaseRequestEvent)
            .where(PurchaseRequestEvent.request_id == row.id)
        )
        == 7
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(RequestCommandReceipt)
            .where(RequestCommandReceipt.request_id == row.id)
        )
        == 7
    )


@pytest.mark.parametrize("command", ["record", "reverse"])
@pytest.mark.parametrize("revocation", ["fulfill", "read_unit", "grant"])
def test_fulfillment_wait_rechecks_revoked_authority(
    db, db_runtime, command_case, command, revocation
):
    from threading import Event

    from sqlalchemy import event

    from app.identity.models import User

    row = ready(db, command_case)
    if command == "reverse":
        row = record(db, command_case, row)
        entry_id = entries(db, row)[0].id
    initial_entries = len(entries(db, row))
    db.commit()
    waiting = Event()

    def observe(conn, cursor, statement, params, context, executemany):
        if (
            conn.info.get("fulfillment_wait")
            and "users" in statement
            and "FOR UPDATE" in statement
        ):
            waiting.set()

    def run():
        with Session(db_runtime) as worker:
            worker.connection().info["fulfillment_wait"] = True
            worker.execute(text("SET LOCAL lock_timeout='8s'"))
            try:
                if command == "record":
                    record(worker, command_case, row)
                else:
                    reverse(worker, command_case, row, entry_id)
                worker.commit()
                return "UNEXPECTED_SUCCESS"
            except ApiError as error:
                worker.rollback()
                return error.code
            finally:
                worker.connection().info.pop("fulfillment_wait", None)

    event.listen(db_runtime, "before_cursor_execute", observe)
    try:
        with Session(db_runtime) as revoker, ThreadPoolExecutor(max_workers=1) as pool:
            revoker.scalar(
                select(User).where(User.id == command_case[3].user_id).with_for_update()
            )
            ids = command_case[0]
            if revocation == "grant":
                target = revoker.scalar(
                    select(MembershipUnitScope).where(
                        MembershipUnitScope.membership_id == ids["buyer_member"],
                        MembershipUnitScope.node_id == ids["node"],
                    )
                )
            else:
                target = revoker.scalar(
                    select(TenantRolePermission).where(
                        TenantRolePermission.role_id == ids["buyer_role"],
                        TenantRolePermission.capability
                        == f"procurement.requests.{revocation}",
                    )
                )
            target.active = False
            revoker.flush()
            future = pool.submit(run)
            assert waiting.wait(5), "Fulfillment never attempted its identity lock"
            revoker.commit()
            assert future.result(timeout=10) in {
                "CAPABILITY_DENIED",
                "UNIT_SCOPE_DENIED",
            }
        with Session(db_runtime) as verify:
            stored = verify.get(PurchaseRequest, row.id)
            assert stored.version == row.version and stored.status == "IN_FULFILLMENT"
            assert len(entries(verify, row)) == initial_entries
    finally:
        event.remove(db_runtime, "before_cursor_execute", observe)
