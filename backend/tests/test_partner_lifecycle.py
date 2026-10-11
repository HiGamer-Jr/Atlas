from datetime import UTC, datetime, timedelta
from importlib import import_module, util
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.core.errors import ApiError
from app.identity.models import AuthSession, PlatformRoleAssignment
from app.identity.schemas import Principal
from app.partners.models import (
    PartnerMembership,
    PartnerMembershipPermission,
    PartnerOrganization,
)
from app.platform.capabilities import CATALOG


def lifecycle():
    assert util.find_spec("app.partners.lifecycle") is not None, (
        "Curated partner lifecycle is missing"
    )
    return import_module("app.partners.lifecycle"), import_module(
        "app.partners.schemas"
    )


def principal(engine, user_id, role):
    with Session(engine) as db:
        now = datetime.now(UTC)
        session = AuthSession(
            user_id=user_id,
            token_hash=uuid4().hex * 2,
            csrf_hash=uuid4().hex * 2,
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(hours=1),
        )
        db.add(session)
        db.flush()
        result = Principal(user_id, session.id, role)
        db.commit()
        return result


@pytest.mark.parametrize(
    "key,role", [("support_user", "PLATFORM_SUPPORT"), ("member_user", None)]
)
def test_support_and_tenant_cannot_provision(db_runtime, auth_users, key, role):
    api, schemas = lifecycle()
    actor = principal(db_runtime, auth_users[key], role)
    with Session(db_runtime) as db:
        with pytest.raises(ApiError) as denied:
            api.create_partner_organization(
                db,
                actor,
                schemas.PartnerOrganizationCreate(name="External", category="OTHER"),
            )
        assert denied.value.status == 403
        assert db.scalar(select(func.count()).select_from(PartnerOrganization)) == 0
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_partner_capabilities_never_enter_tenant_role_catalog():
    assert "partners.organizations.manage" in CATALOG, (
        "Dedicated lifecycle capability missing"
    )
    assert not any(
        item.tenant_role
        for code, item in CATALOG.items()
        if code.startswith(("partner.", "partners."))
    )
    api, _ = lifecycle()
    assert api is not None


def test_membership_replace_version_and_audit_atomic(
    db_runtime, auth_users, monkeypatch
):
    api, schemas = lifecycle()
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    with Session(db_runtime) as db:
        org = api.create_partner_organization(
            db,
            actor,
            schemas.PartnerOrganizationCreate(name="External", category="OTHER"),
        )
        member = api.create_partner_membership(
            db,
            actor,
            schemas.PartnerMembershipCreate(
                organization_id=org.id,
                user_id=auth_users["member_user"],
                permissions=["partner.processes.read"],
            ),
        )
        member_id = member.id
        db.commit()
        command = schemas.PartnerMembershipReplace(
            active=False,
            blocked=True,
            permissions=[],
            expected_version=1,
            reason="Curated suspension",
        )
        changed = api.replace_partner_membership(db, actor, member_id, command)
        assert changed.version == 2
        db.commit()
        event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "partner.membership.replaced")
        )
        assert event.actor_role == "PLATFORM_ADMIN"
        assert event.after_state["actor_kind"] == "INTERNAL"
        assert event.after_state["schema_version"] == 1
        assert event.before_state["permissions"] == ["partner.processes.read"]
        assert event.after_state["permissions"] == []
        with pytest.raises(ApiError) as stale:
            api.replace_partner_membership(db, actor, member_id, command)
        assert stale.value.status == 409
        db.rollback()

        def failure(*args, **kwargs):
            raise RuntimeError("audit unavailable")

        monkeypatch.setattr("app.partners.audit.append_event", failure)
        with pytest.raises(RuntimeError):
            api.replace_partner_membership(
                db,
                actor,
                member_id,
                command.model_copy(update={"expected_version": 2, "active": True}),
            )
        # Service failure rolls back even when caller catches it and commits.
        db.commit()
        db.expire_all()
        assert db.get(PartnerMembership, member_id).version == 2
        assert db.get(PartnerMembership, member_id).active is False
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 3


def test_reactivate_does_not_restore_removed_permissions(
    db_runtime, auth_users, partner_case
):
    api, schemas = lifecycle()
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    with Session(db_runtime) as db:
        member_id = partner_case["membership"]
        for active, permissions in [
            (True, ["partner.processes.read", "partner.timeline.read"]),
            (False, ["partner.processes.read"]),
            (True, ["partner.processes.read"]),
        ]:
            member = db.get(PartnerMembership, member_id)
            api.replace_partner_membership(
                db,
                actor,
                member_id,
                schemas.PartnerMembershipReplace(
                    active=active,
                    blocked=False,
                    permissions=permissions,
                    expected_version=member.version,
                    reason="Curated change",
                ),
            )
            db.commit()
        assert list(
            db.scalars(
                select(PartnerMembershipPermission.code).where(
                    PartnerMembershipPermission.membership_id == member_id,
                    PartnerMembershipPermission.active.is_(True),
                )
            )
        ) == ["partner.processes.read"]


@pytest.mark.parametrize("invalid", ["role", "revoked", "idle"])
def test_current_identity_revalidated(db_runtime, auth_users, invalid):
    api, schemas = lifecycle()
    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    with Session(db_runtime) as db:
        if invalid == "role":
            db.get(PlatformRoleAssignment, actor.user_id).role = "PLATFORM_SUPPORT"
        elif invalid == "revoked":
            db.get(AuthSession, actor.session_id).revoked_at = datetime.now(UTC)
        else:
            db.get(AuthSession, actor.session_id).last_seen_at = datetime.now(
                UTC
            ) - timedelta(days=1)
        db.commit()
        with pytest.raises(ApiError) as denied:
            api.create_partner_organization(
                db,
                actor,
                schemas.PartnerOrganizationCreate(name="External", category="OTHER"),
            )
        assert denied.value.status == (403 if invalid == "role" else 401)
        assert db.scalar(select(func.count()).select_from(PartnerOrganization)) == 0


def test_session_idle_expiry_during_organization_lock_wait(
    db_runtime, auth_users, partner_case
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.partners import lifecycle as api
    from app.partners.schemas import PartnerMembershipReplace

    actor = principal(db_runtime, auth_users["admin_user"], "PLATFORM_ADMIN")
    entered = Event()
    clock_released = Event()
    worker_pid = []
    clock = [datetime.now(UTC)]
    with Session(db_runtime) as blocker:
        blocker.scalar(
            select(PartnerOrganization)
            .where(PartnerOrganization.id == partner_case["organization"])
            .with_for_update()
        )

        def operation():
            with Session(db_runtime) as db:
                worker_pid.append(db.scalar(text("SELECT pg_backend_pid()")))
                db.info["clock"] = lambda: clock[0]
                # Signal after initial identity authorization and before organization wait.
                original_clock = db.info["clock"]

                def ticking():
                    value = original_clock()
                    if not entered.is_set():
                        entered.set()
                        assert clock_released.wait(10)
                    return value

                db.info["clock"] = ticking
                with pytest.raises(ApiError) as denied:
                    api.replace_partner_membership(
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
                assert denied.value.status == 401
                db.commit()

        with ThreadPoolExecutor(max_workers=1) as pool:
            task = pool.submit(operation)
            try:
                assert entered.wait(10), "Worker did not reach identity authorization"
                clock_released.set()
                import time

                deadline = time.monotonic() + 10
                with db_runtime.connect() as observer:
                    while not observer.scalar(
                        text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                        {"pid": worker_pid[0]},
                    ):
                        assert time.monotonic() < deadline, (
                            "Worker never waited for organization lock"
                        )
                        time.sleep(0.01)
                clock[0] += timedelta(hours=1)
            finally:
                clock_released.set()
                blocker.rollback()
            task.result(timeout=10)
    with Session(db_runtime) as db:
        assert db.get(PartnerMembership, partner_case["membership"]).version == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent)) == 0
