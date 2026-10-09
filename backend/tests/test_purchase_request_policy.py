"""Real authorization boundaries: removing any gate must fail these tests."""

from dataclasses import replace

import pytest
from sqlalchemy import select

from app.core.errors import ApiError
from app.identity.models import AuthSession, PlatformRoleAssignment, User
from app.organization.models import (
    ContractModule,
    MembershipUnitScope,
    OrganizationNode,
)
from app.procurement.requests.models import PurchaseRequest
from app.tenancy.models import (
    AccessContext,
    Membership,
    TenantRole,
    TenantRolePermission,
)
from tests.fixtures.purchase_request_policy import (
    request_grants,
)


def policy():
    from app.procurement.requests import policy

    return policy


def denied(call, status=403):
    with pytest.raises(ApiError) as failure:
        call()
    assert failure.value.status == status


def test_custom_role_without_admin_permissions(db, request_policy_case):
    ids, actor, scope, _, _ = request_policy_case
    assert (
        policy().require_request_actor(db, actor, scope, "create").id == ids["member_a"]
    )
    assert (
        policy().require_request_unit(db, actor, scope, ids["node"], "create").id
        == ids["node"]
    )
    denied(lambda: policy().require_request_actor(db, actor, scope, "triage"))
    denied(lambda: policy().require_request_actor(db, actor, scope, "cancel"))
    denied(lambda: policy().require_request_actor(db, actor, scope, "roles.manage"))
    row = db.get(PurchaseRequest, ids["request"])
    policy().authorize_request_read(db, actor, scope, row)
    db.get(TenantRole, ids["role_basic"]).name = "PLATFORM_ADMIN"
    denied(lambda: policy().require_request_actor(db, actor, scope, "fulfill"))


@pytest.mark.parametrize(
    "mode,count", [("ALL", 2), ("RESTRICTED", 0), ("RESTRICTED", 1), ("RESTRICTED", 2)]
)
def test_all_zero_one_multiple_units(db, request_policy_case, mode, count):
    ids, actor, scope, _, _ = request_policy_case
    db.get(Membership, ids["member_a"]).unit_scope_mode = mode
    for grant in db.scalars(
        select(MembershipUnitScope).where(
            MembershipUnitScope.membership_id == ids["member_a"]
        )
    ):
        grant.active = count > 0
    if count == 2 and mode == "RESTRICTED":
        request_grants(db, ids, ids["member_a"], [ids["second_node"]])
    db.flush()
    for index, key in enumerate(["node", "second_node"]):
        check = lambda key=key: policy().require_request_unit(
            db, actor, scope, ids[key], "create"
        )
        if index < count:
            assert check().id == ids[key]
        else:
            denied(check)


def test_own_read_still_requires_scope(db, request_policy_case):
    ids, actor, scope, _, _ = request_policy_case
    row = db.get(PurchaseRequest, ids["request"])
    policy().authorize_request_read(db, actor, scope, row)
    grant = db.scalar(
        select(MembershipUnitScope).where(
            MembershipUnitScope.membership_id == ids["member_a"]
        )
    )
    grant.active = False
    db.flush()
    denied(lambda: policy().authorize_request_read(db, actor, scope, row))


def test_read_unit_never_reads_foreign_draft_or_infers_read_from_action(
    db, request_policy_case
):
    ids, actor, scope, buyer, buyer_scope = request_policy_case
    row = db.get(PurchaseRequest, ids["request"])
    denied(lambda: policy().authorize_request_read(db, buyer, buyer_scope, row))
    row.status = "SUBMITTED"
    db.flush()
    policy().authorize_request_read(db, buyer, buyer_scope, row)
    db.get(
        TenantRolePermission, (ids["buyer_role"], "procurement.requests.read_unit")
    ).active = False
    db.flush()
    assert (
        policy().require_request_actor(db, buyer, buyer_scope, "fulfill").id
        == ids["buyer_member"]
    )
    denied(lambda: policy().authorize_request_read(db, buyer, buyer_scope, row))
    db.get(
        TenantRolePermission, (ids["role_basic"], "procurement.requests.read_own")
    ).active = False
    db.flush()
    denied(lambda: policy().authorize_request_read(db, actor, scope, row))


@pytest.mark.parametrize("target", ["company", "foreign_node", "ancestor", "node"])
def test_company_ancestor_foreign_node_denied(db, request_policy_case, target):
    ids, actor, scope, _, _ = request_policy_case
    db.get(Membership, ids["member_a"]).unit_scope_mode = "ALL"
    node_id = ids.get(target, ids["node"])
    if target == "ancestor":
        db.get(OrganizationNode, ids["node"]).parent_id = ids["company"]
        db.get(OrganizationNode, ids["company"]).active = False
    elif target == "node":
        db.get(OrganizationNode, ids["node"]).active = False
    db.flush()
    denied(lambda: policy().require_request_unit(db, actor, scope, node_id, "create"))


@pytest.mark.parametrize("role", ["PLATFORM_ADMIN", "PLATFORM_SUPPORT"])
def test_internal_denied_even_with_membership_and_permission(
    db, request_policy_case, role
):
    ids, actor, scope, _, _ = request_policy_case
    db.add(PlatformRoleAssignment(user_id=actor.user_id, role=role))
    db.flush()
    denied(
        lambda: policy().require_request_unit(db, actor, scope, ids["node"], "create")
    )


@pytest.mark.parametrize(
    "target",
    [
        "permission",
        "module_active",
        "module_contracted",
        "role",
        "member",
        "blocked_member",
        "pending_member",
        "context",
        "foreign_scope",
        "session",
        "tenant",
        "contract",
        "user",
    ],
)
def test_actor_revalidates_every_gate(db, request_policy_case, target):
    ids, actor, scope, _, _ = request_policy_case
    assert (
        policy().require_request_unit(db, actor, scope, ids["node"], "create").id
        == ids["node"]
    )
    status = 403
    if target == "permission":
        db.get(
            TenantRolePermission, (ids["role_basic"], "procurement.requests.create")
        ).active = False
    elif target.startswith("module_"):
        module = db.scalar(
            select(ContractModule).where(
                ContractModule.contract_id == ids["contract_a"],
                ContractModule.code == "PROCUREMENT",
            )
        )
        if target == "module_contracted":
            module.active = False
        setattr(module, target.removeprefix("module_"), False)
    elif target in ("role", "member", "tenant", "contract"):
        from app.tenancy.models import Contract, Tenant

        model, key = {
            "role": (TenantRole, "role_basic"),
            "member": (Membership, "member_a"),
            "tenant": (Tenant, "tenant_a"),
            "contract": (Contract, "contract_a"),
        }[target]
        db.get(model, ids[key]).active = False
    elif target in ("blocked_member", "pending_member"):
        setattr(
            db.get(Membership, ids["member_a"]),
            "blocked" if target == "blocked_member" else "invitation_pending",
            True,
        )
    elif target == "context":
        db.get(AccessContext, scope.id).revoked_at = db.get(
            AccessContext, scope.id
        ).created_at
    elif target == "foreign_scope":
        scope = replace(scope, contract_id=ids["contract_a2"])
    elif target == "session":
        session = db.get(AuthSession, actor.session_id)
        session.revoked_at = session.created_at
        status = 401
    elif target == "user":
        db.get(User, actor.user_id).blocked = True
        status = 401
    db.flush()
    denied(
        lambda: policy().require_request_unit(db, actor, scope, ids["node"], "create"),
        status,
    )


@pytest.mark.parametrize(
    "target",
    [
        "valid",
        "foreign_contract",
        "foreign_tenant",
        "user_inactive",
        "user_blocked",
        "internal",
        "member_inactive",
        "member_blocked",
        "member_pending",
        "role_inactive",
        "fulfill",
        "read_unit",
        "scope",
        "node",
        "module",
    ],
)
def test_candidate_same_contract_current_scope_permissions(
    db, request_policy_case, target
):
    ids, actor, scope, _, _ = request_policy_case
    candidate_id = ids["buyer_member"]
    before = list(
        db.scalars(
            select(MembershipUnitScope.node_id).where(
                MembershipUnitScope.membership_id == candidate_id
            )
        )
    )
    assert (
        policy().require_buyer_candidate(db, actor, scope, ids["node"], candidate_id).id
        == candidate_id
    )
    if target == "foreign_contract":
        candidate_id = ids["member_a2"]
    elif target == "foreign_tenant":
        candidate_id = ids["member_b"]
    elif target.startswith("user_"):
        setattr(
            db.get(User, ids["buyer"]),
            "active" if target == "user_inactive" else "blocked",
            target == "user_blocked",
        )
    elif target == "internal":
        db.add(PlatformRoleAssignment(user_id=ids["buyer"], role="PLATFORM_ADMIN"))
    elif target.startswith("member_"):
        member = db.get(Membership, ids["buyer_member"])
        setattr(
            member,
            {
                "member_inactive": "active",
                "member_blocked": "blocked",
                "member_pending": "invitation_pending",
            }[target],
            target != "member_inactive",
        )
    elif target == "role_inactive":
        db.get(TenantRole, ids["buyer_role"]).active = False
    elif target in ("fulfill", "read_unit"):
        db.get(
            TenantRolePermission, (ids["buyer_role"], f"procurement.requests.{target}")
        ).active = False
    elif target == "scope":
        db.scalar(
            select(MembershipUnitScope).where(
                MembershipUnitScope.membership_id == ids["buyer_member"]
            )
        ).active = False
    elif target == "node":
        db.get(OrganizationNode, ids["node"]).active = False
    elif target == "module":
        db.scalar(
            select(ContractModule).where(
                ContractModule.contract_id == ids["contract_a"],
                ContractModule.code == "PROCUREMENT",
            )
        ).active = False
    db.flush()
    if target == "valid":
        assert (
            policy()
            .require_buyer_candidate(db, actor, scope, ids["node"], candidate_id)
            .id
            == ids["buyer_member"]
        )
    else:
        denied(
            lambda: policy().require_buyer_candidate(
                db, actor, scope, ids["node"], candidate_id
            )
        )
    assert (
        list(
            db.scalars(
                select(MembershipUnitScope.node_id).where(
                    MembershipUnitScope.membership_id == ids["buyer_member"]
                )
            )
        )
        == before
    )


def test_read_foreign_request_is_uniform_not_found(db, request_policy_case):
    ids, actor, scope, _, _ = request_policy_case
    row = PurchaseRequest(
        tenant_id=ids["tenant_b"],
        contract_id=ids["contract_b"],
        requester_user_id=actor.user_id,
        requester_membership_id=ids["member_a"],
        requesting_node_id=ids["foreign_node"],
        title="Invisible",
    )
    denied(lambda: policy().authorize_request_read(db, actor, scope, row), 404)


@pytest.mark.parametrize("kind", ["support", "grant"])
def test_derived_context_denied_after_operator_role_removed(
    db, request_policy_case, kind
):
    from dataclasses import replace
    from uuid import uuid4

    from app.grants.models import TemporaryPrivilegedGrant
    from app.support.models import SupportSession
    from tests.fixtures.purchase_request_policy import request_identity

    ids, _, _, _, _ = request_policy_case
    # This operator has a real tenant membership as well as a platform role.
    operator, parent_scope = request_identity(db, ids, ids["support_user"])
    parent = db.get(AccessContext, parent_scope.id)
    derived = AccessContext(
        id=uuid4(),
        session_id=operator.session_id,
        actor_id=operator.user_id,
        tenant_id=ids["tenant_a"],
        contract_id=ids["contract_a"],
        created_at=parent.created_at,
        expires_at=parent.expires_at,
    )
    db.add(derived)
    db.flush()
    common = {
        "operator_id": operator.user_id,
        "operator_session_id": operator.session_id,
        "tenant_id": ids["tenant_a"],
        "contract_id": ids["contract_a"],
        "parent_context_id": parent.id,
        "context_id": derived.id,
        "reason": "Recorded operational support purpose",
        "started_at": parent.created_at,
        "expires_at": parent.expires_at,
    }
    if kind == "support":
        db.add(
            SupportSession(
                operator_role="PLATFORM_SUPPORT",
                viewed_membership_id=ids["member_a"],
                viewed_user_id=ids["user"],
                **common,
            )
        )
    else:
        db.get(PlatformRoleAssignment, operator.user_id).role = "PLATFORM_ADMIN"
        db.add(
            TemporaryPrivilegedGrant(
                operator_role="PLATFORM_ADMIN", grant_type="FINANCIAL_FISCAL", **common
            )
        )
    db.flush()
    # Losing INTERNAL status never converts an old derived context to tenant access.
    db.get(PlatformRoleAssignment, operator.user_id).active = False
    db.flush()
    derived_scope = replace(parent_scope, id=derived.id)
    with pytest.raises(ApiError) as failure:
        policy().require_request_actor(db, operator, derived_scope, "create")
    assert failure.value.status == 403
    assert failure.value.code == "CAPABILITY_DENIED"
