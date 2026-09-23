from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    "classification,flag,locked,permissions,eligible",
    [
        ("STANDARD", True, False, {"memberships.read"}, True),
        ("STANDARD", False, False, {"memberships.read"}, False),
        ("FINANCIAL_FISCAL", True, False, set(), False),
        ("ADMINISTRATIVE", True, False, set(), False),
        ("SENSITIVE", True, False, set(), False),
        ("STANDARD", True, False, {"finance.read"}, False),
        ("STANDARD", True, False, {"fiscal.read"}, False),
        ("STANDARD", True, False, {"roles.manage"}, False),
        ("STANDARD", True, False, {"unknown.permission"}, False),
        ("STANDARD", True, True, {"roles.read"}, False),
    ],
)
def test_support_eligibility_uses_classification_history_and_catalog(
    classification, flag, locked, permissions, eligible
):
    from app.platform.policy import role_support_eligible

    role = SimpleNamespace(
        classification=classification,
        support_assignable=flag,
        sensitivity_locked=locked,
        active=True,
        name="Harmless name",
    )
    assert role_support_eligible(role, permissions) is eligible


@pytest.mark.parametrize("browser", ["admin", "support", "member"])
@pytest.mark.parametrize(
    "capability", ["finance.read", "fiscal.read", "unknown.permission"]
)
def test_financial_and_unknown_capabilities_are_denied_everywhere(
    request, browser, capability, scope_ids, db_runtime
):
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.core.errors import ApiError
    from app.identity.schemas import Principal
    from app.platform.policy import require_capability
    from app.tenancy.models import AccessContext
    from app.tenancy.schemas import AccessScope
    from tests.helpers import CONTEXT_HEADER, select_context

    client = request.getfixturevalue(browser)
    header = select_context(client, scope_ids["contract_a"])
    with Session(db_runtime) as db, db.begin():
        context = db.scalar(
            select(AccessContext).where(
                AccessContext.id == UUID(header[CONTEXT_HEADER])
            )
        )
        scope = AccessScope(
            context.id,
            context.tenant_id,
            context.contract_id,
            context.session_id,
            context.actor_id,
        )
        # Even a stale/forged ADMIN label cannot grant a reserved capability.
        principal = Principal(context.actor_id, context.session_id, "PLATFORM_ADMIN")
        with pytest.raises(ApiError) as failure:
            require_capability(db, principal, scope, capability)
        assert failure.value.status == 403
