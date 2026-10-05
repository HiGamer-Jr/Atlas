from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import AuthSession, EmailOutbox, SecurityToken
from app.tenancy.models import AccessContext
from tests.helpers import assert_internal_failure, select_context
from tests.identity_helpers import csrf, login

NEW_PASSWORD = "new-secure-test-password-2026"


def token_from(transport, index=-1):
    link = next(
        word
        for word in transport.messages[index].text.split()
        if word.startswith("https://")
    )
    return parse_qs(urlparse(link).fragment)["token"][0]


def issue(client, mail, email="member@example.test"):
    csrf(client)
    response = client.post("/api/auth/recovery", json={"email": email})
    assert response.status_code == 202
    transport, worker = mail
    assert worker.deliver_batch(20).sent == 1
    return token_from(transport)


def test_reset_valid_revokes_sessions_and_contexts(
    client, mail, member, scope_ids, db_runtime, new_client
):
    context_a = select_context(member, scope_ids["contract_a"])
    second = new_client()
    login(second, "member@example.test")
    context_b = select_context(second, scope_ids["contract_a2"])
    raw = issue(client, mail)
    response = client.post(
        "/api/auth/reset-password", json={"token": raw, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 204
    assert member.get("/api/auth/me").status_code == 401
    assert second.get("/api/auth/me").status_code == 401
    assert member.get("/api/context", headers=context_a).status_code == 401
    assert second.get("/api/context", headers=context_b).status_code == 401
    with Session(db_runtime) as db:
        assert all(row.revoked_at for row in db.scalars(select(AuthSession)))
        assert all(row.revoked_at for row in db.scalars(select(AccessContext)))
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": NEW_PASSWORD},
        ).status_code
        == 400
    )
    login(client, "member@example.test", NEW_PASSWORD)


@pytest.mark.parametrize(
    "kind", ["expired", "invalidated", "wrong-purpose", "recipient"]
)
def test_reset_rejects_invalid_token(client, mail, auth_users, clock, db_runtime, kind):
    raw = issue(client, mail)
    if kind == "expired":
        clock.advance(minutes=31)
        csrf(client)
    elif kind == "invalidated":
        csrf(client)
        client.post("/api/auth/recovery", json={"email": "member@example.test"})
    elif kind == "recipient":
        with Session(db_runtime) as db, db.begin():
            db.scalar(select(SecurityToken)).recipient_email = "different@example.test"
    purpose = "INVITE" if kind == "wrong-purpose" else "PASSWORD_RESET"
    response = client.post(
        "/api/auth/token/validate", json={"token": raw, "purpose": purpose}
    )
    assert response.status_code == 400


def test_reset_consume_concurrently_only_once(client, mail, auth_users, new_client):
    raw = issue(client, mail)
    clients = [new_client(), new_client()]
    for browser in clients:
        csrf(browser)
    barrier = Barrier(2)

    def consume(browser):
        barrier.wait()
        return browser.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": NEW_PASSWORD},
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(consume, clients)) == [204, 400]


def test_recovery_neutral_and_no_secrets(client, mail, auth_users):
    csrf(client)
    responses = [
        client.post("/api/auth/recovery", json={"email": email})
        for email in [
            "member@example.test",
            "missing@example.test",
            "support@example.test",
        ]
    ]
    assert all(response.status_code == 202 for response in responses)
    assert len({response.text for response in responses}) == 1
    assert set(responses[0].json()) == {"status", "message"}


def test_unconfigured_mail_is_not_success(client, auth_users):
    csrf(client)
    for email in ["member@example.test", "missing@example.test"]:
        assert (
            client.post("/api/auth/recovery", json={"email": email}).status_code == 503
        )


def test_invitation_creates_pending_membership(support, scope_ids, mail):
    scope = select_context(support, scope_ids["contract_a"])
    response = support.post(
        "/api/memberships",
        headers=scope,
        json={
            "email": "new@example.test",
            "display_name": "New user",
            "role_id": str(scope_ids["role_basic"]),
        },
    )
    assert response.status_code == 202


def test_recovery_existing_missing_blocked_inactive_have_identical_contract(
    client, mail, auth_users, db_runtime
):
    from app.identity.models import User

    csrf(client)
    outcomes = []
    for state in ["active", "blocked", "inactive", "missing"]:
        with Session(db_runtime) as db, db.begin():
            user = db.get(User, auth_users["member_user"])
            user.active, user.blocked = state != "inactive", state == "blocked"
        email = "missing@example.test" if state == "missing" else "member@example.test"
        response = client.post("/api/auth/recovery", json={"email": email})
        outcomes.append((response.status_code, response.text))
    assert len(set(outcomes)) == 1


def test_issue_and_consume_race_has_linearizable_result(
    client, mail, auth_users, new_client, db_runtime
):
    raw = issue(client, mail)
    consume_client, issue_client = new_client(), new_client()
    csrf(consume_client)
    csrf(issue_client)
    barrier = Barrier(2)

    def reset():
        barrier.wait()
        return consume_client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": NEW_PASSWORD},
        ).status_code

    def reissue():
        barrier.wait()
        return issue_client.post(
            "/api/auth/recovery", json={"email": "member@example.test"}
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        consumed, issued = pool.submit(reset), pool.submit(reissue)
        assert consumed.result() in {204, 400}
        assert issued.result() == 202
    with Session(db_runtime) as db:
        rows = list(
            db.scalars(
                select(SecurityToken).order_by(
                    SecurityToken.created_at, SecurityToken.id
                )
            )
        )
        assert len(rows) == 2
        assert (
            sum(row.invalidated_at is None and row.consumed_at is None for row in rows)
            == 1
        )


def test_issue_failure_rolls_back_token_and_outbox(
    client, mail, auth_users, db_runtime, monkeypatch
):
    def fail(*args, **kwargs):
        raise RuntimeError("controlled audit failure")

    monkeypatch.setattr("app.identity.tokens.append_event", fail)
    csrf(client)
    response = client.post("/api/auth/recovery", json={"email": "member@example.test"})
    assert_internal_failure(response, "controlled")
    with Session(db_runtime) as db:
        assert db.scalar(select(SecurityToken)) is None
        assert db.scalar(select(EmailOutbox)) is None


def test_audit_does_not_contain_credentials(client, mail, auth_users, db_runtime):
    from app.audit.models import AccessEvent, AuditEvent

    raw = issue(client, mail)
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": NEW_PASSWORD},
        ).status_code
        == 204
    )
    with Session(db_runtime) as db:
        for model in [AuditEvent, AccessEvent]:
            for row in db.scalars(select(model)):
                values = str(
                    {
                        col.name: getattr(row, col.name)
                        for col in model.__table__.columns
                    }
                )
                assert (
                    raw not in values
                    and NEW_PASSWORD not in values
                    and "$argon2" not in values
                )
