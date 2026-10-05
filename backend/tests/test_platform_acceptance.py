"""Foundation acceptance across a process restart and contextual read surfaces."""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import select_context
from tests.identity_helpers import SESSION_COOKIE


@pytest.mark.parametrize("operator", ["admin", "support"])
def test_contextual_surfaces_remain_bound_after_restart(
    request, operator, scope_ids, settings
):
    browser = request.getfixturevalue(operator)
    scope = select_context(browser, scope_ids["contract_a"])
    token = browser.cookies.get(SESSION_COOKIE)
    with TestClient(create_app(settings), base_url="https://testserver") as restarted:
        restarted.cookies.set(SESSION_COOKIE, token)
        context = restarted.get("/api/context", headers=scope)
        assert context.status_code == 200
        assert context.json()["contract_id"] == str(scope_ids["contract_a"])
        for path in (
            "/api/memberships",
            "/api/roles/assignable",
            "/api/contract/modules",
            "/api/support-sessions",
        ):
            result = restarted.get(path, headers=scope)
            assert result.status_code == 200
            serialized = result.text
            assert str(scope_ids["member_a2"]) not in serialized
            assert str(scope_ids["member_b"]) not in serialized
            assert str(scope_ids["role_a2"]) not in serialized
            assert str(scope_ids["role_b"]) not in serialized
        roles = restarted.get("/api/roles/assignable", headers=scope).json()["items"]
        assert all(
            row.get("code") not in {"PLATFORM_ADMIN", "PLATFORM_SUPPORT"}
            for row in roles
        )


def test_context_does_not_transfer_to_new_http_session_after_restart(
    admin, scope_ids, settings
):
    from tests.identity_helpers import login

    scope = select_context(admin, scope_ids["contract_a"])
    with TestClient(create_app(settings), base_url="https://testserver") as restarted:
        login(restarted)
        assert restarted.get("/api/context", headers=scope).status_code == 403
        assert restarted.get("/api/memberships", headers=scope).status_code == 403
