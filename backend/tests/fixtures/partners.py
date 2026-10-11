import pytest
from sqlalchemy import inspect

from tests.identity_helpers import seed_user


@pytest.fixture
def partner_case(db_runtime):
    with db_runtime.connect() as conn:
        if not {
            "partner_organizations",
            "partner_memberships",
            "partner_membership_permissions",
        } <= set(inspect(conn).get_table_names()):
            return None
    from sqlalchemy.orm import Session

    from app.partners.models import PartnerMembership, PartnerOrganization

    user_id = seed_user(db_runtime, "partner@example.test")
    with Session(db_runtime) as session:
        organization = PartnerOrganization(
            name="External logistics", category="LOGISTICS_OPERATOR"
        )
        other = PartnerOrganization(name="Other company", category="OTHER")
        session.add_all([organization, other])
        session.flush()
        membership = PartnerMembership(organization_id=organization.id, user_id=user_id)
        session.add(membership)
        session.flush()
        result = {
            "organization": organization.id,
            "other_organization": other.id,
            "membership": membership.id,
            "user": user_id,
        }
        session.commit()
    return result
