from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.identity.dependencies import Database
from app.platform import roles
from app.platform.role_schemas import (
    RoleAssignment,
    RoleCreate,
    RoleList,
    RolePatch,
    RoleView,
)
from app.tenancy.dependencies import Context
from app.tenancy.schemas import ManagedMembershipView

router = APIRouter()


@router.get("/roles", response_model=RoleList)
def role_list(
    request: Request,
    db: Database,
    scope: Context,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
):
    return roles.list_roles(db, request.state.principal, scope, False, limit, offset)


@router.get("/roles/assignable", response_model=RoleList)
def assignable_list(
    request: Request,
    db: Database,
    scope: Context,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
):
    return roles.list_roles(db, request.state.principal, scope, True, limit, offset)


@router.post("/roles", status_code=201, response_model=RoleView)
def role_create(payload: RoleCreate, request: Request, db: Database, scope: Context):
    return roles.create_role(db, request, request.state.principal, scope, payload)


@router.patch("/roles/{role_id}", response_model=RoleView)
def role_patch(
    role_id: UUID, payload: RolePatch, request: Request, db: Database, scope: Context
):
    return roles.patch_role(
        db, request, request.state.principal, scope, role_id, payload
    )


@router.put("/memberships/{member_id}/role", response_model=ManagedMembershipView)
def member_role(
    member_id: UUID,
    payload: RoleAssignment,
    request: Request,
    db: Database,
    scope: Context,
):
    return roles.assign_role(
        db, request, request.state.principal, scope, member_id, payload
    )


@router.get("/capabilities")
def capabilities(request: Request, db: Database, scope: Context):
    from app.platform.capabilities import CATALOG
    from app.platform.policy import require_capability

    require_capability(db, request.state.principal, scope, "roles.manage")
    return {
        "items": [
            {"code": cap.code, "domain": cap.domain, "sensitive": cap.sensitive}
            for cap in sorted(CATALOG.values(), key=lambda item: item.code)
            if cap.tenant_role
        ]
    }
