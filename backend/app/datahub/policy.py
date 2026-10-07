"""Tenant authorization is independent of profile names and internal roles."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.datahub.catalog import DATASETS, template_definition
from app.datahub.types import AuthorizedSelection, AuthorizedUnit, Operation
from app.identity.schemas import Principal
from app.organization.models import MembershipUnitScope, OrganizationNode
from app.platform.policy import (
    effective_capabilities,
    require_capability,
    require_contracted_module,
)
from app.tenancy.contexts import membership_role, revalidate
from app.tenancy.schemas import AccessScope

UNIT_DATASETS = frozenset({"DEMANDS", "STOCK_POSITIONS", "FINANCIAL_FORECASTS"})


def authorize_selection(
    db: Session,
    principal: Principal,
    scope: AccessScope,
    operation: Operation,
    template_id: str,
    template_version: int,
    node_ids: tuple[UUID, ...],
) -> AuthorizedSelection:
    try:
        operation = Operation(operation)
        template = template_definition(template_id, template_version)
    except ValueError:
        raise ApiError(
            422, "TEMPLATE_INCOMPATIBLE", "Template ou operação incompatível."
        ) from None
    fresh, _, tenant, contract, _ = revalidate(db, principal, scope)
    # Neither support viewing nor privileged grants authorize connector access.
    from app.grants.models import TemporaryPrivilegedGrant
    from app.support.models import SupportSession

    if (
        fresh.platform_role == "PLATFORM_SUPPORT"
        or db.scalar(
            select(TemporaryPrivilegedGrant.id).where(
                TemporaryPrivilegedGrant.context_id == scope.id
            )
        )
        or db.scalar(
            select(SupportSession.id).where(SupportSession.context_id == scope.id)
        )
    ):
        raise ApiError(
            403, "CAPABILITY_DENIED", "Data Hub não permitido neste contexto."
        )
    membership, role = membership_role(
        db, fresh.user_id, scope.tenant_id, scope.contract_id
    )
    if membership is None or role is None:
        raise ApiError(
            403, "CAPABILITY_DENIED", "Data Hub não permitido neste contexto."
        )
    require_capability(db, principal, scope, "datahub.read", module_code="DATAHUB")
    general = {
        Operation.READ: "datahub.read",
        Operation.TEMPLATE: "datahub.template.download",
        Operation.IMPORT: "datahub.import",
        Operation.EXPORT: "datahub.export",
    }[operation]
    require_capability(db, principal, scope, general)
    if operation == Operation.IMPORT and not template.importable:
        raise ApiError(
            403,
            "TEMPLATE_READ_ONLY",
            "Este template permite somente consulta e exportação.",
        )
    assigned = tuple(
        db.scalars(
            select(MembershipUnitScope.node_id)
            .where(
                MembershipUnitScope.membership_id == membership.id,
                MembershipUnitScope.tenant_id == scope.tenant_id,
                MembershipUnitScope.contract_id == scope.contract_id,
                MembershipUnitScope.active.is_(True),
            )
            .order_by(MembershipUnitScope.node_id)
            .with_for_update()
        )
    )
    requested = tuple(sorted(set(node_ids or assigned), key=str))
    units = []
    for node_id in requested:
        try:
            require_capability(
                db, principal, scope, general, organization_node_id=node_id
            )
        except ApiError as error:
            if error.code == "UNIT_SCOPE_DENIED":
                if node_ids:
                    raise ApiError(
                        404, "NOT_FOUND", "Unidade não encontrada."
                    ) from None
                continue
            raise
        node = db.scalar(
            select(OrganizationNode).where(
                OrganizationNode.id == node_id,
                OrganizationNode.tenant_id == scope.tenant_id,
                OrganizationNode.contract_id == scope.contract_id,
            )
        )
        units.append(AuthorizedUnit(node.id, node.code, node.name, node.version))
    caps = effective_capabilities(db, principal, scope)
    selected = []
    suffix = "import" if operation == Operation.IMPORT else "read"
    for code in template.datasets:
        dataset = DATASETS[code]
        if (
            dataset.sensitive
            or f"datahub.{code.lower()}.read" not in caps
            or f"datahub.{code.lower()}.{suffix}" not in caps
        ):
            continue
        if (
            operation == Operation.EXPORT
            and f"datahub.{code.lower()}.export" not in caps
        ):
            continue
        if code in UNIT_DATASETS and not units:
            continue
        if dataset.module_code:
            try:
                require_contracted_module(db, principal, scope, dataset.module_code)
            except ApiError as error:
                if error.code == "MODULE_UNAVAILABLE":
                    continue
                raise
        selected.append(code)
    require_capability(db, principal, scope, general)
    if not selected:
        raise ApiError(
            403, "DATASET_DENIED", "Nenhum dataset permitido neste contexto."
        )
    return AuthorizedSelection(
        template.code,
        template.version,
        tuple(selected),
        role.name,
        tuple(units),
        tenant.name,
        contract.code,
        contract.environment,
    )
