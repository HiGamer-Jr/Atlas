import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.core.errors import ApiError
from app.identity.models import AuthSession, PlatformRoleAssignment, SecurityToken
from app.identity.tokens import LIFECYCLE_LOCK
from app.partners import lifecycle
from app.partners.models import (
    PartnerLifecycleReceipt,
    PartnerMembership,
    PartnerMembershipPermission,
    PartnerOrganization,
)
from app.partners.schemas import PartnerMembershipReplace
from tests.identity_helpers import login
from tests.test_access_tokens import token_from
from tests.test_partner_availability import ORG, headers
from tests.test_partner_invitations import issue_partner
from tests.test_partner_lifecycle import principal


def invite(db_runtime, auth_users, partner_case, app, mail):
    issue_partner(db_runtime, auth_users, partner_case, app)
    transport, worker = mail
    assert worker.deliver_batch(20).sent == 1
    return token_from(transport)


def accept(browser, raw):
    return browser.post(
        "/api/auth/invite/accept", json={"token": raw, "target_kind": "PARTNER"}
    ).status_code


def test_concurrent_invite_accept_has_one_effect(
    db_runtime, auth_users, partner_case, app, mail, new_client
):
    raw = invite(db_runtime, auth_users, partner_case, app, mail)
    browsers = [new_client(), new_client()]
    for browser in browsers:
        login(browser, "partner@example.test")
    barrier = Barrier(2)

    def run(browser):
        barrier.wait(timeout=10)
        return accept(browser, raw)

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(run, browsers)) == [204, 400]
    with Session(db_runtime) as db:
        assert not db.get(
            PartnerMembership, partner_case["membership"]
        ).invitation_pending
        assert (
            db.scalar(
                select(func.count())
                .select_from(SecurityToken)
                .where(SecurityToken.consumed_at.is_not(None))
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "access.invite.consumed")
            )
            == 1
        )
        assert db.get(PlatformRoleAssignment, partner_case["user"]) is None
        assert (
            len(
                list(
                    db.scalars(
                        select(AuthSession).where(
                            AuthSession.user_id == partner_case["user"]
                        )
                    )
                )
            )
            == 2
        )


def test_reissue_vs_accept_linearizes(
    db_runtime, auth_users, partner_case, app, mail, new_client
):
    raw = invite(db_runtime, auth_users, partner_case, app, mail)
    browser = new_client()
    login(browser, "partner@example.test")
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    entered, pids = Event(), []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT pg_advisory_xact_lock"):
            pids.append(conn.connection.driver_connection.info.backend_pid)
            entered.set()

    engine = app.state.database_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        with Session(db_runtime) as blocker:
            blocker.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": LIFECYCLE_LOCK}
            )
            blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
            with ThreadPoolExecutor(1) as pool:
                future = pool.submit(accept, browser, raw)
                try:
                    assert entered.wait(10)
                    wait_for_block(db_runtime, pids[0], blocker_pid)
                    blocker.info.update(
                        settings=app.state.settings,
                        email_transport=app.state.email_transport,
                        clock=app.state.clock,
                    )
                    from app.partners.invitations import issue_partner_invitation

                    issue_partner_invitation(blocker, actor, partner_case["membership"])
                    blocker.commit()
                finally:
                    blocker.rollback()
                assert future.result(timeout=20) == 400
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    transport, worker = mail
    assert worker.deliver_batch(20).sent == 1
    assert accept(browser, token_from(transport)) == 204
    with Session(db_runtime) as db:
        assert not db.get(
            PartnerMembership, partner_case["membership"]
        ).invitation_pending
        assert db.get(PlatformRoleAssignment, partner_case["user"]) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(SecurityToken)
                .where(SecurityToken.consumed_at.is_not(None))
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "access.invite.consumed")
            )
            == 1
        )


def wait_for_block(engine, worker_pid, blocker_pid):
    deadline = time.monotonic() + 10
    with engine.connect() as observer:
        while not observer.scalar(
            text("SELECT :blocker=ANY(pg_blocking_pids(:worker))"),
            {"blocker": blocker_pid, "worker": worker_pid},
        ):
            assert time.monotonic() < deadline, (
                "Worker did not wait for the attested blocker"
            )
            time.sleep(0.01)


def test_platform_role_revoked_while_waiting_denies_lifecycle(
    db_runtime, auth_users, partner_case
):
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    entered, pids = Event(), []

    def run():
        with Session(db_runtime) as db:
            pids.append(db.scalar(text("SELECT pg_backend_pid()")))
            entered.set()
            try:
                lifecycle.replace_partner_membership(
                    db,
                    actor,
                    partner_case["membership"],
                    PartnerMembershipReplace(
                        active=False,
                        blocked=True,
                        permissions=[],
                        expected_version=1,
                        reason="Suspension",
                    ),
                )
            except ApiError as error:
                db.rollback()
                return error.status
            db.commit()
            return 200

    with Session(db_runtime) as blocker:
        from app.identity.operators import lock_operator_population

        lock_operator_population(blocker)
        blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(run)
            try:
                assert entered.wait(10)
                wait_for_block(db_runtime, pids[0], blocker_pid)
                blocker.get(PlatformRoleAssignment, actor.user_id).active = False
                blocker.commit()
            finally:
                blocker.rollback()
            assert future.result(timeout=20) == 403
    with Session(db_runtime) as db:
        assert db.get(PartnerMembership, partner_case["membership"]).version == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_membership_replace_same_version_one_winner(
    db_runtime, auth_users, partner_case
):
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    barrier = Barrier(2)
    choices = [["partner.processes.read"], ["partner.payment_requests.read_org"]]

    def run(permissions):
        with Session(db_runtime) as db:
            barrier.wait(timeout=10)
            try:
                lifecycle.replace_partner_membership(
                    db,
                    actor,
                    partner_case["membership"],
                    PartnerMembershipReplace(
                        active=True,
                        blocked=False,
                        permissions=permissions,
                        expected_version=1,
                        reason="Replace",
                    ),
                )
            except ApiError as error:
                db.rollback()
                return error.status, permissions
            db.commit()
            return 200, permissions

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(run, choices))
    assert sorted(status for status, _ in results) == [200, 409]
    winner = next(permissions for status, permissions in results if status == 200)
    with Session(db_runtime) as db:
        assert db.get(PartnerMembership, partner_case["membership"]).version == 2
        assert (
            sorted(
                db.scalars(
                    select(PartnerMembershipPermission.code).where(
                        PartnerMembershipPermission.membership_id
                        == partner_case["membership"]
                    )
                )
            )
            == winner
        )
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 1


@pytest.mark.parametrize("fault", ["audit", "receipt"])
def test_receipt_audit_failure_rolls_back(admin, db_runtime, monkeypatch, fault):
    def failure(*args, **kwargs):
        raise RuntimeError("injected persistence failure")

    def receipt_failure(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO partner_lifecycle_receipts"):
            failure()

    engine = admin.app.state.database_engine
    if fault == "audit":
        monkeypatch.setattr("app.partners.audit.append_event", failure)
    else:
        event.listen(engine, "before_cursor_execute", receipt_failure)
    try:
        assert (
            admin.post(
                ORG,
                json={"name": "Atomic external", "category": "OTHER"},
                headers=headers(),
            ).status_code
            == 500
        )
    finally:
        if fault == "receipt":
            event.remove(engine, "before_cursor_execute", receipt_failure)
    with Session(db_runtime) as db:
        for model in (PartnerOrganization, PartnerLifecycleReceipt, AuditEvent):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_accept_before_reissue_preserves_consumption(
    db_runtime, auth_users, partner_case, app, mail, new_client
):
    raw = invite(db_runtime, auth_users, partner_case, app, mail)
    browser = new_client()
    login(browser, "partner@example.test")
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    consumed, release, reissue_entered = Event(), Event(), Event()
    acceptance_pids, reissue_pids = [], []

    def pause(conn, cursor, statement, parameters, context, executemany):
        if (
            statement.startswith("UPDATE security_tokens")
            and "consumed_at" in statement
        ):
            acceptance_pids.append(conn.connection.driver_connection.info.backend_pid)
            consumed.set()
            assert release.wait(15)

    def reissue():
        from app.partners.invitations import issue_partner_invitation

        with Session(db_runtime) as db:
            db.info.update(
                settings=app.state.settings,
                email_transport=app.state.email_transport,
                clock=app.state.clock,
            )
            reissue_pids.append(db.scalar(text("SELECT pg_backend_pid()")))
            reissue_entered.set()
            issue_partner_invitation(db, actor, partner_case["membership"])
            db.commit()

    engine = app.state.database_engine
    event.listen(engine, "after_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(2) as pool:
            accepted = pool.submit(accept, browser, raw)
            try:
                assert consumed.wait(10)
                issued = pool.submit(reissue)
                assert reissue_entered.wait(10)
                wait_for_block(db_runtime, reissue_pids[0], acceptance_pids[0])
            finally:
                release.set()
            assert accepted.result(timeout=20) == 204
            issued.result(timeout=20)
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause)
    assert accept(browser, raw) == 400
    with Session(db_runtime) as db:
        assert db.get(PartnerMembership, partner_case["membership"]).invitation_pending
        assert (
            db.scalar(
                select(func.count())
                .select_from(SecurityToken)
                .where(SecurityToken.consumed_at.is_not(None))
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "access.invite.consumed")
            )
            == 1
        )
        assert db.get(PlatformRoleAssignment, partner_case["user"]) is None
