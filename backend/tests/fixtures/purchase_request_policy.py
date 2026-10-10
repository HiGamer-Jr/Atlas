from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.identity.models import AuthSession, User
from app.identity.schemas import Principal
from app.organization.models import (
    ContractModule,
    MembershipUnitScope,
    OrganizationNode,
)
from app.tenancy.models import (
    AccessContext,
    Membership,
    TenantRole,
    TenantRolePermission,
)
from app.tenancy.schemas import AccessScope


def request_identity(db, ids, user_id):
    now = datetime.now(UTC)
    session = AuthSession(
        id=uuid4(),
        user_id=user_id,
        token_hash=uuid4().hex * 2,
        csrf_hash=uuid4().hex * 2,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db.add(session)
    db.flush()
    context = AccessContext(
        id=uuid4(),
        session_id=session.id,
        actor_id=user_id,
        tenant_id=ids["tenant_a"],
        contract_id=ids["contract_a"],
        created_at=now,
        expires_at=now + timedelta(hours=1),
    )
    db.add(context)
    db.flush()
    return Principal(user_id, session.id, None), AccessScope(
        context.id, context.tenant_id, context.contract_id, session.id, user_id
    )


def request_permissions(db, ids, role_id, actions):
    for action in actions:
        db.add(
            TenantRolePermission(
                tenant_id=ids["tenant_a"],
                contract_id=ids["contract_a"],
                role_id=role_id,
                capability=f"procurement.requests.{action}",
            )
        )
    db.flush()


def request_grants(db, ids, member_id, node_ids):
    for node_id in node_ids:
        db.add(
            MembershipUnitScope(
                tenant_id=ids["tenant_a"],
                contract_id=ids["contract_a"],
                membership_id=member_id,
                node_id=node_id,
            )
        )
    db.flush()


@pytest.fixture
def request_policy_case(db, purchase_case):
    # Task4 exposes the actual operational domain; no availability monkeypatch.
    ids = dict(purchase_case)
    ids.update(
        company=uuid4(),
        second_node=uuid4(),
        buyer=uuid4(),
        buyer_member=uuid4(),
        buyer_role=uuid4(),
    )
    db.add_all(
        [
            OrganizationNode(
                id=ids["company"],
                tenant_id=ids["tenant_a"],
                contract_id=ids["contract_a"],
                kind="COMPANY",
                code="COMPANY",
                name="Company grouping",
            ),
            OrganizationNode(
                id=ids["second_node"],
                tenant_id=ids["tenant_a"],
                contract_id=ids["contract_a"],
                kind="WORKSITE",
                code="WORKSITE",
                name="Real worksite",
            ),
            User(
                id=ids["buyer"],
                email_normalized="buyer@example.test",
                display_name="Actual buyer",
            ),
            TenantRole(
                id=ids["buyer_role"],
                tenant_id=ids["tenant_a"],
                contract_id=ids["contract_a"],
                code="CUSTOM_BUYER",
                name="Custom procurement operator",
            ),
            ContractModule(
                tenant_id=ids["tenant_a"],
                contract_id=ids["contract_a"],
                code="PROCUREMENT",
                contracted=True,
                active=True,
            ),
        ]
    )
    db.flush()
    db.add(
        Membership(
            id=ids["buyer_member"],
            user_id=ids["buyer"],
            tenant_id=ids["tenant_a"],
            contract_id=ids["contract_a"],
            role_id=ids["buyer_role"],
        )
    )
    db.flush()
    # No administrative capabilities: custom persisted role controls the actor.
    for permission in db.scalars(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["role_basic"]
        )
    ):
        permission.active = False
    request_permissions(db, ids, ids["role_basic"], ["create", "read_own", "assign"])
    request_permissions(db, ids, ids["buyer_role"], ["fulfill", "read_unit"])
    request_grants(db, ids, ids["member_a"], [ids["node"]])
    request_grants(db, ids, ids["buyer_member"], [ids["node"]])
    principal, scope = request_identity(db, ids, ids["user"])
    buyer_principal, buyer_scope = request_identity(db, ids, ids["buyer"])
    db.flush()
    return ids, principal, scope, buyer_principal, buyer_scope
