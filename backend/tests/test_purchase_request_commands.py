"""Workflow commands exercise durable PostgreSQL state and private HTTP contracts."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.audit.models import AuditEvent
from app.core.errors import ApiError
from app.organization.models import MembershipUnitScope
from app.procurement.requests.models import (
    PurchaseRequest,
    PurchaseRequestEvent,
    PurchaseRequestItem,
    RequestCommandReceipt,
)
from tests.fixtures.purchase_request_policy import request_permissions
from tests.helpers import select_context


def request():
    return SimpleNamespace(state=SimpleNamespace(request_id=uuid4()))


def api():
    from app.procurement.requests import command_schemas, commands

    return commands, command_schemas


def payload(node):
    return {
        "requesting_node_id": str(node),
        "title": "Replace damaged safety equipment",
        "description": "Equipment needed on the unit",
        "justification": "Existing equipment is damaged",
        "needed_on": "2020-01-01",
        "items": [
            {
                "description": "Safety equipment",
                "requested_quantity": "2.250000",
                "uom_code": "UN",
            }
        ],
    }


@pytest.fixture(name="command_case")
def command_case(db, request_policy_case):
    ids, actor, scope, buyer, buyer_scope = request_policy_case
    request_permissions(
        db,
        ids,
        ids["role_basic"],
        ["triage", "approve", "cancel", "close", "comment", "read_unit"],
    )
    request_permissions(
        db,
        ids,
        ids["buyer_role"],
        ["approve", "assign", "triage", "cancel", "close", "comment"],
    )
    return ids, actor, scope, buyer, buyer_scope


def create(db, case, key=None):
    commands, schemas = api()
    ids, actor, scope, *_ = case
    return commands.create_request(
        db,
        request(),
        actor,
        scope,
        schemas.RequestCreate(**payload(ids["node"])),
        key or uuid4(),
    )


def act(db, case, row, command, *, who="actor", key=None, reason=None):
    commands, schemas = api()
    _, actor, scope, buyer, buyer_scope = case
    principal, access = (actor, scope) if who == "actor" else (buyer, buyer_scope)
    body = {"expected_version": row.version}
    if reason is not None:
        body["reason"] = reason
    schema = (
        schemas.ReasonCommand
        if command in {"reject", "cancel"}
        else schemas.VersionCommand
    )
    return commands.transition_request(
        db,
        request(),
        principal,
        access,
        row.id,
        command,
        schema(**body),
        key or uuid4(),
    )


def triage(db, case):
    row = create(db, case)
    row = act(db, case, row, "submit")
    return act(db, case, row, "start-triage")


def fail(call, code):
    with pytest.raises(ApiError) as error:
        call()
    assert error.value.code == code


def test_http_create_and_reference_domain_error(member, db, request_policy_case):
    ids, *_ = request_policy_case
    db.commit()
    headers = select_context(member, ids["contract_a"])
    headers["Idempotency-Key"] = str(uuid4())
    original = member.post(
        "/api/procurement/requests", headers=headers, json=payload(ids["node"])
    )
    assert original.status_code == 201, original.text
    assert original.json()["status"] == "DRAFT"
    assert original.headers["Cache-Control"] == "no-store"
    duplicate = member.post(
        "/api/procurement/requests", headers=headers, json=payload(ids["node"])
    )
    assert duplicate.json() == original.json()
    invalid = payload(ids["node"]) | {"project_id": str(uuid4())}
    response = member.post("/api/procurement/requests", headers=headers, json=invalid)
    assert response.status_code == 422
    assert response.json()["code"] == "REFERENCE_DOMAIN_UNAVAILABLE"
    invalid = payload(ids["node"]) | {"approval_mode": "NOT_REQUIRED"}
    response = member.post("/api/procurement/requests", headers=headers, json=invalid)
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert "approval_mode" not in response.text


def test_workflow_and_every_invalid_state_pair():
    from app.procurement.requests.transitions import transition_target

    allowed = {
        ("DRAFT", "submit"): "SUBMITTED",
        ("SUBMITTED", "start-triage"): "IN_TRIAGE",
        ("IN_TRIAGE", "request-approval"): "AWAITING_APPROVAL",
        ("AWAITING_APPROVAL", "approve"): "APPROVED",
        ("IN_TRIAGE", "reject"): "REJECTED",
        ("AWAITING_APPROVAL", "reject"): "REJECTED",
        ("APPROVED", "start-fulfillment"): "IN_FULFILLMENT",
        ("FULFILLED", "close"): "CLOSED",
    }
    for status in (
        "DRAFT",
        "SUBMITTED",
        "IN_TRIAGE",
        "AWAITING_APPROVAL",
        "APPROVED",
        "IN_FULFILLMENT",
    ):
        allowed[status, "cancel"] = "CANCELLED"
    for status in (
        "DRAFT",
        "SUBMITTED",
        "IN_TRIAGE",
        "AWAITING_APPROVAL",
        "APPROVED",
        "IN_FULFILLMENT",
        "FULFILLED",
        "CLOSED",
        "REJECTED",
        "CANCELLED",
    ):
        for command in (
            "submit",
            "start-triage",
            "request-approval",
            "approve",
            "reject",
            "start-fulfillment",
            "cancel",
            "close",
        ):
            if (status, command) in allowed:
                assert (
                    transition_target(status, command, approval_mode="REQUIRED")
                    == allowed[status, command]
                )
            else:
                fail(
                    lambda status=status, command=command: transition_target(
                        status, command, approval_mode="REQUIRED"
                    ),
                    "INVALID_TRANSITION",
                )
    assert (
        transition_target("IN_TRIAGE", "request-approval", approval_mode="NOT_REQUIRED")
        == "APPROVED"
    )
    fail(
        lambda: transition_target(
            "IN_TRIAGE", "request-approval", approval_mode="UNKNOWN"
        ),
        "INVALID_POLICY",
    )


@pytest.mark.parametrize("mode", [None, "REQUIRED", "NOT_REQUIRED"])
def test_required_default_not_required_and_invalid_policy(db, command_case, mode):
    from app.procurement.requests.approval_policy import effective_approval_policy
    from app.procurement.requests.models import ContractRequestPolicy

    _ids, _, scope, *_ = command_case
    if mode:
        db.add(
            ContractRequestPolicy(
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                approval_mode=mode,
                version=3,
            )
        )
        db.flush()
    policy = effective_approval_policy(db, scope)
    assert policy.approval_mode == (mode or "REQUIRED")
    assert policy.version == (3 if mode else 0)
    row = act(db, command_case, triage(db, command_case), "request-approval")
    assert row.status == ("APPROVED" if mode == "NOT_REQUIRED" else "AWAITING_APPROVAL")
    assert row.approval_decision_kind == (
        "POLICY_WAIVER" if mode == "NOT_REQUIRED" else None
    )
    assert row.approval_policy_version == (3 if mode else 0)
    stored = db.get(PurchaseRequest, row.id)
    assert stored.approver_user_id is None


def test_self_approval_denied_and_content_frozen(db, command_case):
    commands, schemas = api()
    _, actor, scope, *_ = command_case
    row = act(db, command_case, triage(db, command_case), "request-approval")
    fail(lambda: act(db, command_case, row, "approve"), "CAPABILITY_DENIED")
    fail(
        lambda: commands.update_draft(
            db,
            request(),
            actor,
            scope,
            row.id,
            schemas.DraftPatch(expected_version=row.version, title="Altered"),
        ),
        "INVALID_TRANSITION",
    )
    approved = act(db, command_case, row, "approve", who="buyer")
    assert approved.approval_decision_kind == "HUMAN"
    stored = db.get(PurchaseRequest, row.id)
    assert stored.approver_user_id == command_case[3].user_id


def test_atomic_audit_event_sequence_and_assignment(db, command_case):
    commands, schemas = api()
    ids, actor, scope, _buyer, _buyer_scope = command_case
    row = act(db, command_case, triage(db, command_case), "request-approval")
    row = act(db, command_case, row, "approve", who="buyer")
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
    first = row.assigned_at
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
    assert row.status == "APPROVED" and row.assigned_at == first
    row = act(db, command_case, row, "start-fulfillment", who="buyer")
    row = commands.add_note(
        db,
        request(),
        actor,
        scope,
        row.id,
        schemas.NoteCommand(
            expected_version=row.version, text="Actual additional detail"
        ),
        uuid4(),
    )
    events = list(
        db.scalars(
            select(PurchaseRequestEvent)
            .where(PurchaseRequestEvent.request_id == row.id)
            .order_by(PurchaseRequestEvent.sequence)
        )
    )
    assert [e.sequence for e in events] == list(range(1, 10))
    assert [e.aggregate_version for e in events] == list(range(1, 10))
    assert events[-1].payload["text"] == "Actual additional detail"
    for event in events:
        audit = db.get(AuditEvent, event.audit_event_id)
        assert audit.actor_role is None
        assert audit.after_state["actor_membership_id"] == str(
            event.actor_membership_id
        )
        assert audit.after_state["tenant_role_id"] == str(event.tenant_role_id)
        assert "Actual additional detail" not in str(audit.after_state)


def test_retry_conflict_and_scope_revoked(db, command_case):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    key = uuid4()
    original = create(db, command_case, key)
    later = commands.update_draft(
        db,
        request(),
        actor,
        scope,
        original.id,
        schemas.DraftPatch(expected_version=1, title="Later content"),
    )
    assert later.version == 2
    assert create(db, command_case, key).model_dump(mode="json") == original.model_dump(
        mode="json"
    )
    changed = schemas.RequestCreate(
        **(payload(ids["node"]) | {"title": "Other content"})
    )
    fail(
        lambda: commands.create_request(db, request(), actor, scope, changed, key),
        "IDEMPOTENCY_CONFLICT",
    )
    fail(
        lambda: commands.update_draft(
            db,
            request(),
            actor,
            scope,
            original.id,
            schemas.DraftPatch(expected_version=1, title="Stale"),
        ),
        "VERSION_CONFLICT",
    )
    grant = db.scalar(
        select(MembershipUnitScope).where(
            MembershipUnitScope.membership_id == ids["member_a"],
            MembershipUnitScope.node_id == ids["node"],
        )
    )
    grant.active = False
    db.flush()
    fail(lambda: create(db, command_case, key), "UNIT_SCOPE_DENIED")
    assert (
        db.scalar(
            select(func.count())
            .select_from(RequestCommandReceipt)
            .where(RequestCommandReceipt.request_id == original.id)
        )
        == 1
    )


def test_audit_failure_rolls_back_commands(db, command_case, monkeypatch):
    from app.procurement.requests import events

    before = db.scalar(select(func.count()).select_from(PurchaseRequest))

    def unavailable(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(events, "append_event", unavailable)
    with pytest.raises(RuntimeError), db.begin_nested():
        create(db, command_case)
    assert db.scalar(select(func.count()).select_from(PurchaseRequest)) == before
    assert db.scalar(select(func.count()).select_from(RequestCommandReceipt)) == 0


def test_policy_admin_patch_prospective(admin, member, db, command_case):
    ids, *_ = command_case
    db.commit()
    headers = select_context(admin, ids["contract_a"])
    path = "/api/contract/purchase-request-policy"
    assert admin.get(path, headers=headers).json() == {
        "approval_mode": "REQUIRED",
        "version": 0,
    }
    result = admin.patch(
        path,
        headers=headers,
        json={
            "approval_mode": "NOT_REQUIRED",
            "expected_version": 0,
            "reason": "Single-stage procurement contract",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json() == {"approval_mode": "NOT_REQUIRED", "version": 1}
    assert (
        admin.patch(
            path,
            headers=headers,
            json={
                "approval_mode": "REQUIRED",
                "expected_version": 0,
                "reason": "Stale",
            },
        ).status_code
        == 409
    )
    customer = select_context(member, ids["contract_a"])
    assert (
        member.patch(
            path,
            headers=customer,
            json={
                "approval_mode": "REQUIRED",
                "expected_version": 1,
                "reason": "Forbidden",
            },
        ).status_code
        == 403
    )
    assert (
        admin.patch(
            path,
            headers=headers,
            json={
                "approval_mode": "UNKNOWN",
                "expected_version": 1,
                "reason": "Invalid",
            },
        ).status_code
        == 422
    )


@pytest.mark.parametrize("mode", ["REQUIRED", "NOT_REQUIRED"])
def test_both_policy_flows_retries_versions_revalidation(db, command_case, mode):
    from app.procurement.requests.models import ContractRequestPolicy
    from app.tenancy.models import TenantRolePermission

    ids, actor, scope, *_ = command_case
    commands, schemas = api()
    db.add(
        ContractRequestPolicy(
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            approval_mode=mode,
            version=1,
        )
    )
    db.flush()
    before = triage(db, command_case)
    key = uuid4()
    result = act(db, command_case, before, "request-approval", key=key)
    assert act(db, command_case, before, "request-approval", key=key).model_dump(
        mode="json"
    ) == result.model_dump(mode="json")
    fail(
        lambda: commands.transition_request(
            db,
            request(),
            actor,
            scope,
            before.id,
            "request-approval",
            schemas.VersionCommand(expected_version=before.version + 1),
            key,
        ),
        "IDEMPOTENCY_CONFLICT",
    )
    fail(lambda: act(db, command_case, before, "request-approval"), "VERSION_CONFLICT")
    permission = db.scalar(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["role_basic"],
            TenantRolePermission.capability == "procurement.requests.triage",
        )
    )
    permission.active = False
    db.flush()
    fail(
        lambda: act(db, command_case, before, "request-approval", key=key),
        "CAPABILITY_DENIED",
    )


def test_policy_change_preserves_pending_human_decision(db, command_case):
    from app.procurement.requests.models import ContractRequestPolicy

    _, _, scope, *_ = command_case
    pending = act(db, command_case, triage(db, command_case), "request-approval")
    db.add(
        ContractRequestPolicy(
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            approval_mode="NOT_REQUIRED",
            version=1,
        )
    )
    db.flush()
    approved = act(db, command_case, pending, "approve", who="buyer")
    assert approved.approval_decision_kind == "HUMAN"
    assert (
        approved.approval_mode == "REQUIRED" and approved.approval_policy_version == 0
    )
    next_request = act(db, command_case, triage(db, command_case), "request-approval")
    assert (
        next_request.approval_decision_kind == "POLICY_WAIVER"
        and next_request.approval_policy_version == 1
    )


def test_buyer_read_unit_revocation_blocks_execution(db, command_case):
    from app.tenancy.models import TenantRolePermission

    commands, schemas = api()
    ids, actor, scope, buyer, buyer_scope = command_case
    request_permissions(db, ids, ids["buyer_role"], ["create", "read_own"])
    own_case = (ids, buyer, buyer_scope, actor, scope)
    row = act(db, own_case, triage(db, own_case), "request-approval")
    row = act(db, own_case, row, "approve", who="buyer")
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
    # The buyer/requester retains read_own, but buyer execution requires read_unit.
    permission = db.scalar(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["buyer_role"],
            TenantRolePermission.capability == "procurement.requests.read_unit",
        )
    )
    permission.active = False
    db.flush()
    fail(
        lambda: act(db, command_case, row, "start-fulfillment", who="buyer"),
        "CAPABILITY_DENIED",
    )


def test_incomplete_submit_draft_unit_change_and_note_limits(db, command_case):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    row = commands.create_request(
        db,
        request(),
        actor,
        scope,
        schemas.RequestCreate(requesting_node_id=ids["node"], title="Incomplete"),
        uuid4(),
    )
    fail(lambda: act(db, command_case, row, "submit"), "VALIDATION_ERROR")
    fail(
        lambda: commands.update_draft(
            db,
            request(),
            actor,
            scope,
            row.id,
            schemas.DraftPatch(
                expected_version=1, requesting_node_id=ids["second_node"]
            ),
        ),
        "UNIT_SCOPE_DENIED",
    )
    fail(
        lambda: commands.add_note(
            db,
            request(),
            actor,
            scope,
            row.id,
            schemas.NoteCommand(expected_version=1, text="Must be submitted"),
            uuid4(),
        ),
        "INVALID_TRANSITION",
    )
    from pydantic import ValidationError

    for value in ("", "x" * 4001):
        with pytest.raises(ValidationError):
            schemas.NoteCommand(expected_version=1, text=value)


def test_assignment_http_opaque_context_and_invalid_candidate(member, db, command_case):
    ids, *_ = command_case
    row = act(db, command_case, triage(db, command_case), "request-approval")
    row = act(db, command_case, row, "approve", who="buyer")
    db.commit()
    headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    path = f"/api/procurement/requests/{row.id}/assign"
    malformed = member.post(
        path,
        headers=headers,
        json={
            "expected_version": row.version,
            "buyer_membership_id": "invalid-private-input",
        },
    )
    assert (
        malformed.status_code == 422 and "invalid-private-input" not in malformed.text
    )
    foreign = member.post(
        path,
        headers=headers,
        json={
            "expected_version": row.version,
            "buyer_membership_id": str(ids["member_b"]),
        },
    )
    assert foreign.status_code == 403 and "other@example" not in foreign.text
    result = member.post(
        path,
        headers=headers,
        json={
            "expected_version": row.version,
            "buyer_membership_id": str(ids["buyer_member"]),
        },
    )
    assert result.status_code == 200, result.text
    replay = member.post(
        path,
        headers=headers,
        json={
            "expected_version": row.version,
            "buyer_membership_id": str(ids["buyer_member"]),
        },
    )
    assert replay.json() == result.json()


@pytest.mark.parametrize("command", ["reject", "cancel"])
def test_reason_transitions_private_evidence_and_exact_retry(db, command_case, command):
    before = triage(db, command_case)
    key = uuid4()
    result = act(
        db,
        command_case,
        before,
        command,
        key=key,
        reason="Operational evidence requiring correction",
    )
    assert result.status == ("REJECTED" if command == "reject" else "CANCELLED")
    replay = act(
        db,
        command_case,
        before,
        command,
        key=key,
        reason="Operational evidence requiring correction",
    )
    assert replay.model_dump(mode="json") == result.model_dump(mode="json")
    event = db.scalar(
        select(PurchaseRequestEvent).where(
            PurchaseRequestEvent.request_id == result.id,
            PurchaseRequestEvent.aggregate_version == result.version,
        )
    )
    assert event.reason == "Operational evidence requiring correction"
    assert event.payload["from_status"] == "IN_TRIAGE"


def test_operational_scope_hides_request_controls_without_eligible_node(
    db, command_case
):
    from app.tenancy.operational_scope import operational_scope_view
    from tests.fixtures.purchase_request_policy import request_grants

    ids, actor, scope, *_ = command_case
    for grant in db.scalars(
        select(MembershipUnitScope).where(
            MembershipUnitScope.membership_id == ids["member_a"]
        )
    ):
        grant.active = False
    request_grants(db, ids, ids["member_a"], [ids["company"]])
    scope_view = operational_scope_view(db, actor, scope)
    assert scope_view.customer_scope.organization_nodes[0].kind == "COMPANY"
    assert not any(
        code.startswith("procurement.requests.")
        for code in scope_view.customer_scope.capabilities
    )


def test_http_command_csrf_version_key_and_content_freeze(member, db, command_case):
    ids, *_ = command_case
    db.commit()
    headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    row = member.post(
        "/api/procurement/requests", headers=headers, json=payload(ids["node"])
    )
    assert row.status_code == 201
    path = f"/api/procurement/requests/{row.json()['id']}"
    missing_key = member.post(
        path + "/submit",
        headers={"X-HiAtlas-Context": headers["X-HiAtlas-Context"]},
        json={"expected_version": 1},
    )
    assert missing_key.status_code == 422
    bad_mode = member.post(
        path + "/submit",
        headers=headers,
        json={"expected_version": 1, "approval_mode": "NOT_REQUIRED"},
    )
    assert bad_mode.status_code == 422 and bad_mode.json()["code"] == "VALIDATION_ERROR"
    submitted = member.post(
        path + "/submit", headers=headers, json={"expected_version": 1}
    )
    assert submitted.status_code == 200 and submitted.json()["status"] == "SUBMITTED"
    assert submitted.json()["version"] == 2 and submitted.json()["submitted_at"]
    duplicate = member.post(
        path + "/submit", headers=headers, json={"expected_version": 1}
    )
    assert duplicate.json() == submitted.json()
    changed = member.patch(
        path, headers=headers, json={"expected_version": 2, "items": []}
    )
    assert changed.status_code == 409 and changed.json()["code"] == "INVALID_TRANSITION"
    denied = member.post(
        path + "/start-triage",
        headers=headers | {"x-csrf-token": "invalid"},
        json={"expected_version": 2},
    )
    assert denied.status_code == 403 and denied.json()["code"] == "CSRF_INVALID"


@pytest.mark.parametrize("foreign", [False, True])
def test_draft_item_ids_are_scoped_and_preserved(db, command_case, foreign):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    row = create(db, command_case)
    original = row.items[0]
    values = {
        "id": ids["other_item"] if foreign else original.id,
        "description": "Updated actual equipment",
        "requested_quantity": "3.125000",
        "uom_code": "UN",
    }
    patch = schemas.DraftPatch(expected_version=row.version, items=[values])
    if foreign:
        fail(
            lambda: commands.update_draft(db, request(), actor, scope, row.id, patch),
            "NOT_FOUND",
        )
        stored = db.get(PurchaseRequest, row.id)
        assert stored.version == 1
    else:
        result = commands.update_draft(db, request(), actor, scope, row.id, patch)
        assert result.items[0].id == original.id
        assert result.items[0].created_at == original.created_at
        assert result.items[0].requested_quantity == "3.125000"
        assert result.version == 2


@pytest.mark.parametrize("remove", [False, True])
def test_draft_item_edit_preserves_existing_attachment_reference(
    db, command_case, remove
):
    from hashlib import sha256

    from app.procurement.requests.models import RequestAttachment

    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    row = create(db, command_case)
    item = row.items[0]
    content = b"Actual equipment specification"
    attachment = RequestAttachment(
        tenant_id=scope.tenant_id,
        contract_id=scope.contract_id,
        request_id=row.id,
        item_id=item.id,
        uploader_user_id=actor.user_id,
        uploader_membership_id=ids["member_a"],
        filename="specification.txt",
        media_type="text/plain",
        digest=sha256(content).hexdigest(),
        size=len(content),
        content=content,
    )
    db.add(attachment)
    db.flush()
    if remove:
        receipts = db.scalar(select(func.count()).select_from(RequestCommandReceipt))
        evidence = db.scalar(select(func.count()).select_from(PurchaseRequestEvent))
        with db.begin_nested():
            fail(
                lambda: commands.update_draft(
                    db,
                    request(),
                    actor,
                    scope,
                    row.id,
                    schemas.DraftPatch(expected_version=1, items=[]),
                ),
                "ITEM_HAS_ATTACHMENTS",
            )
        assert db.get(PurchaseRequest, row.id).version == 1
        assert db.get(PurchaseRequestItem, item.id) is not None
        assert (
            db.scalar(select(func.count()).select_from(RequestCommandReceipt))
            == receipts
        )
        assert (
            db.scalar(select(func.count()).select_from(PurchaseRequestEvent))
            == evidence
        )
        return
    result = commands.update_draft(
        db,
        request(),
        actor,
        scope,
        row.id,
        schemas.DraftPatch(
            expected_version=1,
            items=[
                {
                    "id": item.id,
                    "description": "Revised specification",
                    "requested_quantity": "4",
                    "uom_code": "UN",
                }
            ],
        ),
    )
    assert result.items[0].id == item.id
    assert result.attachments[0].item_id == item.id
    assert result.attachments[0].digest == sha256(content).hexdigest()


@pytest.mark.parametrize("count", [2, 100])
def test_draft_item_reorder_retains_identity(db, command_case, count):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    values = payload(ids["node"])
    values["items"] *= count
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**values), uuid4()
    )
    if count == 100:
        from hashlib import sha256

        from app.procurement.requests.models import RequestAttachment

        content = b"Attached equipment reference"
        db.add(
            RequestAttachment(
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                request_id=row.id,
                item_id=row.items[0].id,
                uploader_user_id=actor.user_id,
                uploader_membership_id=ids["member_a"],
                filename="reference.txt",
                media_type="text/plain",
                digest=sha256(content).hexdigest(),
                size=len(content),
                content=content,
            )
        )
        db.flush()
    items = [
        {
            "id": item.id,
            "description": item.description,
            "requested_quantity": item.requested_quantity,
            "uom_code": item.uom_code,
        }
        for item in reversed(row.items)
    ]
    result = commands.update_draft(
        db,
        request(),
        actor,
        scope,
        row.id,
        schemas.DraftPatch(expected_version=1, items=items),
    )
    assert [item.id for item in result.items] == [
        item.id for item in reversed(row.items)
    ]
    assert [item.position for item in result.items] == list(range(1, count + 1))
    if count == 100:
        assert result.attachments[0].item_id == row.items[0].id


def test_duplicate_item_positions_remain_blocked_at_commit(db, command_case):
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    values = payload(ids["node"])
    values["items"] *= 2
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**values), uuid4()
    )
    db.commit()
    db.execute(text("SET CONSTRAINTS uq_purchase_request_item_position DEFERRED"))
    db.execute(
        text(
            "UPDATE purchase_request_items SET position=1 WHERE request_id=:request_id"
        ),
        {"request_id": row.id},
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert list(
        db.scalars(
            select(PurchaseRequestItem.position)
            .where(PurchaseRequestItem.request_id == row.id)
            .order_by(PurchaseRequestItem.position)
        )
    ) == [1, 2]


@pytest.mark.parametrize("missing_reason", [None, "   "])
def test_urgent_submit_requires_distinct_reason(db, command_case, missing_reason):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    values = payload(ids["node"]) | {"priority": "URGENT"}
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**values), uuid4()
    )
    receipts = db.scalar(select(func.count()).select_from(RequestCommandReceipt))
    evidence = db.scalar(select(func.count()).select_from(PurchaseRequestEvent))
    body = schemas.VersionCommand(expected_version=1)
    if missing_reason is not None:
        # Canonical DTOs are mutable for internal callers; service validation stays defensive.
        body = schemas.ReasonCommand(
            expected_version=1, reason="Initially validated reason"
        )
        body.reason = missing_reason
    with db.begin_nested():
        fail(
            lambda: commands.transition_request(
                db, request(), actor, scope, row.id, "submit", body, uuid4()
            ),
            "VALIDATION_ERROR",
        )
    stored = db.get(PurchaseRequest, row.id)
    assert stored.status == "DRAFT" and stored.version == 1
    assert stored.justification == values["justification"]
    assert (
        db.scalar(select(func.count()).select_from(RequestCommandReceipt)) == receipts
    )
    assert db.scalar(select(func.count()).select_from(PurchaseRequestEvent)) == evidence


@pytest.mark.parametrize("revocation", ["create", "read"])
def test_urgent_submit_reason_evidence_retry_and_authority(
    db, command_case, revocation
):
    from app.tenancy.models import TenantRolePermission

    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    values = payload(ids["node"]) | {"priority": "URGENT"}
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**values), uuid4()
    )
    key = uuid4()
    body = schemas.ReasonCommand(
        expected_version=1, reason="Urgent safety risk requires immediate action"
    )
    result = commands.transition_request(
        db, request(), actor, scope, row.id, "submit", body, key
    )
    assert result.status == "SUBMITTED" and result.version == 2
    stored = db.get(PurchaseRequest, row.id)
    assert (
        stored.justification == values["justification"]
        and stored.justification != body.reason
    )
    evidence = db.scalar(
        select(PurchaseRequestEvent).where(
            PurchaseRequestEvent.request_id == row.id,
            PurchaseRequestEvent.aggregate_version == 2,
        )
    )
    assert evidence.reason == body.reason
    audit = db.get(AuditEvent, evidence.audit_event_id)
    assert audit.reason is None
    assert body.reason not in str(audit.before_state) + str(audit.after_state)
    receipt_count = db.scalar(select(func.count()).select_from(RequestCommandReceipt))
    event_count = db.scalar(select(func.count()).select_from(PurchaseRequestEvent))
    replay = commands.transition_request(
        db, request(), actor, scope, row.id, "submit", body, key
    )
    assert replay.model_dump(mode="json") == result.model_dump(mode="json")
    fail(
        lambda: commands.transition_request(
            db,
            request(),
            actor,
            scope,
            row.id,
            "submit",
            schemas.ReasonCommand(
                expected_version=1, reason="A changed urgent risk explanation"
            ),
            key,
        ),
        "IDEMPOTENCY_CONFLICT",
    )
    assert (
        db.scalar(select(func.count()).select_from(RequestCommandReceipt))
        == receipt_count
    )
    assert (
        db.scalar(select(func.count()).select_from(PurchaseRequestEvent)) == event_count
    )
    codes = ["create"] if revocation == "create" else ["read_own", "read_unit"]
    for permission in db.scalars(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["role_basic"],
            TenantRolePermission.capability.in_(
                ["procurement.requests." + code for code in codes]
            ),
        )
    ):
        permission.active = False
    db.flush()
    fail(
        lambda: commands.transition_request(
            db, request(), actor, scope, row.id, "submit", body, key
        ),
        "CAPABILITY_DENIED",
    )


@pytest.mark.parametrize("bad_reason", [None, "   ", "a" * 2001])
def test_http_urgent_submit_rejects_invalid_reason(
    member, db, command_case, bad_reason
):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    values = payload(ids["node"]) | {"priority": "URGENT"}
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**values), uuid4()
    )
    db.commit()
    headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    body = {"expected_version": 1}
    if bad_reason is not None:
        body["reason"] = bad_reason
    response = member.post(
        f"/api/procurement/requests/{row.id}/submit", headers=headers, json=body
    )
    assert response.status_code == 422 and response.json()["code"] == "VALIDATION_ERROR"
    stored = db.get(PurchaseRequest, row.id)
    db.refresh(stored)
    assert stored.status == "DRAFT" and stored.version == 1
    assert (
        len(
            list(
                db.scalars(
                    select(PurchaseRequestEvent).where(
                        PurchaseRequestEvent.request_id == row.id
                    )
                )
            )
        )
        == 1
    )


@pytest.mark.parametrize("priority", ["NORMAL", "URGENT"])
def test_http_submit_reason_contract_and_exact_replay(
    member, db, command_case, priority
):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    values = payload(ids["node"]) | {"priority": priority}
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**values), uuid4()
    )
    db.commit()
    headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    body = {"expected_version": 1}
    if priority == "URGENT":
        body["reason"] = "Urgent immediate safety requirement"
    path = f"/api/procurement/requests/{row.id}/submit"
    response = member.post(path, headers=headers, json=body)
    assert response.status_code == 200 and response.json()["status"] == "SUBMITTED"
    assert response.headers["Cache-Control"] == "no-store"
    assert member.post(path, headers=headers, json=body).json() == response.json()
    if priority == "URGENT":
        changed = member.post(
            path, headers=headers, json=body | {"reason": "Different reason"}
        )
        assert (
            changed.status_code == 409
            and changed.json()["code"] == "IDEMPOTENCY_CONFLICT"
        )
        evidence = db.scalar(
            select(PurchaseRequestEvent).where(
                PurchaseRequestEvent.request_id == row.id,
                PurchaseRequestEvent.aggregate_version == 2,
            )
        )
        assert evidence.reason == body["reason"]


def test_urgent_submit_reason_does_not_replace_ordinary_justification(db, command_case):
    commands, schemas = api()
    ids, actor, scope, *_ = command_case
    values = payload(ids["node"]) | {"priority": "URGENT", "justification": ""}
    row = commands.create_request(
        db, request(), actor, scope, schemas.RequestCreate(**values), uuid4()
    )
    fail(
        lambda: commands.transition_request(
            db,
            request(),
            actor,
            scope,
            row.id,
            "submit",
            schemas.ReasonCommand(expected_version=1, reason="Urgent safety reason"),
            uuid4(),
        ),
        "VALIDATION_ERROR",
    )
    assert db.get(PurchaseRequest, row.id).status == "DRAFT"
