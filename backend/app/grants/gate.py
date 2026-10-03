"""Central fail-closed derived-context gate, including routes with no database dependency."""

from uuid import UUID

from sqlalchemy import select

from app.grants.models import TemporaryPrivilegedGrant
from app.grants.schemas import GrantDenialProvenance
from app.grants.services import denied, lock_bound, terminal
from app.identity.schemas import Principal
from app.identity.sessions import session_candidate
from app.tenancy.models import Contract


def grant_control(kind):
    def decorate(endpoint):
        endpoint.grant_control = kind
        return endpoint

    return decorate


def privileged_read(capability, module_code, entity_scope):
    """Future reads explicitly register capability/module and scoped entity resolver."""

    def decorate(endpoint):
        endpoint.privileged_read = (capability, module_code, entity_scope)
        return endpoint

    return decorate


def check_request(db, request):
    declaration = getattr(request.scope.get("endpoint"), "privileged_read", None)
    try:
        context_id = UUID(request.headers.get("X-HiAtlas-Context", ""))
    except ValueError:
        return denied() if declaration else None
    row = db.scalar(
        select(TemporaryPrivilegedGrant).where(
            TemporaryPrivilegedGrant.context_id == context_id
        )
    )
    if row is None:
        return (
            denied() if declaration else None
        )  # Parent and independent tabs never inherit a grant.
    candidate = session_candidate(db, request)
    if (
        not candidate
        or row.operator_id != candidate.user_id
        or row.operator_session_id != candidate.id
    ):
        return denied()
    contract = db.get(Contract, row.contract_id)
    request.state.grant_denial = GrantDenialProvenance(
        actor_id=row.operator_id,
        actor_role=row.operator_role,
        tenant_id=row.tenant_id,
        contract_id=row.contract_id,
        environment=contract.environment,
        grant_id=row.id,
    )
    request.state.privileged_no_touch = True
    endpoint = request.scope.get("endpoint")
    control = getattr(endpoint, "grant_control", None)
    common = getattr(endpoint, "support_control", None)
    row, cause = lock_bound(db, row)
    if row.status == "ACTIVE" and cause:
        terminal(db, request, row, cause)
    if (row.status != "ACTIVE" or cause) and control != "end" and common != "logout":
        return denied()
    if common in {"identity", "csrf", "logout", "context"} or control in {
        "read",
        "end",
    }:
        return None
    declaration = getattr(endpoint, "privileged_read", None)
    if request.method == "GET" and declaration and row.grant_type == "FINANCIAL_FISCAL":
        from app.platform.policy import require_capability
        from app.tenancy.schemas import AccessScope

        capability, module, entity_scope = declaration
        principal = Principal(
            row.operator_id, row.operator_session_id, "PLATFORM_ADMIN"
        )
        scope = AccessScope(
            row.context_id,
            row.tenant_id,
            row.contract_id,
            row.operator_session_id,
            row.operator_id,
        )
        try:
            require_capability(db, principal, scope, capability, module_code=module)
            if not entity_scope(db, scope, request.path_params):
                return denied()
            row, cause = lock_bound(db, row)
            if row.status == "ACTIVE" and cause:
                terminal(db, request, row, cause)
            if row.status != "ACTIVE" or cause:
                return denied()
        except Exception as error:
            from app.core.errors import ApiError

            if isinstance(error, ApiError):
                return error
            raise
        return None
    return denied()


def record_denial(db, request, provenance, code):
    from app.audit.models import AccessEvent
    from app.grants.schemas import GrantDenialEvent

    event = GrantDenialEvent(
        **provenance.model_dump(), request_id=request.state.request_id, reason=code
    )
    data = event.model_dump(exclude={"grant_id"})
    db.add(
        AccessEvent(
            **data,
            action="privileged_grant.denied",
            outcome="DENIED",
            entity_type="privileged_grant",
            entity_id=provenance.grant_id,
        )
    )
    db.flush()
