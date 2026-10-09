"""Persisted private reads: scope must constrain counts, rows and names first."""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.errors import ApiError
from app.identity.models import User
from app.organization.models import MembershipUnitScope, OrganizationNode
from app.procurement.requests.models import PurchaseRequest, PurchaseRequestEvent
from app.tenancy.models import Membership, TenantRolePermission
from tests.fixtures.purchase_request_policy import request_permissions
from tests.helpers import select_context


def queries():
    from app.procurement.requests import queries

    return queries


def filters(**kwargs):
    from app.procurement.requests.schemas import RequestFilters

    return RequestFilters(**kwargs)


def rejected(call, status):
    with pytest.raises(ApiError) as failure:
        call()
    assert failure.value.status == status
    return failure.value.code


@pytest.fixture
def query_case(db, request_policy_case):
    ids, actor, scope, buyer, buyer_scope = request_policy_case
    request_permissions(db, ids, ids["role_basic"], ["read_unit"])
    own = db.get(PurchaseRequest, ids["request"])
    own.status = "SUBMITTED"
    for key, member, user, node, status in [
        ("buyer_draft", "buyer_member", "buyer", "node", "DRAFT"),
        ("buyer_submitted", "buyer_member", "buyer", "node", "SUBMITTED"),
        ("out_of_unit", "member_a", "user", "second_node", "SUBMITTED"),
        ("foreign_request", "member_b", "other_user", "foreign_node", "SUBMITTED"),
    ]:
        ids[key] = uuid4()
        foreign = key == "foreign_request"
        db.add(
            PurchaseRequest(
                id=ids[key],
                tenant_id=ids["tenant_b" if foreign else "tenant_a"],
                contract_id=ids["contract_b" if foreign else "contract_a"],
                requester_membership_id=ids[member],
                requester_user_id=ids[user],
                requesting_node_id=ids[node],
                title="FOREIGN_NODE" if foreign else key,
                status=status,
            )
        )
    ids["other_contract_node"], ids["other_contract_request"] = uuid4(), uuid4()
    db.add(
        OrganizationNode(
            id=ids["other_contract_node"],
            tenant_id=ids["tenant_a"],
            contract_id=ids["contract_a2"],
            kind="UNIT",
            code="FOREIGN_CONTRACT",
            name="FOREIGN_NODE",
        )
    )
    db.flush()
    db.add(
        PurchaseRequest(
            id=ids["other_contract_request"],
            tenant_id=ids["tenant_a"],
            contract_id=ids["contract_a2"],
            requester_membership_id=ids["member_a2"],
            requester_user_id=ids["user"],
            requesting_node_id=ids["other_contract_node"],
            title="FOREIGN_NODE",
        )
    )
    db.add(
        PurchaseRequestEvent(
            tenant_id=ids["tenant_a"],
            contract_id=ids["contract_a"],
            request_id=ids["request"],
            sequence=1,
            aggregate_version=1,
            action="procurement.request.created",
            actor_user_id=ids["user"],
            actor_membership_id=ids["member_a"],
            tenant_role_id=ids["role_basic"],
            tenant_role_code="ROLE_BASIC",
            payload={"to_status": "DRAFT"},
            audit_event_id=ids["audit"],
        )
    )
    db.flush()
    return ids, actor, scope, buyer, buyer_scope


def test_count_cursor_filters_never_leak(db, query_case):
    ids, actor, scope, buyer, buyer_scope = query_case
    page = queries().list_requests(db, actor, scope, filters(limit=1))
    assert page.total == 2
    assert page.next_cursor
    second = queries().list_requests(
        db, actor, scope, filters(limit=1, cursor=page.next_cursor)
    )
    assert {page.items[0].id, second.items[0].id} == {
        ids["request"],
        ids["other_request"],
    }
    unit = queries().list_requests(db, actor, scope, filters(visibility="unit"))
    assert unit.total == 3
    assert {row.id for row in unit.items} == {
        ids["request"],
        ids["other_request"],
        ids["buyer_submitted"],
    }
    assert "FOREIGN_NODE" not in unit.model_dump_json()
    submitted = queries().list_requests(
        db, actor, scope, filters(visibility="unit", status="SUBMITTED")
    )
    assert submitted.total == 2
    rejected(
        lambda: queries().list_requests(
            db, actor, scope, filters(status="SUBMITTED", cursor=page.next_cursor)
        ),
        422,
    )
    rejected(
        lambda: queries().list_requests(
            db, buyer, buyer_scope, filters(cursor=page.next_cursor)
        ),
        422,
    )
    rejected(
        lambda: queries().list_requests(
            db, actor, scope, filters(requester_membership_id=ids["buyer_member"])
        ),
        422,
    )
    assert (
        queries()
        .list_requests(db, actor, scope, filters(node_id=ids["foreign_node"]))
        .total
        == 0
    )
    for grant in db.scalars(
        select(MembershipUnitScope).where(
            MembershipUnitScope.membership_id == ids["member_a"]
        )
    ):
        grant.active = False
    db.flush()
    assert queries().list_requests(db, actor, scope, filters()).total == 0


def test_private_draft_and_history_without_audit_read(db, query_case):
    ids, actor, scope, buyer, buyer_scope = query_case
    assert (
        queries().get_request(db, actor, scope, ids["other_request"]).status == "DRAFT"
    )
    rejected(
        lambda: queries().get_request(db, buyer, buyer_scope, ids["other_request"]), 403
    )
    rejected(
        lambda: queries().request_history(
            db, buyer, buyer_scope, ids["other_request"], 10, None
        ),
        403,
    )
    history = queries().request_history(db, actor, scope, ids["request"], 10, None)
    assert history.total == 1
    assert history.items[0].payload.to_status == "DRAFT"
    assert "email" not in history.model_dump_json()


def test_minimal_scoped_candidates(db, query_case):
    ids, actor, scope, _, _ = query_case
    page = queries().buyer_candidates(db, actor, scope, ids["node"], 1, None)
    assert page.total == 1
    assert page.items[0].model_dump() == {
        "membership_id": ids["buyer_member"],
        "display_name": "Actual buyer",
    }
    assert "email" not in page.model_dump_json()
    rejected(
        lambda: queries().buyer_candidates(
            db, actor, scope, ids["foreign_node"], 10, None
        ),
        403,
    )
    db.get(User, ids["buyer"]).blocked = True
    db.flush()
    assert queries().buyer_candidates(db, actor, scope, ids["node"], 1, None).total == 0
    db.get(User, ids["buyer"]).blocked = False
    db.get(
        TenantRolePermission, (ids["buyer_role"], "procurement.requests.fulfill")
    ).active = False
    db.flush()
    assert queries().buyer_candidates(db, actor, scope, ids["node"], 1, None).total == 0


def test_uniform_foreign_missing_404(db, query_case):
    ids, actor, scope, _, _ = query_case
    for method in [
        lambda key: queries().get_request(db, actor, scope, key),
        lambda key: queries().request_history(db, actor, scope, key, 10, None),
    ]:
        rejected(lambda method=method: method(ids["other_contract_request"]), 404)
        assert (
            rejected(lambda method=method: method(ids["foreign_request"]), 404)
            == rejected(lambda method=method: method(uuid4()), 404)
            == "NOT_FOUND"
        )


def test_routes_are_private_and_revalidate(member, db, query_case):
    ids, _, _, _, _ = query_case
    db.commit()
    headers = select_context(member, ids["contract_a"])
    root = "/api/procurement/requests"
    for path in [
        root,
        f"{root}/{ids['request']}",
        f"{root}/{ids['request']}/history",
        f"{root}/buyer-candidates?requesting_node_id={ids['node']}",
    ]:
        response = member.get(path, headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
    assert member.get(root, headers=headers, params={"limit": 101}).status_code == 422
    assert (
        member.get(root, headers=headers, params={"cursor": "x" * 2049}).status_code
        == 422
    )
    db.get(Membership, ids["member_a"]).blocked = True
    db.commit()
    assert member.get(root, headers=headers).status_code == 403


def test_cursor_scope_kind_version_and_bounds(db, query_case):
    import base64
    import json

    from tests.fixtures.purchase_request_policy import request_identity

    ids, actor, scope, _, _ = query_case
    page = queries().list_requests(db, actor, scope, filters(limit=1))
    other_actor, other_scope = request_identity(db, ids, actor.user_id)
    rejected(
        lambda: queries().list_requests(
            db, other_actor, other_scope, filters(limit=1, cursor=page.next_cursor)
        ),
        422,
    )
    rejected(
        lambda: queries().request_history(
            db, actor, scope, ids["request"], 1, page.next_cursor
        ),
        422,
    )
    for cursor in [
        "not-base64",
        base64.urlsafe_b64encode(
            json.dumps({"v": 2, "scope": "wrong", "offset": 0}).encode()
        ).decode(),
    ]:
        rejected(
            lambda cursor=cursor: queries().list_requests(
                db, actor, scope, filters(limit=1, cursor=cursor)
            ),
            422,
        )


def test_unit_filters_and_candidates_need_read_unit(db, query_case):
    ids, actor, scope, _, _ = query_case
    page = queries().list_requests(
        db,
        actor,
        scope,
        filters(visibility="unit", requester_membership_id=ids["buyer_member"]),
    )
    assert page.total == 1 and page.items[0].id == ids["buyer_submitted"]
    assert (
        queries()
        .list_requests(
            db,
            actor,
            scope,
            filters(visibility="unit", buyer_membership_id=ids["buyer_member"]),
        )
        .total
        == 0
    )
    db.get(
        TenantRolePermission, (ids["role_basic"], "procurement.requests.read_unit")
    ).active = False
    db.flush()
    rejected(
        lambda: queries().buyer_candidates(db, actor, scope, ids["node"], 10, None), 403
    )
    rejected(
        lambda: queries().list_requests(db, actor, scope, filters(visibility="unit")),
        403,
    )


@pytest.mark.parametrize(
    "gate",
    [
        "active_user",
        "blocked_user",
        "internal",
        "member",
        "blocked_member",
        "pending_member",
        "role",
        "fulfill",
        "read_unit",
        "grant",
    ],
)
def test_candidate_eligibility_matches_fresh_policy(db, query_case, gate):
    from app.identity.models import PlatformRoleAssignment
    from app.procurement.requests import policy
    from app.tenancy.models import TenantRole

    ids, actor, scope, _, _ = query_case
    if gate in ("active_user", "blocked_user"):
        setattr(
            db.get(User, ids["buyer"]),
            "active" if gate == "active_user" else "blocked",
            gate == "blocked_user",
        )
    elif gate == "internal":
        db.add(PlatformRoleAssignment(user_id=ids["buyer"], role="PLATFORM_ADMIN"))
    elif gate in ("member", "blocked_member", "pending_member"):
        setattr(
            db.get(Membership, ids["buyer_member"]),
            {
                "member": "active",
                "blocked_member": "blocked",
                "pending_member": "invitation_pending",
            }[gate],
            gate != "member",
        )
    elif gate == "role":
        db.get(TenantRole, ids["buyer_role"]).active = False
    elif gate in ("fulfill", "read_unit"):
        db.get(
            TenantRolePermission, (ids["buyer_role"], f"procurement.requests.{gate}")
        ).active = False
    else:
        db.scalar(
            select(MembershipUnitScope).where(
                MembershipUnitScope.membership_id == ids["buyer_member"]
            )
        ).active = False
    db.flush()
    rejected(
        lambda: policy.require_buyer_candidate(
            db, actor, scope, ids["node"], ids["buyer_member"]
        ),
        403,
    )
    page = queries().buyer_candidates(db, actor, scope, ids["node"], 1, None)
    assert page.total == 0 and page.items == [] and page.next_cursor is None


def test_candidates_paginate_only_eligible_contract_members(db, query_case):
    from tests.fixtures.purchase_request_policy import request_grants

    ids, actor, scope, _, _ = query_case
    extra_user, extra_member = uuid4(), uuid4()
    db.add(
        User(
            id=extra_user,
            email_normalized="eligible@example.test",
            display_name="Another eligible buyer",
        )
    )
    db.flush()
    db.add(
        Membership(
            id=extra_member,
            user_id=extra_user,
            tenant_id=ids["tenant_a"],
            contract_id=ids["contract_a"],
            role_id=ids["buyer_role"],
        )
    )
    db.flush()
    request_grants(db, ids, extra_member, [ids["node"]])
    first = queries().buyer_candidates(db, actor, scope, ids["node"], 1, None)
    assert first.total == 2 and len(first.items) == 1 and first.next_cursor
    second = queries().buyer_candidates(
        db, actor, scope, ids["node"], 1, first.next_cursor
    )
    assert second.total == 2 and second.next_cursor is None
    assert {first.items[0].membership_id, second.items[0].membership_id} == {
        ids["buyer_member"],
        extra_member,
    }
    request_grants(db, ids, ids["member_a"], [ids["second_node"]])
    rejected(
        lambda: queries().buyer_candidates(
            db, actor, scope, ids["second_node"], 1, first.next_cursor
        ),
        422,
    )


def test_history_cursor_and_revoked_scope(db, query_case):
    ids, actor, scope, _, _ = query_case
    for sequence in (2, 3):
        db.add(
            PurchaseRequestEvent(
                tenant_id=ids["tenant_a"],
                contract_id=ids["contract_a"],
                request_id=ids["request"],
                sequence=sequence,
                aggregate_version=sequence,
                action="procurement.request.note_added",
                actor_user_id=ids["user"],
                actor_membership_id=ids["member_a"],
                tenant_role_id=ids["role_basic"],
                tenant_role_code="ROLE_BASIC",
                payload={"text": "Real requirement clarification"},
                audit_event_id=ids["audit"],
            )
        )
    db.flush()
    first = queries().request_history(db, actor, scope, ids["request"], 2, None)
    second = queries().request_history(
        db, actor, scope, ids["request"], 2, first.next_cursor
    )
    assert first.total == second.total == 3
    assert [event.sequence for event in first.items] == [1, 2]
    assert [event.sequence for event in second.items] == [3]
    assert second.next_cursor is None
    rejected(
        lambda: queries().request_history(
            db, actor, scope, ids["other_request"], 2, first.next_cursor
        ),
        422,
    )
    db.scalar(
        select(MembershipUnitScope).where(
            MembershipUnitScope.membership_id == ids["member_a"]
        )
    ).active = False
    db.flush()
    rejected(
        lambda: queries().request_history(
            db, actor, scope, ids["request"], 2, first.next_cursor
        ),
        403,
    )


def test_detail_projects_real_balances_metadata_and_current_buyer(db, query_case):
    from decimal import Decimal

    from app.procurement.requests.models import (
        RequestAttachment,
        RequestFulfillmentEntry,
    )

    ids, actor, scope, _, _ = query_case
    row = db.get(PurchaseRequest, ids["request"])
    row.buyer_membership_id = ids["buyer_member"]
    db.add(
        RequestFulfillmentEntry(
            tenant_id=ids["tenant_a"],
            contract_id=ids["contract_a"],
            request_id=ids["request"],
            item_id=ids["item"],
            quantity=Decimal("0.25"),
            uom_code="UN",
            actor_user_id=ids["buyer"],
            actor_membership_id=ids["buyer_member"],
            evidence="Recorded external receipt",
            reason="Actual partial delivery",
            aggregate_version=1,
        )
    )
    db.add(
        RequestAttachment(
            tenant_id=ids["tenant_a"],
            contract_id=ids["contract_a"],
            request_id=ids["request"],
            uploader_user_id=ids["user"],
            uploader_membership_id=ids["member_a"],
            filename="specification.txt",
            media_type="text/plain",
            digest="a" * 64,
            size=4,
            content=b"need",
        )
    )
    db.flush()
    view = queries().get_request(db, actor, scope, ids["request"])
    assert view.fulfillment_state == "PARTIAL"
    assert Decimal(view.items[0].fulfilled_quantity) == Decimal("0.25")
    assert Decimal(view.items[0].remaining_quantity) == Decimal("0.75")
    assert view.buyer.membership_id == ids["buyer_member"]
    assert view.attachments[0].filename == "specification.txt"
    assert "content" not in view.attachments[0].model_dump()
    assert "email" not in view.model_dump_json()
    db.get(User, ids["buyer"]).blocked = True
    db.flush()
    assert queries().get_request(db, actor, scope, ids["request"]).buyer is None


def test_own_list_read_unit_fallback_is_private(db, query_case):
    ids, _, _, buyer, buyer_scope = query_case
    page = queries().list_requests(db, buyer, buyer_scope, filters())
    assert page.total == 2
    assert {row.id for row in page.items} == {
        ids["buyer_draft"],
        ids["buyer_submitted"],
    }
    rejected(
        lambda: queries().list_requests(
            db, buyer, buyer_scope, filters(requester_membership_id=ids["member_a"])
        ),
        422,
    )
    db.get(
        TenantRolePermission, (ids["buyer_role"], "procurement.requests.read_unit")
    ).active = False
    db.flush()
    rejected(lambda: queries().list_requests(db, buyer, buyer_scope, filters()), 403)
