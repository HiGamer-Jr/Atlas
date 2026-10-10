"""Contract lock serializes prospective approval decisions and policy upserts."""

from sqlalchemy import select

from app.audit.schemas import AuditInput, RequestPolicySnapshot
from app.audit.service import append_event
from app.core.errors import ApiError
from app.platform.policy import require_capability
from app.procurement.requests.models import ContractRequestPolicy
from app.procurement.requests.schemas import ApprovalPolicyView
from app.tenancy.contexts import contract_rows


def policy_row(db, scope):
    contract_rows(db, scope.contract_id)
    return db.scalar(
        select(ContractRequestPolicy)
        .where(
            ContractRequestPolicy.tenant_id == scope.tenant_id,
            ContractRequestPolicy.contract_id == scope.contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def effective_approval_policy(db, scope) -> ApprovalPolicyView:
    row = policy_row(db, scope)
    if row is not None and row.approval_mode not in {"REQUIRED", "NOT_REQUIRED"}:
        raise ApiError(409, "INVALID_POLICY", "Política indisponível.")
    return ApprovalPolicyView(
        approval_mode=row.approval_mode if row else "REQUIRED",
        version=row.version if row else 0,
    )


def patch_approval_policy(db, request, principal, scope, payload) -> ApprovalPolicyView:
    require_capability(db, principal, scope, "modules.manage")
    row = policy_row(db, scope)
    before = effective_approval_policy(db, scope)
    require_capability(db, principal, scope, "modules.manage")
    if payload.expected_version != before.version:
        raise ApiError(
            409, "VERSION_CONFLICT", "Política alterada. Atualize antes de confirmar."
        )
    if row is None:
        row = ContractRequestPolicy(
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            approval_mode=payload.approval_mode,
            version=1,
        )
        db.add(row)
    else:
        row.approval_mode = payload.approval_mode
        row.version += 1
    db.flush()
    after = effective_approval_policy(db, scope)
    append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role=principal.platform_role,
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            action="procurement.request_policy.updated",
            entity_type="contract_request_policy",
            entity_id=scope.contract_id,
            before=RequestPolicySnapshot(**before.model_dump()),
            after=RequestPolicySnapshot(**after.model_dump()),
            reason=payload.reason,
            request_id=request.state.request_id,
        ),
    )
    require_capability(db, principal, scope, "modules.manage")
    return after
