from importlib import import_module, util

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.identity.models import (
    AuthSession,
    EmailOutbox,
    PlatformRoleAssignment,
    SecurityToken,
    User,
)
from app.partners.models import PartnerMembership
from app.tenancy.models import Membership
from tests.identity_helpers import csrf, login
from tests.test_access_tokens import NEW_PASSWORD, issue, token_from
from tests.test_partner_lifecycle import principal


def invitations():
    assert util.find_spec("app.partners.invitations") is not None, (
        "Typed partner invitations are missing"
    )
    return import_module("app.partners.invitations")


def issue_partner(db_runtime, auth_users, partner_case, app):
    api = invitations()
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    with Session(db_runtime) as db:
        db.info.update(
            settings=app.state.settings,
            email_transport=app.state.email_transport,
            clock=app.state.clock,
        )
        api.issue_partner_invitation(db, actor, partner_case["membership"])
        db.commit()


def identity_snapshot(db, user_id):
    user = db.get(User, user_id)
    return (
        user.password_hash,
        user.active,
        user.blocked,
        [
            (row.user_id, row.role, row.active)
            for row in db.scalars(
                select(PlatformRoleAssignment).where(
                    PlatformRoleAssignment.user_id == user_id
                )
            )
        ],
        [
            (
                row.id,
                row.role_id,
                row.active,
                row.blocked,
                row.invitation_pending,
                row.version,
            )
            for row in db.scalars(
                select(Membership).where(Membership.user_id == user_id)
            )
        ],
    )


def test_partner_invite_existing_user_preserves_identity(
    db_runtime,
    auth_users,
    partner_case,
    app,
    mail,
    client,
    new_client,
    scope_ids,
    clock,
):
    # Attach invitation to existing TENANT identity to prove its memberships survive.
    with Session(db_runtime) as db, db.begin():
        db.get(PartnerMembership, partner_case["membership"]).user_id = auth_users[
            "member_user"
        ]
        before = identity_snapshot(db, auth_users["member_user"])
    issue_partner(db_runtime, auth_users, partner_case, app)
    transport, worker = mail
    assert worker.deliver_batch(20).sent == 1
    raw = token_from(transport)
    csrf(client)
    inspected = client.post(
        "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
    )
    assert inspected.status_code == 200
    assert inspected.json() == {
        "target_kind": "PARTNER",
        "requires_authentication": True,
    }
    assert (
        client.post(
            "/api/auth/invite/accept", json={"token": raw, "target_kind": "PARTNER"}
        ).status_code
        == 401
    )
    login(client, "support@example.test")
    assert (
        client.post(
            "/api/auth/invite/accept", json={"token": raw, "target_kind": "PARTNER"}
        ).status_code
        == 401
    )
    recipient = new_client()
    login(recipient, "member@example.test")
    assert (
        recipient.post(
            "/api/auth/invite/accept", json={"token": raw, "target_kind": "TENANT"}
        ).status_code
        == 400
    )
    assert (
        recipient.post(
            "/api/auth/invite/accept",
            json={"token": raw, "target_kind": "PARTNER", "new_password": NEW_PASSWORD},
        ).status_code
        == 422
    )
    assert (
        recipient.post(
            "/api/auth/invite/accept",
            json={
                "token": raw,
                "target_kind": "PARTNER",
                "user_id": str(auth_users["member_user"]),
            },
        ).status_code
        == 422
    )
    clock.advance(seconds=app.state.settings.access_window_seconds + 1)
    login(recipient, "member@example.test")
    accepted = recipient.post(
        "/api/auth/invite/accept", json={"token": raw, "target_kind": "PARTNER"}
    )
    assert accepted.status_code == 204
    assert accepted.headers["X-HiAtlas-Invite-Target"] == "PARTNER"
    with Session(db_runtime) as db:
        assert identity_snapshot(db, auth_users["member_user"]) == before
        assert (
            db.get(PartnerMembership, partner_case["membership"]).invitation_pending
            is False
        )


def test_invite_target_exclusive_and_single_use(
    db_runtime, auth_users, partner_case, app, mail, client, scope_ids
):
    issue_partner(db_runtime, auth_users, partner_case, app)
    transport, worker = mail
    assert worker.deliver_batch(20).sent == 1
    raw = token_from(transport)
    with Session(db_runtime) as db:
        token = db.scalar(select(SecurityToken))
        assert token.membership_id is None
        assert token.partner_membership_id == partner_case["membership"]
        tenant_member = db.scalar(select(Membership))
        token.membership_id = tenant_member.id
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        token = db.scalar(select(SecurityToken))
        token.purpose = "PASSWORD_RESET"
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    login(client, "partner@example.test")
    for expected in (204, 400):
        assert (
            client.post(
                "/api/auth/invite/accept", json={"token": raw, "target_kind": "PARTNER"}
            ).status_code
            == expected
        )


def test_reissue_invalidates_old_partner_invite(
    db_runtime, auth_users, partner_case, app, mail, client
):
    issue_partner(db_runtime, auth_users, partner_case, app)
    transport, worker = mail
    assert worker.deliver_batch(20).sent == 1
    old = token_from(transport)
    issue_partner(db_runtime, auth_users, partner_case, app)
    assert worker.deliver_batch(20).sent == 1
    new = token_from(transport)
    assert old != new
    login(client, "partner@example.test")
    assert (
        client.post(
            "/api/auth/invite/accept", json={"token": old, "target_kind": "PARTNER"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/invite/accept", json={"token": new, "target_kind": "PARTNER"}
        ).status_code
        == 204
    )
    with Session(db_runtime) as db:
        rows = list(db.scalars(select(SecurityToken)))
        assert sum(row.invalidated_at is not None for row in rows) == 1
        assert sum(row.consumed_at is not None for row in rows) == 1
        assert all(row.ciphertext is None for row in db.scalars(select(EmailOutbox)))


def test_reset_revokes_partner_user_sessions(
    client, mail, auth_users, partner_case, new_client, db_runtime
):
    invitations()
    browsers = [new_client(), new_client(), new_client()]
    for browser in browsers:
        login(browser, "partner@example.test")
    raw = issue(client, mail, "partner@example.test")
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": NEW_PASSWORD},
        ).status_code
        == 204
    )
    assert all(browser.get("/api/auth/me").status_code == 401 for browser in browsers)
    with Session(db_runtime) as db:
        assert all(
            row.revoked_at
            for row in db.scalars(
                select(AuthSession).where(AuthSession.user_id == partner_case["user"])
            )
        )


def test_partner_invitation_audit_binds_typed_target(
    db_runtime, auth_users, partner_case, app, mail, client
):
    from app.audit.models import AuditEvent

    issue_partner(db_runtime, auth_users, partner_case, app)
    assert mail[1].deliver_batch(20).sent == 1
    raw = token_from(mail[0])
    login(client, "partner@example.test")
    assert (
        client.post(
            "/api/auth/invite/accept", json={"token": raw, "target_kind": "PARTNER"}
        ).status_code
        == 204
    )
    with Session(db_runtime) as db:
        rows = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.action.in_(
                        ["access.invite.requested", "access.invite.consumed"]
                    )
                )
            )
        )
        rows.sort(key=lambda row: row.action == "access.invite.consumed")
        assert len(rows) == 2
        for row in rows:
            assert row.entity_type == "partner_membership"
            assert row.entity_id == partner_case["membership"]
            assert row.after_state["target_kind"] == "PARTNER"
            assert row.after_state["partner_org_id"] == str(
                partner_case["organization"]
            )
            assert row.after_state["partner_membership_id"] == str(
                partner_case["membership"]
            )
            assert row.after_state["recipient_user_id"] == str(partner_case["user"])
            assert raw not in str(row.after_state)
        assert rows[0].after_state["actor_kind"] == "INTERNAL"
        assert rows[1].after_state["actor_kind"] == "PARTNER"


def test_new_partner_initial_credential_only(
    db_runtime, auth_users, partner_case, app, mail, client
):
    with Session(db_runtime) as db, db.begin():
        db.get(User, partner_case["user"]).password_hash = None
    issue_partner(db_runtime, auth_users, partner_case, app)
    assert mail[1].deliver_batch(20).sent == 1
    raw = token_from(mail[0])
    csrf(client)
    assert client.post(
        "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
    ).json() == {"target_kind": "PARTNER", "requires_authentication": False}
    assert (
        client.post(
            "/api/auth/invite/accept", json={"token": raw, "target_kind": "PARTNER"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/invite/accept",
            json={"token": raw, "target_kind": "PARTNER", "new_password": "short"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/invite/accept",
            json={"token": raw, "target_kind": "PARTNER", "new_password": NEW_PASSWORD},
        ).status_code
        == 204
    )
    login(client, "partner@example.test", NEW_PASSWORD)


def test_null_scoped_invite_is_not_internal_authority(
    db_runtime, auth_users, app, client
):
    from datetime import timedelta

    from app.core.security import new_token

    raw, hashed = new_token()
    with Session(db_runtime) as db, db.begin():
        db.add(
            SecurityToken(
                token_hash=hashed,
                purpose="INVITE",
                recipient_user_id=auth_users["member_user"],
                recipient_email="member@example.test",
                issuer_role="PLATFORM_ADMIN",
                created_at=app.state.clock(),
                expires_at=app.state.clock() + timedelta(hours=1),
            )
        )
    csrf(client)
    assert (
        client.post(
            "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/invite/accept", json={"token": raw, "target_kind": "INTERNAL"}
        ).status_code
        == 400
    )


def test_valid_internal_operator_invite_remains_discriminated(admin, mail, client):
    from tests.identity_helpers import PASSWORD

    assert (
        admin.post(
            "/api/platform/operators/invite",
            json={
                "email": "operator-new@example.test",
                "display_name": "New operator",
                "role": "PLATFORM_SUPPORT",
                "password": PASSWORD,
                "confirmation": {
                    "email": "operator-new@example.test",
                    "role": "PLATFORM_SUPPORT",
                },
            },
        ).status_code
        == 202
    )
    assert mail[1].deliver_batch(20).sent == 1
    raw = token_from(mail[0])
    csrf(client)
    assert client.post(
        "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
    ).json() == {"target_kind": "INTERNAL", "requires_authentication": False}
    assert (
        client.post(
            "/api/auth/invite/accept",
            json={
                "token": raw,
                "target_kind": "INTERNAL",
                "new_password": NEW_PASSWORD,
            },
        ).status_code
        == 204
    )
    assert (
        login(client, "operator-new@example.test", NEW_PASSWORD).json()["platform_role"]
        == "PLATFORM_SUPPORT"
    )


def test_reissue_cancels_queued_partner_outbox(
    db_runtime, auth_users, partner_case, app, mail
):
    issue_partner(db_runtime, auth_users, partner_case, app)
    issue_partner(db_runtime, auth_users, partner_case, app)
    with Session(db_runtime) as db:
        rows = list(db.scalars(select(EmailOutbox)))
        assert sorted(row.status for row in rows) == ["CANCELLED", "QUEUED"]
        assert all(row.ciphertext is None for row in rows if row.status == "CANCELLED")
    assert mail[1].deliver_batch(20).sent == 1


@pytest.mark.parametrize(
    "key,role", [("support_user", "PLATFORM_SUPPORT"), ("member_user", None)]
)
def test_only_current_admin_issues_partner_invite(
    db_runtime, auth_users, partner_case, app, mail, key, role
):
    api = invitations()
    actor = principal(db_runtime, auth_users[key], role)
    with Session(db_runtime) as db:
        db.info.update(
            settings=app.state.settings,
            email_transport=app.state.email_transport,
            clock=app.state.clock,
        )
        with pytest.raises(ApiError) as denied:
            api.issue_partner_invitation(db, actor, partner_case["membership"])
        assert denied.value.status == 403
        db.commit()
        assert db.scalar(select(SecurityToken)) is None
        assert db.scalar(select(EmailOutbox)) is None
        assert (
            db.get(PartnerMembership, partner_case["membership"]).invitation_pending
            is False
        )


def test_partner_issue_audit_failure_rolls_back_command(
    db_runtime, auth_users, partner_case, app, mail, monkeypatch
):
    api = invitations()
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")

    def fail(*args, **kwargs):
        raise RuntimeError("controlled partner invitation audit failure")

    monkeypatch.setattr("app.identity.tokens.append_event", fail)
    with Session(db_runtime) as db:
        db.info.update(
            settings=app.state.settings,
            email_transport=app.state.email_transport,
            clock=app.state.clock,
        )
        with pytest.raises(RuntimeError):
            api.issue_partner_invitation(db, actor, partner_case["membership"])
        db.commit()
        assert db.scalar(select(SecurityToken)) is None
        assert db.scalar(select(EmailOutbox)) is None
        member = db.get(PartnerMembership, partner_case["membership"])
        assert member.invitation_pending is False and member.version == 1


def test_partner_invite_requires_nonnull_issuer_role(
    db_runtime, auth_users, partner_case, app, mail
):
    issue_partner(db_runtime, auth_users, partner_case, app)
    with Session(db_runtime) as db:
        token = db.scalar(select(SecurityToken))
        token.issuer_role = None
        with pytest.raises(IntegrityError):
            db.flush()


def test_accept_expiry_during_real_organization_lock_wait(
    db_runtime, auth_users, partner_case, app, mail, client, clock
):
    import time
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import text

    from app.partners.models import PartnerOrganization

    issue_partner(db_runtime, auth_users, partner_case, app)
    assert mail[1].deliver_batch(20).sent == 1
    raw = token_from(mail[0])
    login(client, "partner@example.test")
    with Session(db_runtime) as blocker:
        blocker.scalar(
            select(PartnerOrganization)
            .where(PartnerOrganization.id == partner_case["organization"])
            .with_for_update()
        )
        blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        with ThreadPoolExecutor(1) as pool:
            task = pool.submit(
                client.post,
                "/api/auth/invite/accept",
                json={"token": raw, "target_kind": "PARTNER"},
            )
            try:
                deadline = time.monotonic() + 10
                with db_runtime.connect() as observer:
                    while not observer.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE :pid=ANY(pg_blocking_pids(pid)))"
                        ),
                        {"pid": blocker_pid},
                    ):
                        assert time.monotonic() < deadline, (
                            "Acceptance never waited for organization lock"
                        )
                        time.sleep(0.01)
                clock.advance(hours=25)
            finally:
                blocker.rollback()
            result = task.result(timeout=10)
            assert result.status_code == 400
            assert result.json()["code"] == "TOKEN_EXPIRED"
    with Session(db_runtime) as db:
        assert (
            db.get(PartnerMembership, partner_case["membership"]).invitation_pending
            is True
        )
        assert db.scalar(select(SecurityToken)).consumed_at is None
