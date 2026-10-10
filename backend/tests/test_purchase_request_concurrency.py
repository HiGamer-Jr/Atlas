"""Real PostgreSQL lock waits use events and bounded futures, never sleep ordering."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.models import User
from app.organization.models import (
    ContractModule,
    MembershipUnitScope,
    OrganizationNode,
)
from app.procurement.requests import command_schemas as schemas
from app.procurement.requests import commands
from app.procurement.requests.models import PurchaseRequest, PurchaseRequestEvent
from app.tenancy.models import (
    AccessContext,
    Contract,
    Membership,
    TenantRole,
    TenantRolePermission,
)
from tests.helpers import select_context
from tests.test_purchase_request_commands import (
    act,
    create,
    request,
    triage,
)
from tests.test_purchase_request_commands import (
    command_case as _command_case,  # noqa: F401 -- fixture registration
)


@pytest.mark.parametrize(
    "revocation",
    [
        "grant",
        "capability",
        "node",
        "role",
        "module",
        "contract",
        "membership",
        "context",
    ],
)
def test_revocation_wait_revalidates_each_authority(
    db, db_runtime, command_case, revocation
):
    ids, actor, scope, *_ = command_case
    row = create(db, command_case)
    db.commit()
    attempting_identity = Event()

    def observe(conn, cursor, statement, params, context, executemany):
        if (
            conn.info.get("command_wait")
            and "users" in statement
            and "FOR UPDATE" in statement
        ):
            attempting_identity.set()

    event.listen(db_runtime, "before_cursor_execute", observe)

    def submit():
        with Session(db_runtime) as worker:
            worker.connection().info["command_wait"] = True
            worker.execute(text("SET LOCAL lock_timeout='8s'"))
            try:
                result = commands.transition_request(
                    worker,
                    request(),
                    actor,
                    scope,
                    row.id,
                    "submit",
                    schemas.VersionCommand(expected_version=row.version),
                    uuid4(),
                )
                worker.commit()
                return result.status
            except ApiError as error:
                worker.rollback()
                return error.code
            finally:
                worker.connection().info.pop("command_wait", None)

    try:
        with Session(db_runtime) as revoker, ThreadPoolExecutor(max_workers=1) as pool:
            # A persisted identity lock forces a real wait before fresh command authorization.
            revoker.scalar(
                select(User).where(User.id == actor.user_id).with_for_update()
            )
            if revocation == "grant":
                target = revoker.scalar(
                    select(MembershipUnitScope).where(
                        MembershipUnitScope.membership_id == ids["member_a"],
                        MembershipUnitScope.node_id == ids["node"],
                    )
                )
            elif revocation == "capability":
                target = revoker.scalar(
                    select(TenantRolePermission).where(
                        TenantRolePermission.role_id == ids["role_basic"],
                        TenantRolePermission.capability
                        == "procurement.requests.create",
                    )
                )
            else:
                model, key = {
                    "node": (OrganizationNode, ids["node"]),
                    "role": (TenantRole, ids["role_basic"]),
                    "module": (ContractModule, None),
                    "contract": (Contract, ids["contract_a"]),
                    "membership": (Membership, ids["member_a"]),
                    "context": (AccessContext, scope.id),
                }[revocation]
                target = (
                    revoker.get(model, key)
                    if key
                    else revoker.scalar(
                        select(model).where(
                            model.contract_id == scope.contract_id,
                            model.code == "PROCUREMENT",
                        )
                    )
                )
            if revocation == "context":
                from app.tenancy.contexts import now

                target.revoked_at = now(revoker)
            else:
                target.active = False
            revoker.flush()
            future = pool.submit(submit)
            assert attempting_identity.wait(5), (
                "Command never attempted its identity lock"
            )
            revoker.commit()
            result = future.result(timeout=10)
            assert result in {
                "UNIT_SCOPE_DENIED",
                "CAPABILITY_DENIED",
                "MODULE_UNAVAILABLE",
                "CONTEXT_INVALID",
            }, result
        with Session(db_runtime) as verify:
            stored = verify.get(PurchaseRequest, row.id)
            assert stored.status == "DRAFT" and stored.version == 1
            assert (
                len(
                    list(
                        verify.scalars(
                            select(PurchaseRequestEvent).where(
                                PurchaseRequestEvent.request_id == row.id
                            )
                        )
                    )
                )
                == 1
            )
    finally:
        event.remove(db_runtime, "before_cursor_execute", observe)


def test_policy_change_and_concurrent_decision(
    admin, member, db, command_case, app, monkeypatch
):
    from app.procurement.requests import routes

    ids, *_ = command_case
    row = triage(db, command_case)
    db.commit()
    admin_headers = select_context(admin, ids["contract_a"])
    actor_headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    admin_locked, release_admin, decision_wait = Event(), Event(), Event()
    original = routes.patch_approval_policy

    def held_patch(*args, **kwargs):
        # The real Context dependency has already acquired lifecycle/user/contract locks.
        admin_locked.set()
        assert release_admin.wait(8)
        return original(*args, **kwargs)

    monkeypatch.setattr(routes, "patch_approval_policy", held_patch)

    def observe(conn, cursor, statement, params, context, executemany):
        if (
            admin_locked.is_set()
            and not release_admin.is_set()
            and "pg_advisory_xact_lock" in statement
        ):
            decision_wait.set()

    event.listen(app.state.database_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            patch = pool.submit(
                admin.patch,
                "/api/contract/purchase-request-policy",
                headers=admin_headers,
                json={
                    "approval_mode": "NOT_REQUIRED",
                    "expected_version": 0,
                    "reason": "Authorized prospective waiver",
                },
            )
            assert admin_locked.wait(5)
            decision = pool.submit(
                member.post,
                f"/api/procurement/requests/{row.id}/request-approval",
                headers=actor_headers,
                json={"expected_version": row.version},
            )
            assert decision_wait.wait(5)
            release_admin.set()
            assert patch.result(timeout=10).status_code == 200
            response = decision.result(timeout=10)
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "APPROVED"
            assert response.json()["approval_policy_version"] == 1
            assert response.json()["approval_decision_kind"] == "POLICY_WAIVER"
    finally:
        release_admin.set()
        event.remove(app.state.database_engine, "before_cursor_execute", observe)


def test_revocation_wait_and_admin_lock_order(
    admin, member, db, command_case, app, monkeypatch
):
    from app.tenancy import member_commands

    ids, *_ = command_case
    row = act(db, command_case, triage(db, command_case), "request-approval")
    row = act(db, command_case, row, "approve", who="buyer")
    db.commit()
    admin_headers = select_context(admin, ids["contract_a"])
    actor_headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    admin_locked, release_admin, assignment_wait = Event(), Event(), Event()
    original = member_commands.target_member

    def held_member(*args, **kwargs):
        result = original(*args, **kwargs)
        admin_locked.set()
        assert release_admin.wait(8)
        return result

    monkeypatch.setattr(member_commands, "target_member", held_member)

    def observe(conn, cursor, statement, params, context, executemany):
        if (
            admin_locked.is_set()
            and not release_admin.is_set()
            and "pg_advisory_xact_lock" in statement
        ):
            assignment_wait.set()

    event.listen(app.state.database_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            revoke = pool.submit(
                admin.patch,
                f"/api/memberships/{ids['buyer_member']}/status",
                headers=admin_headers,
                json={"active": False, "blocked": False, "expected_version": 1},
            )
            assert admin_locked.wait(5), "Admin did not acquire target locks"
            assign = pool.submit(
                member.post,
                f"/api/procurement/requests/{row.id}/assign",
                headers=actor_headers,
                json={
                    "expected_version": row.version,
                    "buyer_membership_id": str(ids["buyer_member"]),
                },
            )
            assert assignment_wait.wait(5)
            release_admin.set()
            response = revoke.result(timeout=10)
            assert response.status_code == 200, response.text
            response = assign.result(timeout=10)
            assert response.status_code == 403, response.text
    finally:
        release_admin.set()
        event.remove(app.state.database_engine, "before_cursor_execute", observe)


def test_crossed_candidate_assignments_finish_without_deadlock(
    db, db_runtime, command_case
):
    from tests.fixtures.purchase_request_policy import request_permissions

    ids, actor, scope, buyer, buyer_scope = command_case
    request_permissions(db, ids, ids["role_basic"], ["fulfill"])
    rows = []
    for _ in range(2):
        row = act(db, command_case, triage(db, command_case), "request-approval")
        rows.append(act(db, command_case, row, "approve", who="buyer"))
    db.commit()
    start = Barrier(2)

    def assign(principal, access, row, candidate):
        with Session(db_runtime) as worker:
            worker.execute(text("SET LOCAL lock_timeout='8s'"))
            start.wait(timeout=5)
            result = commands.assign_buyer(
                worker,
                request(),
                principal,
                access,
                row.id,
                schemas.AssignmentCommand(
                    expected_version=row.version, buyer_membership_id=candidate
                ),
                uuid4(),
            )
            worker.commit()
            return result.buyer.membership_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(assign, actor, scope, rows[0], ids["buyer_member"])
        second = pool.submit(assign, buyer, buyer_scope, rows[1], ids["member_a"])
        assert first.result(timeout=10) == ids["buyer_member"]
        assert second.result(timeout=10) == ids["member_a"]


@pytest.mark.parametrize(
    "revocation", ["user", "membership", "role", "capability", "grant"]
)
def test_candidate_revocation_during_identity_wait(
    db, db_runtime, command_case, revocation
):
    ids, actor, scope, *_ = command_case
    row = act(db, command_case, triage(db, command_case), "request-approval")
    row = act(db, command_case, row, "approve", who="buyer")
    db.commit()
    waiting = Event()

    def observe(conn, cursor, statement, params, context, executemany):
        if (
            conn.info.get("candidate_wait")
            and "users" in statement
            and "FOR UPDATE" in statement
        ):
            waiting.set()

    event.listen(db_runtime, "before_cursor_execute", observe)

    def assign():
        with Session(db_runtime) as worker:
            worker.connection().info["candidate_wait"] = True
            worker.execute(text("SET LOCAL lock_timeout='8s'"))
            try:
                commands.assign_buyer(
                    worker,
                    request(),
                    actor,
                    scope,
                    row.id,
                    schemas.AssignmentCommand(
                        expected_version=row.version,
                        buyer_membership_id=ids["buyer_member"],
                    ),
                    uuid4(),
                )
                worker.commit()
                return "UNEXPECTED_SUCCESS"
            except ApiError as error:
                worker.rollback()
                return error.code
            finally:
                worker.connection().info.pop("candidate_wait", None)

    try:
        with Session(db_runtime) as revoker, ThreadPoolExecutor(max_workers=1) as pool:
            user = revoker.scalar(
                select(User).where(User.id == ids["buyer"]).with_for_update()
            )
            if revocation == "user":
                target = user
            elif revocation == "membership":
                target = revoker.get(Membership, ids["buyer_member"])
            elif revocation == "role":
                target = revoker.get(TenantRole, ids["buyer_role"])
            elif revocation == "capability":
                target = revoker.scalar(
                    select(TenantRolePermission).where(
                        TenantRolePermission.role_id == ids["buyer_role"],
                        TenantRolePermission.capability
                        == "procurement.requests.fulfill",
                    )
                )
            else:
                target = revoker.scalar(
                    select(MembershipUnitScope).where(
                        MembershipUnitScope.membership_id == ids["buyer_member"],
                        MembershipUnitScope.node_id == ids["node"],
                    )
                )
            target.active = False
            revoker.flush()
            future = pool.submit(assign)
            assert waiting.wait(5)
            revoker.commit()
            assert future.result(timeout=10) in {
                "CAPABILITY_DENIED",
                "UNIT_SCOPE_DENIED",
            }
        with Session(db_runtime) as verify:
            stored = verify.get(PurchaseRequest, row.id)
            assert stored.buyer_membership_id is None and stored.version == row.version
    finally:
        event.remove(db_runtime, "before_cursor_execute", observe)
