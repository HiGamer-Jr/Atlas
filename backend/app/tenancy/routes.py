from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.identity.dependencies import Database
from app.support.gate import support_control
from app.tenancy import services
from app.tenancy.contexts import authenticated
from app.tenancy.dependencies import Context
from app.tenancy.operational_scope import operational_scope_view
from app.tenancy.operational_scope_schemas import OperationalScopeView
from app.tenancy.schemas import (
    ContextCreate,
    ContextCreated,
    ContextView,
    ContractCreate,
    ContractList,
    ContractView,
    ManagedMembershipView,
    TenantCreate,
    TenantView,
)

router = APIRouter()


@router.get("/context/operational-scope", response_model=OperationalScopeView)
@support_control("context")
def operational_scope_get(
    request: Request, response: Response, db: Database, scope: Context
):
    response.headers["Cache-Control"] = "no-store"
    return operational_scope_view(db, request.state.principal, scope)


@router.get("/contracts", response_model=ContractList)
def contracts(
    request: Request,
    db: Database,
    search: str = Query(default="", max_length=128),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
):
    return services.list_contracts(
        db, authenticated(db, request), search, limit, offset
    )


@router.post("/tenants", status_code=201, response_model=TenantView)
def tenant_create(payload: TenantCreate, request: Request, db: Database):
    return services.create_tenant(db, request, authenticated(db, request), payload)


@router.post(
    "/tenants/{tenant_id}/contracts", status_code=201, response_model=ContractView
)
def contract_create(
    tenant_id: UUID, payload: ContractCreate, request: Request, db: Database
):
    return services.create_contract(
        db, request, authenticated(db, request), tenant_id, payload
    )


@router.post("/contexts", status_code=201, response_model=ContextCreated)
def context_create(payload: ContextCreate, request: Request, db: Database):
    return services.select_context(
        db, request, authenticated(db, request), payload.contract_id
    )


@router.delete("/contexts/{context_id}", status_code=204)
def context_close(context_id: UUID, request: Request, db: Database):
    services.close_context(db, request, authenticated(db, request), context_id)
    return Response(status_code=204)


@router.get("/context", response_model=ContextView)
@support_control("context")
def context_get(request: Request, db: Database, scope: Context):
    return services.context_view(db, request.state.principal, scope)


@router.get("/memberships/{member_id}", response_model=ManagedMembershipView)
def membership_get(member_id: UUID, request: Request, db: Database, scope: Context):
    return services.get_membership(db, request.state.principal, scope, member_id)
