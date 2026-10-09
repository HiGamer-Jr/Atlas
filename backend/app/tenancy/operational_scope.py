"""Authenticated self-discovery, scoped and server-calculated on every request."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.datahub.catalog import DATASETS
from app.identity.schemas import Principal
from app.organization.models import ContractModule
from app.organization.modules import CONTRACT_MODULE_CATALOG, OPERATIONAL_MODULES
from app.organization.unit_authorization import invalid, resolve_unit_scope
from app.platform.capabilities import CATALOG
from app.platform.policy import effective_capabilities
from app.tenancy.contexts import membership_role, revalidate
from app.tenancy.operational_scope_schemas import (
    CustomerScope,
    OperationalScopeView,
    ScopeContract,
    ScopeModule,
    ScopeNode,
    ScopeRole,
    ScopeTenant,
    UnitPolicy,
)
from app.tenancy.schemas import AccessScope

UNIT_CAP_PREFIXES = (
    "datahub.demands.",
    "datahub.stock_positions.",
    "datahub.financial_forecasts.",
)
DATASET_MODULES = {
    code.value.lower(): dataset.module_code
    for code, dataset in DATASETS.items()
    if dataset.module_code
}


def operational_scope_view(
    db: Session, principal: Principal, scope: AccessScope
) -> OperationalScopeView:
    fresh, _, tenant, contract, _ = revalidate(db, principal, scope)
    customer = None
    actor = (
        "INTERNAL"
        if fresh.platform_role in {"PLATFORM_ADMIN", "PLATFORM_SUPPORT"}
        else "TENANT"
    )
    if actor == "TENANT":
        member, role = membership_role(
            db, fresh.user_id, scope.tenant_id, scope.contract_id
        )
        if member is None or role is None:
            raise invalid()
        units = resolve_unit_scope(db, scope, member)
        rows = list(
            db.scalars(
                select(ContractModule)
                .where(
                    ContractModule.tenant_id == scope.tenant_id,
                    ContractModule.contract_id == scope.contract_id,
                )
                .order_by(ContractModule.code)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if any(
            row.code not in CONTRACT_MODULE_CATALOG
            or (row.active and not row.contracted)
            for row in rows
        ):
            raise invalid()
        settings = db.info.get("settings")
        feature_available = settings is None or settings.datahub_enabled
        operational_enabled = {
            row.code
            for row in rows
            if row.active
            and row.contracted
            and row.code in OPERATIONAL_MODULES
            and (row.code != "DATAHUB" or feature_available)
        }
        modules = [
            ScopeModule(
                code=row.code,
                label=CONTRACT_MODULE_CATALOG[row.code],
                contracted=True,
                active=row.active,
                operational_available=row.code in operational_enabled,
            )
            for row in rows
            if row.contracted
        ]
        enabled = {row.code for row in rows if row.active and row.contracted}
        caps = effective_capabilities(db, fresh, scope)
        descriptive = []
        for code in sorted(caps):
            cap = CATALOG.get(code)
            if cap is None:
                raise invalid()
            module = cap.module_code or {
                "finance.read": "FINANCE",
                "fiscal.read": "FINANCE",
            }.get(code)
            if module and module not in operational_enabled:
                continue
            if code.startswith(UNIT_CAP_PREFIXES) and not units.nodes:
                continue
            dataset = code.split(".")[1] if code.startswith("datahub.") else None
            if dataset in DATASET_MODULES and DATASET_MODULES[dataset] not in enabled:
                continue
            descriptive.append(code)
        visible = {node.id for node in units.nodes}
        customer = CustomerScope(
            role=ScopeRole(id=role.id, code=role.code, name=role.name),
            unit_scope=UnitPolicy(mode=units.mode),
            organization_nodes=[
                ScopeNode(
                    id=n.id,
                    code=n.code,
                    name=n.name,
                    kind=n.kind,
                    parent_id=n.parent_id if n.parent_id in visible else None,
                )
                for n in units.nodes
            ],
            modules=modules,
            capabilities=descriptive,
        )
    revalidate(db, fresh, scope)
    return OperationalScopeView(
        actor_kind=actor,
        context_id=scope.id,
        tenant=ScopeTenant(id=tenant.id, name=tenant.name),
        contract=ScopeContract(
            id=contract.id,
            name=contract.name,
            code=contract.code,
            environment=contract.environment,
        ),
        customer_scope=customer,
    )
