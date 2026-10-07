"""Immutable commercial catalogue; configuration is never operational authorization."""

from types import MappingProxyType

from app.audit.schemas import ContractModuleSnapshot
from app.core.errors import ApiError
from app.organization.models import ContractModule
from app.organization.schemas import ModuleView
from app.organization.services import scoped
from app.platform.policy import require_capability
from app.tenancy.contexts import revalidate
from app.tenancy.services import audit

CONTRACT_MODULE_CATALOG = MappingProxyType(
    {
        "PROCUREMENT": "Compras",
        "COMEX": "Compras Internacionais / COMEX",
        "INVENTORY": "Estoque",
        "FINANCE": "Financeiro",
        "PROJECTS": "Obras & Projetos",
        "DATAHUB": "DataHub",
    }
)
# Data Hub persists informational records; other operational domains remain unavailable.
OPERATIONAL_MODULES = frozenset({"DATAHUB"})


def snapshot(code, row):
    return ContractModuleSnapshot(
        code=code,
        contracted=row.contracted if row else False,
        active=row.active if row else False,
        version=row.version if row else 0,
    )


def view(code, row, manage):
    state = snapshot(code, row)
    return ModuleView(
        id=row.id if row else None,
        label=CONTRACT_MODULE_CATALOG[code],
        enabled=state.contracted and state.active,
        operational_available=code in OPERATIONAL_MODULES,
        allowed_actions=["edit"] if manage else [],
        **state.model_dump(),
    )


def list_modules(db, principal, scope):
    require_capability(db, principal, scope, "modules.read")
    fresh, *_ = revalidate(db, principal, scope)
    rows = {row.code: row for row in db.scalars(scoped(ContractModule, scope))}
    result = {
        "items": [
            view(code, rows.get(code), fresh.platform_role == "PLATFORM_ADMIN")
            for code in CONTRACT_MODULE_CATALOG
        ]
    }
    require_capability(db, principal, scope, "modules.read")
    return result


def patch_module(db, request, principal, scope, code, payload):
    require_capability(db, principal, scope, "modules.manage")
    if code not in CONTRACT_MODULE_CATALOG:
        raise ApiError(422, "UNKNOWN_CONTRACT_MODULE", "Módulo desconhecido.")
    row = db.scalar(
        scoped(ContractModule, scope)
        .where(ContractModule.code == code)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payload.module_id is not None and (row is None or row.id != payload.module_id):
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    require_capability(db, principal, scope, "modules.manage")
    if payload.expected_version != (row.version if row else 0) or (
        row is not None and payload.module_id is None
    ):
        raise ApiError(
            409, "VERSION_CONFLICT", "Registro alterado. Atualize antes de confirmar."
        )
    before = snapshot(code, row)
    if row is None:
        row = ContractModule(
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            code=code,
            version=1,
        )
        db.add(row)
    else:
        row.version += 1
    row.contracted, row.active = payload.contracted, payload.active
    db.flush()
    audit(
        db,
        request,
        principal,
        "contract.module.updated",
        "contract_module",
        row.id,
        before=before,
        after=snapshot(code, row),
        scope=scope,
    )
    require_capability(db, principal, scope, "modules.manage")
    return view(code, row, True)
