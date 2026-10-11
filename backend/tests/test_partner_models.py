import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError


def test_partner_member_is_not_tenant_membership(db_runtime, partner_case):
    assert partner_case is not None, "Partner identity persistence is missing"
    from sqlalchemy.orm import Session

    from app.partners.models import PartnerMembership, PartnerOrganization

    with Session(db_runtime) as session:
        organization = session.get(PartnerOrganization, partner_case["organization"])
        member = session.get(PartnerMembership, partner_case["membership"])
        assert (
            organization.name,
            organization.category,
            organization.active,
            organization.version,
        ) == ("External logistics", "LOGISTICS_OPERATOR", True, 1)
        assert (
            member.user_id,
            member.organization_id,
            member.active,
            member.blocked,
            member.invitation_pending,
            member.version,
        ) == (partner_case["user"], organization.id, True, False, False, 1)
        for table in (
            "memberships",
            "tenant_roles",
            "tenant_role_permissions",
            "tenants",
        ):
            assert (
                session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            )


def test_partner_permission_cross_org_fk_rejected(db_runtime, partner_case):
    assert partner_case is not None, "Partner identity persistence is missing"
    with pytest.raises(IntegrityError) as error, db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO partner_membership_permissions(organization_id,membership_id,code) VALUES (:org,:member,'partner.processes.read')"
            ),
            {
                "org": partner_case["other_organization"],
                "member": partner_case["membership"],
            },
        )
    assert error.value.orig.sqlstate == "23503"


def test_partner_user_org_unique(db_runtime, partner_case):
    assert partner_case is not None, "Partner identity persistence is missing"
    with pytest.raises(IntegrityError) as error, db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO partner_memberships(organization_id,user_id) VALUES (:org,:user)"
            ),
            {"org": partner_case["organization"], "user": partner_case["user"]},
        )
    assert error.value.orig.sqlstate == "23505"


@pytest.mark.parametrize(
    "code",
    [
        "roles.manage",
        "finance.read",
        "partner.payment_requests.approve",
        "partner.*",
        "partner.processes.unknown",
    ],
)
def test_partner_permission_rejects_non_catalog_codes(db_runtime, partner_case, code):
    assert partner_case is not None, "Partner identity persistence is missing"
    with pytest.raises(IntegrityError) as error, db_runtime.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO partner_membership_permissions(organization_id,membership_id,code) VALUES (:org,:member,:code)"
            ),
            {
                "org": partner_case["organization"],
                "member": partner_case["membership"],
                "code": code,
            },
        )
    assert error.value.orig.sqlstate == "23514"


@pytest.mark.parametrize(
    "code",
    [
        "partner.processes.read",
        "partner.timeline.read",
        "partner.logistics.update",
        "partner.processes.closure_report",
        "partner.documents.create",
        "partner.documents.read",
        "partner.payment_requests.create",
        "partner.payment_requests.read_org",
        "partner.payment_requests.submit",
        "partner.payment_requests.withdraw",
    ],
)
def test_partner_permission_catalog_persists_individual_active_permission(
    db_runtime, partner_case, code
):
    assert partner_case is not None, "Partner identity persistence is missing"
    from sqlalchemy.orm import Session

    from app.partners.models import PartnerMembershipPermission

    with Session(db_runtime) as session:
        permission = PartnerMembershipPermission(
            organization_id=partner_case["organization"],
            membership_id=partner_case["membership"],
            code=code,
        )
        session.add(permission)
        session.commit()
        assert permission.active is True
        permission.active = False
        session.commit()
        assert (
            session.scalar(
                select(PartnerMembershipPermission).where(
                    PartnerMembershipPermission.code == code
                )
            ).active
            is False
        )


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO partner_organizations(name,category) VALUES ('  ','TRADE')",
        "INSERT INTO partner_organizations(name,category) VALUES ('Company','UNKNOWN')",
        "INSERT INTO partner_organizations(name,category,version) VALUES ('Company','TRADE',0)",
        "UPDATE partner_memberships SET version=0",
    ],
)
def test_partner_identity_rejects_invalid_state(db_runtime, partner_case, statement):
    assert partner_case is not None, "Partner identity persistence is missing"
    with pytest.raises(IntegrityError) as error, db_runtime.begin() as conn:
        conn.execute(text(statement))
    assert error.value.orig.sqlstate == "23514"


def test_partner_identity_restricts_parent_deletion(db_owner, partner_case):
    assert partner_case is not None, "Partner identity persistence is missing"
    for statement, value in [
        ("DELETE FROM users WHERE id=:id", partner_case["user"]),
        (
            "DELETE FROM partner_organizations WHERE id=:id",
            partner_case["organization"],
        ),
    ]:
        with pytest.raises(IntegrityError) as error, db_owner.begin() as conn:
            conn.execute(text(statement), {"id": value})
        assert error.value.orig.sqlstate in {"23001", "23503"}
