from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import SecurityToken, User
from app.tenancy.models import Membership
from tests.helpers import select_context
from tests.identity_helpers import PASSWORD, csrf, login
from tests.test_access_tokens import NEW_PASSWORD, token_from


def invite(support, scope_ids, email="new@example.test"):
    scope = select_context(support, scope_ids["contract_a"])
    response = support.post(
        "/api/memberships",
        headers=scope,
        json={
            "email": email,
            "display_name": "Invited",
            "role_id": str(scope_ids["role_basic"]),
        },
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
    return scope


def test_new_invitation_accept_login_and_replay(
    support, scope_ids, mail, client, db_runtime
):
    invite(support, scope_ids)
    assert mail[1].deliver_batch(20).sent == 1
    raw = token_from(mail[0])
    csrf(client)
    assert client.post(
        "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
    ).json() == {"requires_authentication": False}
    payload = {"token": raw, "new_password": NEW_PASSWORD}
    assert client.post("/api/auth/accept-invite", json=payload).status_code == 204
    assert client.post("/api/auth/accept-invite", json=payload).status_code == 400
    login(client, "new@example.test", NEW_PASSWORD)
    select_context(client, scope_ids["contract_a"])
    with Session(db_runtime) as db:
        user = db.scalar(
            select(User).where(User.email_normalized == "new@example.test")
        )
        assert user.password_hash.startswith("$argon2id$")
        assert not db.scalar(
            select(Membership).where(Membership.user_id == user.id)
        ).invitation_pending


def test_existing_identity_requires_own_session_preserves_password(
    support, scope_ids, mail, client, new_client, db_runtime
):
    invite(support, scope_ids, "other@example.test")
    mail[1].deliver_batch(20)
    raw = token_from(mail[0])
    csrf(client)
    assert (
        client.post("/api/auth/accept-invite", json={"token": raw}).status_code == 401
    )
    assert (
        support.post("/api/auth/accept-invite", json={"token": raw}).status_code == 401
    )
    login(client, "other@example.test")
    assert (
        client.post(
            "/api/auth/accept-invite", json={"token": raw, "new_password": NEW_PASSWORD}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/auth/accept-invite", json={"token": raw}).status_code == 204
    )
    other = new_client()
    login(other, "other@example.test", PASSWORD)
    select_context(other, scope_ids["contract_b"])
    select_context(other, scope_ids["contract_a"])


@pytest.mark.parametrize("kind", ["expired", "resend", "blocked", "role-changed"])
def test_invitation_invalidated(
    support, scope_ids, mail, client, db_runtime, clock, kind
):
    scope = invite(support, scope_ids)
    mail[1].deliver_batch(20)
    raw = token_from(mail[0])
    with Session(db_runtime) as db:
        token = db.scalar(select(SecurityToken))
        member_id = token.membership_id
    if kind == "expired":
        clock.advance(hours=25)
    elif kind == "resend":
        assert (
            support.post(
                f"/api/memberships/{member_id}/invite", headers=scope
            ).status_code
            == 202
        )
    elif kind == "blocked":
        assert (
            support.patch(
                f"/api/memberships/{member_id}/status",
                headers=scope,
                json={"blocked": True, "expected_version": 1},
            ).status_code
            == 200
        )
    else:
        from app.tenancy.models import TenantRole

        with Session(db_runtime) as db, db.begin():
            db.get(TenantRole, scope_ids["role_basic"]).support_assignable = False
    csrf(client)
    assert (
        client.post(
            "/api/auth/accept-invite", json={"token": raw, "new_password": NEW_PASSWORD}
        ).status_code
        == 400
    )


def test_invitation_concurrent_once(support, scope_ids, mail, new_client):
    invite(support, scope_ids)
    mail[1].deliver_batch(20)
    raw = token_from(mail[0])
    browsers = [new_client(), new_client()]
    for browser in browsers:
        csrf(browser)
    barrier = Barrier(2)

    def accept(browser):
        barrier.wait()
        return browser.post(
            "/api/auth/accept-invite", json={"token": raw, "new_password": NEW_PASSWORD}
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(accept, browsers)) == [204, 400]


def test_support_cannot_select_sensitive_role_or_edit_global_fields(
    support, scope_ids, mail
):
    scope = select_context(support, scope_ids["contract_a"])
    for extra in [{"password": "forbidden"}, {"platform_role": "PLATFORM_ADMIN"}]:
        assert (
            support.post(
                "/api/memberships",
                headers=scope,
                json={
                    "email": "other@example.test",
                    "display_name": "Other",
                    "role_id": str(scope_ids["role_basic"]),
                    **extra,
                },
            ).status_code
            == 422
        )
    assert (
        support.post(
            "/api/memberships",
            headers=scope,
            json={
                "email": "new@example.test",
                "display_name": "New",
                "role_id": str(scope_ids["role_finance"]),
            },
        ).status_code
        == 403
    )
    assert (
        support.patch(
            f"/api/memberships/{scope_ids['member_a']}/status",
            headers=scope,
            json={"email": "changed@example.test", "expected_version": 1},
        ).status_code
        == 422
    )
    assert (
        support.post(
            f"/api/memberships/{scope_ids['member_b']}/reset-password", headers=scope
        ).status_code
        == 404
    )
    assert (
        support.post(
            f"/api/memberships/{scope_ids['member_a']}/reset-password", headers=scope
        ).status_code
        == 202
    )
    assert (
        support.post(
            f"/api/memberships/{scope_ids['member_internal']}/reset-password",
            headers=scope,
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "email",
    [
        "a@example.test,b@example.test",
        "Name<a@example.test>",
        "a@example.test; b@example.test",
        "a@example.test\r\nBcc:b@example.test",
    ],
)
def test_invite_rejects_address_lists(support, scope_ids, mail, email):
    scope = select_context(support, scope_ids["contract_a"])
    response = support.post(
        "/api/memberships",
        headers=scope,
        json={
            "email": email,
            "display_name": "New",
            "role_id": str(scope_ids["role_basic"]),
        },
    )
    assert response.status_code == 422
    assert mail[1].deliver_batch(20).sent == 0
