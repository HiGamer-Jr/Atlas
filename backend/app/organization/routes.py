from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.identity.dependencies import Database
from app.organization import modules, services
from app.organization.catalogue import node_types
from app.organization.schemas import (
    ModuleList,
    ModulePatch,
    ModuleView,
    NodeCreate,
    NodeKind,
    NodeList,
    NodePatch,
    NodeView,
    UnitScopePatch,
    UnitScopeView,
)
from app.platform.policy import require_capability
from app.tenancy.dependencies import Context

router = APIRouter()


@router.get("/organization/node-types")
def types(request: Request, db: Database, scope: Context):
    require_capability(db, request.state.principal, scope, "organization.manage")
    return node_types()


@router.get("/organization/nodes", response_model=NodeList)
def nodes(
    request: Request,
    db: Database,
    scope: Context,
    search: str | None = Query(default=None, max_length=200),
    kind: NodeKind | None = None,
    status: Literal["ACTIVE", "INACTIVE"] | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    parent_for_kind: NodeKind | None = None,
    exclude_descendants_of: UUID | None = None,
):
    return services.list_nodes(
        db,
        request.state.principal,
        scope,
        search,
        kind,
        status,
        limit,
        offset,
        parent_for_kind,
        exclude_descendants_of,
    )


@router.get("/organization/nodes/{node_id}", response_model=NodeView)
def detail(node_id: UUID, request: Request, db: Database, scope: Context):
    return services.detail(db, request.state.principal, scope, node_id)


@router.post("/organization/nodes", status_code=201, response_model=NodeView)
def create(payload: NodeCreate, request: Request, db: Database, scope: Context):
    return services.create_node(db, request, request.state.principal, scope, payload)


@router.patch("/organization/nodes/{node_id}", response_model=NodeView)
def patch(
    node_id: UUID, payload: NodePatch, request: Request, db: Database, scope: Context
):
    return services.patch_node(
        db, request, request.state.principal, scope, node_id, payload
    )


@router.get("/contract/modules", response_model=ModuleList)
def module_list(request: Request, db: Database, scope: Context):
    return modules.list_modules(db, request.state.principal, scope)


@router.patch("/contract/modules/{code}", response_model=ModuleView)
def module_patch(
    code: str, payload: ModulePatch, request: Request, db: Database, scope: Context
):
    return modules.patch_module(
        db, request, request.state.principal, scope, code, payload
    )


@router.get("/memberships/{member_id}/unit-scope", response_model=UnitScopeView)
def unit_scope(member_id: UUID, request: Request, db: Database, scope: Context):
    return services.read_unit_scope(db, request.state.principal, scope, member_id)


@router.put("/memberships/{member_id}/unit-scope", response_model=UnitScopeView)
def update_unit_scope(
    member_id: UUID,
    payload: UnitScopePatch,
    request: Request,
    db: Database,
    scope: Context,
):
    return services.set_unit_scope(
        db, request, request.state.principal, scope, member_id, payload
    )
