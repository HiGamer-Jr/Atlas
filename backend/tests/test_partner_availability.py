from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.identity.models import PlatformRoleAssignment
from app.partners.models import PartnerMembership, PartnerOrganization
from tests.identity_helpers import login

ORG = "/api/platform/partners/organizations"


def headers(key=None):
    return {"Idempotency-Key": str(key or uuid4())}


def test_comex_commercial_active_is_not_operational(member, scope_ids, db_runtime):
    with db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO contract_modules (tenant_id,contract_id,code,contracted,active) VALUES (:tenant,:contract,'COMEX',true,true)"
            ),
            {"tenant": scope_ids["tenant_a"], "contract": scope_ids["contract_a"]},
        )
    with db_runtime.connect() as conn:
        before = conn.scalar(text("SELECT count(*) FROM access_contexts"))
    assert member.get("/api/partner/availability").json() == {
        "schema_version": 1,
        "status": "DOMAIN_UNAVAILABLE",
        "code": "PARTNER_DOMAIN_UNAVAILABLE",
    }
    assert member.get("/api/partner/access-options").json() == []
    response = member.post(
        "/api/partner/contexts",
        json={"membership_id": str(uuid4()), "client_link_id": str(uuid4())},
    )
    assert response.status_code == 503, response.text
    with db_runtime.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM access_contexts")) == before
        assert (
            conn.scalar(text("SELECT to_regclass('partner_access_contexts')")) is None
        )


def test_internal_cannot_select_partner_context(admin):
    response = admin.post(
        "/api/partner/contexts",
        json={"membership_id": str(uuid4()), "client_link_id": str(uuid4())},
    )
    assert response.status_code == 403


@pytest.mark.parametrize("field", ["tenant_id", "role", "grant"])
def test_unknown_fields_fail_closed(admin, field):
    assert (
        admin.post(
            ORG,
            json={"name": "External", "category": "OTHER", field: str(uuid4())},
            headers=headers(),
        ).status_code
        == 422
    )
    assert (
        admin.post(
            "/api/partner/contexts",
            json={
                "membership_id": str(uuid4()),
                "client_link_id": str(uuid4()),
                field: str(uuid4()),
            },
        ).status_code
        == 422
    )


def test_lifecycle_post_idempotency(admin, auth_users, db_runtime):
    key = headers()
    payload = {"name": "External", "category": "OTHER", "expected_version": 0}
    first = admin.post(ORG, json=payload, headers=key)
    assert first.status_code == 201, first.text
    assert admin.post(ORG, json=payload, headers=key).json() == first.json()
    assert (
        admin.post(ORG, json={**payload, "name": "Different"}, headers=key).status_code
        == 409
    )
    with Session(db_runtime) as db:
        assert db.scalar(select(func.count()).select_from(PartnerOrganization)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1
        db.get(
            PlatformRoleAssignment, auth_users["admin_user"]
        ).role = "PLATFORM_SUPPORT"
        db.commit()
    assert admin.post(ORG, json=payload, headers=key).status_code == 403


def test_lifecycle_requires_csrf_origin_key_and_recent_auth(admin, clock):
    payload = {"name": "External", "category": "OTHER"}
    assert admin.post(ORG, json=payload).status_code == 422
    assert (
        admin.post(
            ORG, json=payload, headers={**headers(), "X-CSRF-Token": ""}
        ).status_code
        == 403
    )
    assert (
        admin.post(
            ORG, json=payload, headers={**headers(), "Origin": "https://foreign.test"}
        ).status_code
        == 403
    )
    key = headers()
    assert admin.post(ORG, json=payload, headers=key).status_code == 201
    clock.advance(minutes=6)
    assert admin.post(ORG, json=payload, headers=key).status_code == 403


def test_membership_patch_replays_original_version(admin, auth_users, db_runtime):
    org = admin.post(
        ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
    )
    assert org.status_code == 201, org.text
    path = f"{ORG}/{org.json()['id']}/memberships"
    create = admin.post(
        path,
        json={
            "user_id": str(auth_users["member_user"]),
            "permissions": ["partner.processes.read"],
            "expected_version": 0,
        },
        headers=headers(),
    )
    assert create.status_code == 201, create.text
    target = f"/api/platform/partners/memberships/{create.json()['id']}"
    key = headers()
    patch = {
        "active": False,
        "blocked": True,
        "permissions": [],
        "expected_version": 1,
        "reason": "Suspend",
    }
    first = admin.patch(target, json=patch, headers=key)
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 2
    again = admin.patch(
        target,
        json={**patch, "active": True, "blocked": False, "expected_version": 2},
        headers=headers(),
    )
    assert again.status_code == 200
    assert admin.patch(target, json=patch, headers=key).json() == first.json()
    assert (
        admin.patch(
            target,
            json={k: v for k, v in patch.items() if k != "expected_version"},
            headers=headers(),
        ).status_code
        == 422
    )
    assert admin.patch(target, json=patch).status_code == 422
    assert (
        admin.post(
            path, json={"user_id": str(uuid4()), "permissions": []}, headers=headers()
        ).status_code
        == 404
    )
    assert (
        admin.post(
            path,
            json={
                "organization_id": str(uuid4()),
                "user_id": str(auth_users["member_user"]),
                "permissions": [],
            },
            headers=headers(),
        ).status_code
        == 422
    )
    with Session(db_runtime) as db:
        assert db.get(PartnerMembership, create.json()["id"]).version == 3


def test_receipts_immutable_and_null_namespace_unique(admin, db_runtime, db_owner):
    first = admin.post(
        ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
    )
    assert first.status_code == 201, first.text
    from sqlalchemy.exc import DBAPIError, IntegrityError

    with db_runtime.begin() as conn:
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(text("UPDATE partner_lifecycle_receipts SET status_code=200"))
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(text("DELETE FROM partner_lifecycle_receipts"))
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                text(
                    "INSERT INTO partner_lifecycle_receipts(user_id,session_id,route,target_id,key,digest,response_json,status_code) SELECT user_id,session_id,route,target_id,key,digest,response_json,status_code FROM partner_lifecycle_receipts"
                )
            )
    with db_owner.begin() as conn, pytest.raises(DBAPIError), conn.begin_nested():
        conn.execute(text("UPDATE partner_lifecycle_receipts SET status_code=200"))


def test_availability_requires_authentication(client):
    assert client.get("/api/partner/access-options").status_code == 401
    assert client.get("/api/partner/availability").status_code == 401


def test_lifecycle_support_and_tenant_denied(support, new_client, auth_users):
    tenant = new_client()
    login(tenant, "member@example.test")
    for browser in (support, tenant):
        assert (
            browser.post(
                ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
            ).status_code
            == 403
        )


def test_new_recipient_atomic_and_invite_first_credential(
    admin, db_runtime, mail, client
):
    from app.identity.models import PlatformRoleAssignment, User
    from app.tenancy.models import Membership
    from tests.identity_helpers import csrf
    from tests.test_access_tokens import NEW_PASSWORD, token_from

    org = admin.post(
        ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
    )
    assert org.status_code == 201, org.text
    path = f"{ORG}/{org.json()['id']}/memberships"
    payload = {
        "recipient": {
            "email": "New.Partner@example.test",
            "display_name": "New Partner",
        },
        "permissions": [],
    }
    key = headers()
    created = admin.post(path, json=payload, headers=key)
    assert created.status_code == 201, created.text
    assert admin.post(path, json=payload, headers=key).json() == created.json()
    member_id = created.json()["id"]
    with Session(db_runtime) as db:
        user = db.scalar(
            select(User).where(User.email_normalized == "new.partner@example.test")
        )
        assert user.password_hash is None and user.active and not user.blocked
        assert db.get(PlatformRoleAssignment, user.id) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.user_id == user.id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(PartnerMembership)
                .where(PartnerMembership.user_id == user.id)
            )
            == 1
        )
        event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "partner.membership.created")
        )
        assert event.after_state["recipient_provisioning"] == "CREATED"
    invite = f"/api/platform/partners/memberships/{member_id}/invite"
    invitation_key = headers()
    sent = admin.post(invite, json={}, headers=invitation_key)
    assert sent.status_code == 202, sent.text
    assert admin.post(invite, json={}, headers=invitation_key).json() == sent.json()
    transport, worker = mail
    assert worker.deliver_batch(20).sent == 1
    raw = token_from(transport)
    csrf(client)
    assert client.post(
        "/api/auth/token/validate", json={"token": raw, "purpose": "INVITE"}
    ).json() == {"target_kind": "PARTNER", "requires_authentication": False}
    assert (
        client.post(
            "/api/auth/invite/accept",
            json={"token": raw, "target_kind": "PARTNER", "new_password": NEW_PASSWORD},
        ).status_code
        == 204
    )
    login(client, "new.partner@example.test", NEW_PASSWORD)


def test_recipient_existing_identity_preserved_and_xor(admin, auth_users, db_runtime):
    from app.identity.models import User

    org = admin.post(
        ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
    )
    assert org.status_code == 201, org.text
    path = f"{ORG}/{org.json()['id']}/memberships"
    recipient = {"email": "member@example.test", "display_name": "Overwrite attempted"}
    with Session(db_runtime) as db:
        user = db.get(User, auth_users["member_user"])
        before = (user.display_name, user.password_hash, user.active, user.blocked)
    for payload in (
        {"permissions": []},
        {
            "permissions": [],
            "recipient": recipient,
            "user_id": str(auth_users["member_user"]),
        },
    ):
        assert admin.post(path, json=payload, headers=headers()).status_code == 422
    result = admin.post(
        path, json={"recipient": recipient, "permissions": []}, headers=headers()
    )
    assert result.status_code == 201, result.text
    assert result.json()["user_id"] == str(auth_users["member_user"])
    with Session(db_runtime) as db:
        user = db.get(User, auth_users["member_user"])
        assert (
            user.display_name,
            user.password_hash,
            user.active,
            user.blocked,
        ) == before


def test_recipient_audit_failure_rolls_back_user(admin, db_runtime, monkeypatch):
    from app.identity.models import User

    org = admin.post(
        ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
    )
    assert org.status_code == 201, org.text

    def failure(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("app.partners.audit.append_event", failure)
    response = admin.post(
        f"{ORG}/{org.json()['id']}/memberships",
        json={
            "recipient": {
                "email": "rollback@example.test",
                "display_name": "Rollback",
            },
            "permissions": [],
        },
        headers=headers(),
    )
    assert response.status_code == 500
    with Session(db_runtime) as db:
        assert (
            db.scalar(
                select(User.id).where(User.email_normalized == "rollback@example.test")
            )
            is None
        )
        assert db.scalar(select(func.count()).select_from(PartnerMembership)) == 0


@pytest.mark.parametrize("state", [{"active": False}, {"blocked": True}])
def test_curated_recipient_never_reactivates_identity(
    admin, auth_users, db_runtime, state
):
    from app.identity.models import User

    org = admin.post(
        ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
    )
    assert org.status_code == 201
    with Session(db_runtime) as db:
        user = db.get(User, auth_users["member_user"])
        for name, value in state.items():
            setattr(user, name, value)
        db.commit()
    response = admin.post(
        f"{ORG}/{org.json()['id']}/memberships",
        json={
            "recipient": {"email": "member@example.test", "display_name": "Ignored"},
            "permissions": [],
        },
        headers=headers(),
    )
    assert response.status_code == 404
    with Session(db_runtime) as db:
        assert db.scalar(select(func.count()).select_from(PartnerMembership)) == 0
        user = db.get(User, auth_users["member_user"])
        for name, value in state.items():
            assert getattr(user, name) == value


def test_receipt_insert_failure_rolls_back_mutation_and_audit(
    admin, db_runtime, monkeypatch
):
    from sqlalchemy import event

    def failure(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO partner_lifecycle_receipts"):
            raise RuntimeError("receipt unavailable")

    engine = admin.app.state.database_engine
    event.listen(engine, "before_cursor_execute", failure)
    try:
        response = admin.post(
            ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
        )
        assert response.status_code == 500
    finally:
        event.remove(engine, "before_cursor_execute", failure)
    with Session(db_runtime) as db:
        assert db.scalar(select(func.count()).select_from(PartnerOrganization)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_replay_reauthentication_expires_during_organization_lock_wait(
    admin, db_runtime, clock
):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sqlalchemy import event

    org = admin.post(
        ORG, json={"name": "External", "category": "OTHER"}, headers=headers()
    )
    org_id = org.json()["id"]
    # Use creation replay: receipt exists, but original organization is now the target of membership command.
    payload = {
        "recipient": {"email": "wait@example.test", "display_name": "Wait"},
        "permissions": [],
    }
    path = f"{ORG}/{org_id}/memberships"
    key = headers()
    first = admin.post(path, json=payload, headers=key)
    assert first.status_code == 201
    entered = Event()
    worker_pid = []
    engine = admin.app.state.database_engine

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "FROM partner_organizations" in statement and "FOR UPDATE" in statement:
            worker_pid.append(conn.scalar(text("SELECT pg_backend_pid()")))
            entered.set()

    event.listen(engine, "before_cursor_execute", capture)
    with Session(db_runtime) as blocker:
        blocker.scalar(
            select(PartnerOrganization)
            .where(PartnerOrganization.id == org_id)
            .with_for_update()
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            task = pool.submit(lambda: admin.post(path, json=payload, headers=key))
            try:
                assert entered.wait(10)
                deadline = time.monotonic() + 10
                with db_runtime.connect() as observer:
                    while not observer.scalar(
                        text("SELECT cardinality(pg_blocking_pids(:pid))>0"),
                        {"pid": worker_pid[0]},
                    ):
                        assert time.monotonic() < deadline
                        time.sleep(0.01)
                clock.advance(minutes=6)
            finally:
                blocker.rollback()
                event.remove(engine, "before_cursor_execute", capture)
            assert task.result(timeout=10).status_code == 403


def test_lifecycle_route_waits_without_holding_operator_lock(admin, db_runtime):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sqlalchemy import event

    from app.identity.operators import OPERATOR_LOCK
    from app.identity.tokens import LIFECYCLE_LOCK

    entered = Event()
    worker_pid = []
    engine = admin.app.state.database_engine

    def capture(conn, cursor, statement, parameters, context, executemany):
        if "pg_advisory_xact_lock(" in statement and not entered.is_set():
            worker_pid.append(conn.scalar(text("SELECT pg_backend_pid()")))
            entered.set()

    event.listen(engine, "before_cursor_execute", capture)
    with db_runtime.begin() as blocker:
        blocker.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": LIFECYCLE_LOCK}
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            task = pool.submit(
                lambda: admin.post(
                    ORG,
                    json={"name": "External", "category": "OTHER"},
                    headers=headers(),
                )
            )
            try:
                assert entered.wait(10)
                deadline = time.monotonic() + 10
                with db_runtime.connect() as observer:
                    while not observer.scalar(
                        text("SELECT cardinality(pg_blocking_pids(:pid))>0"),
                        {"pid": worker_pid[0]},
                    ):
                        assert time.monotonic() < deadline
                        time.sleep(0.01)
                assert blocker.scalar(
                    text("SELECT pg_try_advisory_xact_lock(:key)"),
                    {"key": OPERATOR_LOCK},
                )
            finally:
                blocker.rollback()
                event.remove(engine, "before_cursor_execute", capture)
            assert task.result(timeout=10).status_code == 201


def test_partner_cannot_use_tenant_context_header(new_client, partner_case, db_runtime):
    partner = new_client()
    login(partner, "partner@example.test")
    assert (
        partner.post(
            "/api/contexts",
            json={
                "membership_id": str(partner_case["membership"]),
                "client_link_id": str(uuid4()),
            },
        ).status_code
        == 422
    )
    response = partner.get(
        "/api/context", headers={"X-HiAtlas-Context": str(partner_case["membership"])}
    )
    assert response.status_code == 403
    with db_runtime.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM access_contexts")) == 0
