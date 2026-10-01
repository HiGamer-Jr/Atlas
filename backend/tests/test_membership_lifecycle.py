import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import EmailOutbox, SecurityToken, User
from app.tenancy.models import Membership
from tests.helpers import select_context
from tests.identity_helpers import csrf, login
from tests.test_access_tokens import NEW_PASSWORD, issue


@pytest.mark.parametrize(
    "active,blocked,command,value,expected",
    [
        (False, True, "active", True, (True, True)),
        (False, True, "blocked", False, (False, False)),
        (True, False, "active", False, (False, False)),
        (True, False, "blocked", True, (True, True)),
    ],
)
def test_status_flags_independent(
    support, scope_ids, db_runtime, active, blocked, command, value, expected
):
    with Session(db_runtime) as db, db.begin():
        member = db.get(Membership, scope_ids["member_a"])
        member.active, member.blocked = active, blocked
    scope = select_context(support, scope_ids["contract_a"])
    response = support.patch(
        f"/api/memberships/{scope_ids['member_a']}/status",
        headers=scope,
        json={command: value, "expected_version": 1},
    )
    assert response.status_code == 200
    assert (response.json()["active"], response.json()["blocked"]) == expected


@pytest.mark.parametrize("command,value", [("active", False), ("blocked", True)])
def test_membership_change_immediately_revokes_only_its_context(
    support, member, scope_ids, db_runtime, command, value
):
    context_a = select_context(member, scope_ids["contract_a"])
    context_b = select_context(member, scope_ids["contract_a2"])
    scope = select_context(support, scope_ids["contract_a"])
    assert (
        support.patch(
            f"/api/memberships/{scope_ids['member_a']}/status",
            headers=scope,
            json={command: value, "expected_version": 1},
        ).status_code
        == 200
    )
    assert member.get("/api/context", headers=context_a).status_code == 403
    assert member.get("/api/context", headers=context_b).status_code == 200
    assert member.get("/api/auth/me").status_code == 200
    with Session(db_runtime) as db:
        assert db.get(User, scope_ids["member_user"]).active
        assert db.get(Membership, scope_ids["member_a2"]).active


def test_audit_failure_rolls_back_reset(
    client, mail, auth_users, monkeypatch, db_runtime
):
    raw = issue(client, mail)

    def fail(*args, **kwargs):
        raise RuntimeError("controlled audit failure")

    monkeypatch.setattr("app.identity.tokens.append_event", fail)
    with pytest.raises(RuntimeError, match="controlled"):
        client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": NEW_PASSWORD},
        )
    with Session(db_runtime) as db:
        assert db.scalar(select(SecurityToken)).consumed_at is None
    login(client, "member@example.test")


def test_rate_limit_persists_across_app_restart(
    client, mail, auth_users, app, settings, db_runtime, clock
):
    from fastapi.testclient import TestClient

    from app.main import create_app

    settings.access_request_limit = 1
    csrf(client)
    client.post("/api/auth/recovery", json={"email": "member@example.test"})
    restarted = create_app(settings)
    restarted.state.clock = clock
    restarted.state.email_transport = app.state.email_transport
    with TestClient(restarted, base_url="https://testserver") as browser:
        csrf(browser)
        assert (
            browser.post(
                "/api/auth/recovery", json={"email": "member@example.test"}
            ).status_code
            == 202
        )
    with Session(db_runtime) as db:
        assert len(list(db.scalars(select(SecurityToken)))) == 1
    clock.advance(seconds=settings.access_window_seconds)
    csrf(client)
    assert (
        client.post(
            "/api/auth/recovery", json={"email": "member@example.test"}
        ).status_code
        == 202
    )
    with Session(db_runtime) as db:
        assert len(list(db.scalars(select(SecurityToken)))) == 2


def test_pending_existing_identity_cannot_discover_new_contract(
    support, scope_ids, mail, client
):
    from tests.test_membership_invitations import invite

    invite(support, scope_ids, "other@example.test")
    login(client, "other@example.test")
    contracts = client.get("/api/contracts").json()
    assert str(scope_ids["contract_a"]) not in str(contracts)
    assert (
        client.post(
            "/api/contexts", json={"contract_id": str(scope_ids["contract_a"])}
        ).status_code
        == 404
    )


def test_internal_operator_invite_route_exists():
    from app.main import app

    assert "/api/platform/operators/invite" in app.openapi()["paths"]


def test_operator_invite_requires_admin_confirmation_and_own_password(
    admin, support, mail, client
):
    from tests.identity_helpers import PASSWORD

    payload = {
        "email": "operator-new@example.test",
        "display_name": "New operator",
        "role": "PLATFORM_SUPPORT",
        "password": PASSWORD,
        "confirmation": {
            "email": "operator-new@example.test",
            "role": "PLATFORM_SUPPORT",
        },
    }
    assert (
        support.post("/api/platform/operators/invite", json=payload).status_code == 403
    )
    assert (
        admin.post(
            "/api/platform/operators/invite", json={**payload, "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        admin.post(
            "/api/platform/operators/invite",
            json={
                **payload,
                "confirmation": {
                    "email": "wrong@example.test",
                    "role": "PLATFORM_SUPPORT",
                },
            },
        ).status_code
        == 422
    )
    assert admin.post("/api/platform/operators/invite", json=payload).status_code == 202
    assert mail[1].deliver_batch(10).sent == 1
    from tests.test_access_tokens import token_from

    raw = token_from(mail[0])
    csrf(client)
    assert (
        client.post(
            "/api/auth/accept-invite", json={"token": raw, "new_password": NEW_PASSWORD}
        ).status_code
        == 204
    )
    assert (
        login(client, "operator-new@example.test", NEW_PASSWORD).json()["platform_role"]
        == "PLATFORM_SUPPORT"
    )


def test_scoped_membership_list_finds_pending_without_other_memberships(
    support, scope_ids, mail
):
    from tests.test_membership_invitations import invite

    scope = invite(support, scope_ids, "other@example.test")
    response = support.get(
        "/api/memberships", headers=scope, params={"search": "other@example.test"}
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    row = response.json()["items"][0]
    assert row["invitation_pending"] is True
    assert str(scope_ids["member_b"]) not in response.text
    assert set(row) == {
        "id",
        "user_id",
        "role_id",
        "active",
        "blocked",
        "version",
        "invitation_pending",
        "email",
        "display_name",
        "role_name",
        "allowed_actions",
        "last_access_at",
        "invitation_status",
    }


def test_ineligible_invite_cancellation_is_irreversible(
    support, scope_ids, mail, client, db_runtime
):
    from app.tenancy.models import TenantRole
    from tests.test_access_tokens import token_from
    from tests.test_membership_invitations import invite

    invite(support, scope_ids)
    mail[1].deliver_batch(10)
    raw = token_from(mail[0])
    with Session(db_runtime) as db, db.begin():
        db.get(TenantRole, scope_ids["role_basic"]).support_assignable = False
    csrf(client)
    assert (
        client.post(
            "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
        ).status_code
        == 400
    )
    with Session(db_runtime) as db, db.begin():
        db.get(TenantRole, scope_ids["role_basic"]).support_assignable = True
    assert (
        client.post(
            "/api/auth/accept-invite", json={"token": raw, "new_password": NEW_PASSWORD}
        ).status_code
        == 400
    )


def test_pending_admin_invite_cannot_replace_last_usable_admin(admin, auth_users, mail):
    from tests.identity_helpers import PASSWORD

    payload = {
        "email": "pending-admin@example.test",
        "display_name": "Pending",
        "role": "PLATFORM_ADMIN",
        "password": PASSWORD,
        "confirmation": {
            "email": "pending-admin@example.test",
            "role": "PLATFORM_ADMIN",
        },
    }
    assert admin.post("/api/platform/operators/invite", json=payload).status_code == 202
    assert (
        admin.post(
            f"/api/platform/operators/{auth_users['admin_user']}/status",
            json={"active": False},
        ).status_code
        == 409
    )


def test_pending_internal_invite_can_be_resent(admin, mail, db_runtime):
    from tests.identity_helpers import PASSWORD

    payload = {
        "email": "pending-internal@example.test",
        "display_name": "Pending",
        "role": "PLATFORM_SUPPORT",
        "password": PASSWORD,
        "confirmation": {
            "email": "pending-internal@example.test",
            "role": "PLATFORM_SUPPORT",
        },
    }
    assert admin.post("/api/platform/operators/invite", json=payload).status_code == 202
    assert admin.post("/api/platform/operators/invite", json=payload).status_code == 202
    with Session(db_runtime) as db:
        rows = list(db.scalars(select(SecurityToken)))
        assert len(rows) == 2
        assert sum(row.invalidated_at is None for row in rows) == 1


@pytest.mark.parametrize("bad_role", ["owner", "superuser"])
def test_access_migration_incremental_rejects_unsafe_roles(
    db_owner, db_runtime, migration_config, bad_role
):
    from sqlalchemy import text

    from alembic import command

    safe_role = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0003")
            migration_config.attributes["runtime_role"] = (
                db_owner.url.username
                if bad_role == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
            )
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "0004")
            migration_config.attributes["runtime_role"] = safe_role
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes["runtime_role"] = safe_role
        migration_config.attributes.pop("connection", None)


def test_stale_reauth_rejects_existing_invitation(
    support, scope_ids, mail, client, clock
):
    from tests.test_access_tokens import token_from
    from tests.test_membership_invitations import invite

    invite(support, scope_ids, "other@example.test")
    mail[1].deliver_batch(10)
    raw = token_from(mail[0])
    login(client, "other@example.test")
    clock.advance(minutes=6)
    response = client.post("/api/auth/accept-invite", json={"token": raw})
    assert response.status_code == 401
    assert response.json()["code"] == "INVITE_AUTH_REQUIRED"


@pytest.mark.parametrize("operation", ["status", "accept", "outbox"])
def test_business_failure_rolls_back_all_lifecycle_mutations(
    support, scope_ids, mail, client, db_runtime, monkeypatch, operation
):
    from sqlalchemy import event as sa_event

    from app.audit.models import AuditEvent
    from tests.test_access_tokens import token_from
    from tests.test_membership_invitations import invite

    def fail(*args, **kwargs):
        raise RuntimeError("controlled failure")

    if operation == "outbox":
        sa_event.listen(EmailOutbox, "before_insert", fail)
        try:
            with pytest.raises(RuntimeError, match="controlled"):
                invite(support, scope_ids)
        finally:
            sa_event.remove(EmailOutbox, "before_insert", fail)
        with Session(db_runtime) as db:
            assert (
                db.scalar(
                    select(User).where(User.email_normalized == "new@example.test")
                )
                is None
            )
            assert db.scalar(select(SecurityToken)) is None
            assert db.scalar(select(EmailOutbox)) is None
            assert (
                db.scalar(
                    select(AuditEvent).where(AuditEvent.action == "membership.invited")
                )
                is None
            )
    elif operation == "accept":
        invite(support, scope_ids)
        mail[1].deliver_batch(10)
        raw = token_from(mail[0])
        csrf(client)
        monkeypatch.setattr("app.identity.tokens.append_event", fail)
        with pytest.raises(RuntimeError, match="controlled"):
            client.post(
                "/api/auth/accept-invite",
                json={"token": raw, "new_password": NEW_PASSWORD},
            )
        with Session(db_runtime) as db:
            token = db.scalar(select(SecurityToken))
            assert token.consumed_at is None
            assert db.get(Membership, token.membership_id).invitation_pending
            assert db.get(User, token.recipient_user_id).password_hash is None
    else:
        scope = select_context(support, scope_ids["contract_a"])
        monkeypatch.setattr("app.identity.tokens.append_event", fail)
        with pytest.raises(RuntimeError, match="controlled"):
            support.patch(
                f"/api/memberships/{scope_ids['member_a']}/status",
                headers=scope,
                json={"blocked": True, "expected_version": 1},
            )
        with Session(db_runtime) as db:
            row = db.get(Membership, scope_ids["member_a"])
            assert not row.blocked and row.version == 1


def test_scoped_list_pagination_and_status(support, scope_ids, mail):
    from tests.test_membership_invitations import invite

    scope = invite(support, scope_ids)
    first = support.get("/api/memberships", headers=scope, params={"limit": 1}).json()[
        "items"
    ]
    second = support.get(
        "/api/memberships", headers=scope, params={"limit": 1, "offset": 1}
    ).json()["items"]
    assert first[0]["id"] != second[0]["id"]
    pending = support.get(
        "/api/memberships", headers=scope, params={"status": "PENDING"}
    ).json()["items"]
    assert len(pending) == 1 and pending[0]["invitation_pending"]
    assert (
        support.get(
            "/api/memberships", headers=scope, params={"limit": 101}
        ).status_code
        == 422
    )
    assert support.get("/api/memberships").status_code == 403


def test_membership_list_get_does_not_require_origin_or_csrf(support, scope_ids):
    scope = select_context(support, scope_ids["contract_a"])
    support.headers.pop("Origin", None)
    support.headers.pop("X-CSRF-Token", None)
    response = support.get("/api/memberships", headers=scope)
    assert response.status_code == 200
    response = support.patch(
        f"/api/memberships/{scope_ids['member_a']}/status",
        headers=scope,
        json={"blocked": True, "expected_version": 1},
    )
    assert response.status_code == 403


def test_passwordless_activated_role_still_cannot_replace_last_admin(
    admin, auth_users, mail, db_runtime
):
    from tests.identity_helpers import PASSWORD

    payload = {
        "email": "pending-admin@example.test",
        "display_name": "Pending",
        "role": "PLATFORM_ADMIN",
        "password": PASSWORD,
        "confirmation": {
            "email": "pending-admin@example.test",
            "role": "PLATFORM_ADMIN",
        },
    }
    assert admin.post("/api/platform/operators/invite", json=payload).status_code == 202
    with Session(db_runtime) as db:
        user_id = db.scalar(
            select(User.id).where(User.email_normalized == payload["email"])
        )
    response = admin.post(
        f"/api/platform/operators/{user_id}/role",
        json={
            "role": "PLATFORM_ADMIN",
            "password": PASSWORD,
            "confirmation": {
                "target_user_id": str(user_id),
                "target_role": "PLATFORM_ADMIN",
            },
        },
    )
    assert response.status_code == 200
    response = admin.post(
        f"/api/platform/operators/{auth_users['admin_user']}/status",
        json={"active": False},
    )
    assert response.status_code == 409


def test_cancelled_support_invitation_requires_admin_reissue(
    admin, support, scope_ids, mail, client, db_runtime
):
    from app.tenancy.models import TenantRole
    from tests.test_access_tokens import token_from
    from tests.test_membership_invitations import invite

    scope = invite(support, scope_ids)
    mail[1].deliver_batch(10)
    raw = token_from(mail[0])
    with Session(db_runtime) as db, db.begin():
        db.get(TenantRole, scope_ids["role_basic"]).support_assignable = False
        member_id = db.scalar(select(SecurityToken.membership_id))
    csrf(client)
    response = client.post(
        "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
    )
    assert response.status_code == 400
    with Session(db_runtime) as db, db.begin():
        db.get(TenantRole, scope_ids["role_basic"]).support_assignable = True
    response = support.post(f"/api/memberships/{member_id}/invite", headers=scope)
    assert response.status_code == 403
    admin_scope = select_context(admin, scope_ids["contract_a"])
    response = admin.post(f"/api/memberships/{member_id}/invite", headers=admin_scope)
    assert response.status_code == 202
    assert mail[1].deliver_batch(10).sent == 1
    new_raw = token_from(mail[0])
    response = client.post(
        "/api/auth/accept-invite", json={"token": new_raw, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 204


def test_worker_policy_cancellation_is_audited(support, scope_ids, mail, db_runtime):
    from app.audit.models import AuditEvent
    from app.tenancy.models import TenantRole
    from tests.test_membership_invitations import invite

    invite(support, scope_ids)
    with Session(db_runtime) as db, db.begin():
        db.get(TenantRole, scope_ids["role_basic"]).support_assignable = False
    assert mail[1].deliver_batch(10).cancelled == 1
    with Session(db_runtime) as db:
        row = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "access.invite.invalidated")
        )
        assert row is not None
        assert row.actor_id is None and row.reason == "POLICY_REVALIDATION"
        assert row.contract_id == scope_ids["contract_a"]


@pytest.mark.parametrize("failure_type", [RuntimeError, ValueError])
@pytest.mark.parametrize("path", ["worker", "public"])
def test_cancellation_audit_failure_rolls_back(
    support, scope_ids, mail, client, db_runtime, monkeypatch, path, failure_type
):
    from app.tenancy.models import TenantRole
    from tests.test_access_tokens import token_from
    from tests.test_membership_invitations import invite

    invite(support, scope_ids)
    if path == "public":
        mail[1].deliver_batch(10)
        raw = token_from(mail[0])
        csrf(client)
    with Session(db_runtime) as db, db.begin():
        db.get(TenantRole, scope_ids["role_basic"]).support_assignable = False

    def fail(*args, **kwargs):
        raise failure_type("controlled cancellation audit failure")

    monkeypatch.setattr("app.identity.tokens.append_event", fail)
    with pytest.raises(failure_type, match="controlled"):
        if path == "worker":
            mail[1].deliver_batch(10)
        else:
            client.post(
                "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
            )
    with Session(db_runtime) as db:
        token = db.scalar(select(SecurityToken))
        assert token.invalidated_at is None
        assert not db.get(Membership, token.membership_id).invite_requires_admin
